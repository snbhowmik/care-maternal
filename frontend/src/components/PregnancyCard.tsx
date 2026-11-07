import { useCallback, useEffect, useState } from "react";

import { EMERGENCY_SYMPTOMS } from "@/types";
import type { Alert, Pregnancy, ScheduleItem } from "@/types";
import { currentFacilityId, errorMessage, request } from "@/utils/api";

import BookVisit from "./BookVisit";
import Referrals from "./Referrals";

const ORDER = ["overdue", "due", "upcoming", "waiting", "done"] as const;
const STATE_CLASS: Record<string, string> = {
  overdue: "bg-danger-100 text-danger-700",
  due: "bg-warning-100 text-warning-700",
  upcoming: "bg-secondary-200 text-secondary-800",
  waiting: "bg-secondary-200 text-secondary-800",
  done: "bg-primary-100 text-primary-800",
};

interface Props {
  pregnancy: Pregnancy;
}

export default function PregnancyCard({ pregnancy }: Props) {
  const [items, setItems] = useState<ScheduleItem[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [symptoms, setSymptoms] = useState<string[]>([]);

  const reload = useCallback(async () => {
    try {
      const [i, a] = await Promise.all([
        request<ScheduleItem[]>(`/pregnancies/${pregnancy.id}/items/`),
        request<Alert[]>(`/pregnancies/${pregnancy.id}/alerts/`),
      ]);
      setItems(i);
      setAlerts(a);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [pregnancy.id]);

  useEffect(() => {
    reload();
  }, [reload]);

  async function act(label: string, fn: () => Promise<unknown>) {
    setError("");
    setNotice("");
    try {
      await fn();
      setNotice(label);
      await reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  const markDone = (item: ScheduleItem, date: string) =>
    act(`Recorded: ${item.label}`, () =>
      request(`/pregnancies/${pregnancy.id}/items/${item.spec_id}/complete/`, "POST", { on_date: date, facility: currentFacilityId() }),
    );

  const reportEmergency = () =>
    act("Emergency reported. Clinician alerted.", async () => {
      await request(`/pregnancies/${pregnancy.id}/emergency/`, "POST", { symptoms });
      setSymptoms([]);
    });

  const runSweep = () =>
    act("Overdue check done.", async () => {
      const r = await request<{ overdue_alerts_raised: number }>(
        `/pregnancies/${pregnancy.id}/sweep/`, "POST",
      );
      setNotice(`Overdue check done: ${r.overdue_alerts_raised} new alert(s).`);
    });

  const noShow = (item: ScheduleItem) =>
    act(`Marked no-show: ${item.label}. The visit is due again.`, () =>
      request(`/pregnancies/${pregnancy.id}/items/${item.spec_id}/no-show/`, "POST"),
    );

  const bookVisit = async (item: ScheduleItem, date: string, time: string) => {
    await act(`Booked: ${item.label} on ${date} at ${time}. The patient can see it in CARE appointments.`, () =>
      request(`/pregnancies/${pregnancy.id}/items/${item.spec_id}/book/`, "POST", { on_date: date, start_time: time }),
    );
  };

  const grouped = ORDER.map((s) => ({ state: s, rows: items.filter((i) => i.state === s) }));

  return (
    <section className="rounded-lg border border-secondary-400 bg-white p-4 space-y-4">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-bold text-secondary-900">
          {pregnancy.gestational_age.weeks}+{pregnancy.gestational_age.days} weeks · EDD {pregnancy.edd}
        </h3>
        <span className="text-sm text-secondary-700">
          G{pregnancy.gravida} P{pregnancy.para} A{pregnancy.abortions} L{pregnancy.living} · LMP {pregnancy.lmp}
        </span>
      </header>

      {error && <p className="text-sm text-danger-500">{error}</p>}
      {notice && <p className="text-sm text-primary-700">{notice}</p>}

      <div className="space-y-3">
        {grouped.filter((g) => g.rows.length).map((g) => (
          <div key={g.state}>
            <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-secondary-600">
              {g.state} ({g.rows.length})
            </h4>
            <ul className="space-y-1">
              {g.rows.map((item) => (
                <ItemRow key={item.id} item={item} pregnancyId={pregnancy.id} onDone={markDone} onBook={bookVisit} onNoShow={noShow} />
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="rounded border border-danger-100 bg-danger-50 p-3 space-y-2">
        <h4 className="font-semibold text-danger-700">Report emergency symptoms</h4>
        <div className="grid gap-1 sm:grid-cols-2">
          {EMERGENCY_SYMPTOMS.map((s) => (
            <label key={s.value} className="flex items-center gap-2 text-sm text-secondary-900">
              <input type="checkbox" checked={symptoms.includes(s.value)}
                onChange={(e) =>
                  setSymptoms((prev) =>
                    e.target.checked ? [...prev, s.value] : prev.filter((v) => v !== s.value),
                  )
                } />
              {s.label}
            </label>
          ))}
        </div>
        <button type="button" disabled={!symptoms.length} onClick={reportEmergency}
          className="rounded bg-danger-600 px-3 py-2 text-white disabled:opacity-50">
          Report emergency
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={runSweep}
          className="rounded border border-secondary-500 px-3 py-2 text-secondary-900">
          Run overdue check
        </button>
      </div>

      <Referrals pregnancyId={pregnancy.id} />

      <div>
        <h4 className="mb-1 font-semibold text-secondary-900">Alerts</h4>
        {alerts.length === 0 && <p className="text-sm text-secondary-600">No alerts.</p>}
        <ul className="space-y-1 text-sm">
          {alerts.map((a) => (
            <li key={a.id} className="rounded bg-secondary-100 px-2 py-1">
              <span className="font-medium">{a.audience}</span> · {a.message}
              {a.sms_sent && <span className="ml-2 text-primary-700">(SMS sent)</span>}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function ItemRow({
  item,
  pregnancyId,
  onDone,
  onBook,
  onNoShow,
}: {
  item: ScheduleItem;
  pregnancyId: string;
  onDone: (i: ScheduleItem, d: string) => void;
  onBook: (i: ScheduleItem, d: string, time: string) => Promise<void>;
  onNoShow: (i: ScheduleItem) => void;
}) {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [booking, setBooking] = useState(false);
  const open = item.state !== "done" && item.state !== "waiting";
  const bookable = item.state !== "done";
  const appointment = item.appointment_at
    ? new Date(item.appointment_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
    : null;
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 rounded border border-secondary-300 px-2 py-1 text-sm">
      <span className="flex items-center gap-2">
        <span className={`rounded px-2 py-0.5 text-xs ${STATE_CLASS[item.state]}`}>{item.state}</span>
        {item.label}
      </span>
      <span className="flex flex-wrap items-center gap-2 text-secondary-700">
        {item.done_on ? `done ${item.done_on}` : item.due_to ? `by ${item.due_to}` : item.waiting_on}
        {appointment && <span className="rounded bg-secondary-100 px-2 py-0.5">appointment {appointment}</span>}
        {open && (
          <>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)}
              className="rounded border border-secondary-400 px-1 py-0.5" />
            <button type="button" onClick={() => onDone(item, date)}
              className="rounded bg-primary-700 px-2 py-1 text-white">Mark done</button>
            {item.appointment_at && (
              <button type="button" onClick={() => onNoShow(item)}
                className="rounded border border-danger-500 px-2 py-1 text-danger-500">No-show</button>
            )}
          </>
        )}
        {bookable && (
          <button type="button" onClick={() => setBooking((b) => !b)}
            className="rounded border border-primary-700 px-2 py-1 text-primary-700">
            {booking ? "Close calendar" : item.appointment_at ? "Rebook" : "Book visit"}
          </button>
        )}
      </span>
      {bookable && booking && (
        <BookVisit pregnancyId={pregnancyId} item={item} onBook={async (i, d, t) => {
          await onBook(i, d, t);
          setBooking(false);
        }} />
      )}
    </li>
  );
}
