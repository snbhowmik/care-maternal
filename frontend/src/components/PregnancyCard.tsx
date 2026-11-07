import { useCallback, useEffect, useState } from "react";

import { Alert as AlertBox, AlertDescription, AlertTitle } from "@/components/careui/alert";
import { Badge } from "@/components/careui/badge";
import { Button } from "@/components/careui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/careui/card";
import { Checkbox } from "@/components/careui/checkbox";
import { Input } from "@/components/careui/input";
import { Label } from "@/components/careui/label";
import { Separator } from "@/components/careui/separator";
import { EMERGENCY_SYMPTOMS } from "@/types";
import type { Alert, ItemState, Pregnancy, ScheduleItem } from "@/types";
import { currentFacilityId, errorMessage, request } from "@/utils/api";

import BookVisit from "./BookVisit";
import Referrals from "./Referrals";

const ORDER: ItemState[] = ["overdue", "due", "upcoming", "waiting", "done"];
const STATE_LABEL: Record<ItemState, string> = {
  overdue: "Overdue",
  due: "Due",
  upcoming: "Upcoming",
  waiting: "Waiting",
  done: "Done",
};
const STATE_BADGE = {
  overdue: "destructive",
  due: "warning",
  upcoming: "info",
  waiting: "neutral",
  done: "success",
} as const;

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

  /** Runs an action, then shows its message (or the error) and reloads. */
  async function act(fn: () => Promise<string>) {
    setError("");
    setNotice("");
    try {
      setNotice(await fn());
      await reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  const markDone = (item: ScheduleItem, date: string) =>
    act(async () => {
      await request(`/pregnancies/${pregnancy.id}/items/${item.spec_id}/complete/`, "POST", {
        on_date: date,
        facility: currentFacilityId(),
      });
      return `Recorded: ${item.label}`;
    });

  const reportEmergency = () =>
    act(async () => {
      await request(`/pregnancies/${pregnancy.id}/emergency/`, "POST", { symptoms });
      setSymptoms([]);
      return "Emergency reported. The clinician is alerted.";
    });

  const runSweep = () =>
    act(async () => {
      const r = await request<{ overdue_alerts_raised: number }>(`/pregnancies/${pregnancy.id}/sweep/`, "POST");
      return `Overdue check done: ${r.overdue_alerts_raised} new alert(s).`;
    });

  const noShow = (item: ScheduleItem) =>
    act(async () => {
      await request(`/pregnancies/${pregnancy.id}/items/${item.spec_id}/no-show/`, "POST");
      return `Marked no-show: ${item.label}. The visit is due again.`;
    });

  const bookVisit = (item: ScheduleItem, date: string, time: string) =>
    act(async () => {
      await request(`/pregnancies/${pregnancy.id}/items/${item.spec_id}/book/`, "POST", {
        on_date: date,
        start_time: time,
      });
      return `Booked: ${item.label} on ${date} at ${time}. The patient can see it in CARE appointments.`;
    });

  const grouped = ORDER.map((s) => ({ state: s, rows: items.filter((i) => i.state === s) }));
  const ga = pregnancy.gestational_age;

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {ga.weeks}+{ga.days} weeks · EDD {pregnancy.edd}
        </CardTitle>
        <CardDescription>
          G{pregnancy.gravida} P{pregnancy.para} A{pregnancy.abortions} L{pregnancy.living} · LMP {pregnancy.lmp}
        </CardDescription>
        <CardAction>
          <Button type="button" variant="tertiary" size="sm" onClick={runSweep}>
            Run overdue check
          </Button>
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-6">
        {error && (
          <AlertBox variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </AlertBox>
        )}
        {notice && (
          <AlertBox variant="success">
            <AlertDescription>{notice}</AlertDescription>
          </AlertBox>
        )}

        <section className="flex flex-col gap-4" aria-label="Schedule of checks">
          {grouped.filter((g) => g.rows.length).map((g) => (
            <div key={g.state} className="flex flex-col gap-2">
              <h4 className="flex items-center gap-2 text-sm font-semibold text-foreground">
                {STATE_LABEL[g.state]}
                <Badge variant={STATE_BADGE[g.state]}>{g.rows.length}</Badge>
              </h4>
              <ul className="flex flex-col gap-2">
                {g.rows.map((item) => (
                  <ItemRow key={item.id} item={item} pregnancyId={pregnancy.id}
                    onDone={markDone} onBook={bookVisit} onNoShow={noShow} />
                ))}
              </ul>
            </div>
          ))}
        </section>

        <Separator />

        <AlertBox variant="destructive">
          <AlertTitle>Report emergency symptoms</AlertTitle>
          <AlertDescription>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {EMERGENCY_SYMPTOMS.map((s) => (
                <Label key={s.value} className="flex items-center gap-2 font-normal text-foreground">
                  <Checkbox checked={symptoms.includes(s.value)}
                    onCheckedChange={(checked) =>
                      setSymptoms((prev) => (checked ? [...prev, s.value] : prev.filter((v) => v !== s.value)))
                    } />
                  {s.label}
                </Label>
              ))}
            </div>
            <Button type="button" variant="destructive" size="sm" className="mt-3"
              disabled={!symptoms.length} onClick={reportEmergency}>
              Report emergency
            </Button>
          </AlertDescription>
        </AlertBox>

        <Separator />

        <Referrals pregnancyId={pregnancy.id} />

        <Separator />

        <section className="flex flex-col gap-2" aria-label="Alerts">
          <h4 className="text-sm font-semibold text-foreground">Alerts</h4>
          {alerts.length === 0 && <p className="text-sm text-muted-foreground">No alerts.</p>}
          <ul className="flex flex-col gap-2">
            {alerts.map((a) => (
              <li key={a.id} className="flex flex-wrap items-start gap-2 rounded-md border bg-soft-background px-3 py-2 text-sm">
                <Badge variant={a.audience === "patient" ? "info" : "neutral"}>{a.audience}</Badge>
                <span className="min-w-0 flex-1 text-foreground">{a.message}</span>
                {a.sms_sent && <Badge variant="success">SMS sent</Badge>}
              </li>
            ))}
          </ul>
        </section>
      </CardContent>
    </Card>
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
  const when = item.done_on ? `Done ${item.done_on}` : item.due_to ? `Due by ${item.due_to}` : item.waiting_on;

  return (
    <li className="flex flex-col gap-3 rounded-lg border bg-background p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 flex-col gap-1">
          <span className="text-sm font-medium text-foreground">{item.label}</span>
          <span className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            {when}
            {appointment && <Badge variant="info">Appointment {appointment}</Badge>}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {open && (
            <>
              <Input type="date" value={date} onChange={(e) => setDate(e.target.value)}
                className="h-8 w-auto" aria-label={`Date done for ${item.label}`} />
              <Button type="button" size="sm" onClick={() => onDone(item, date)}>Mark done</Button>
              {item.appointment_at && (
                <Button type="button" size="sm" variant="destructive" onClick={() => onNoShow(item)}>
                  No-show
                </Button>
              )}
            </>
          )}
          {bookable && (
            <Button type="button" size="sm" variant="secondary" onClick={() => setBooking((b) => !b)}>
              {booking ? "Close calendar" : item.appointment_at ? "Rebook" : "Book visit"}
            </Button>
          )}
        </div>
      </div>
      {bookable && booking && (
        <BookVisit pregnancyId={pregnancyId} item={item} onBook={async (i, d, t) => {
          await onBook(i, d, t);
          setBooking(false);
        }} />
      )}
    </li>
  );
}
