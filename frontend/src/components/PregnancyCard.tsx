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
import { EMERGENCY_SYMPTOMS, kindLabel, priorityMeta } from "@/types";
import type { Alert, ItemState, Pregnancy, Resolution, ScheduleItem } from "@/types";
import { currentFacilityId, errorMessage, request } from "@/utils/api";

import AddCheck from "./AddCheck";
import type { NewCheck } from "./AddCheck";
import BookVisit from "./BookVisit";
import CloseCheck from "./CloseCheck";
import Referrals from "./Referrals";
import ReviewEarlier from "./ReviewEarlier";

const ORDER: ItemState[] = ["overdue", "due", "upcoming", "waiting", "done", "elsewhere", "waived"];
const STATE_LABEL: Record<ItemState, string> = {
  overdue: "Overdue",
  due: "Due",
  upcoming: "Upcoming",
  waiting: "Waiting",
  done: "Done",
  elsewhere: "Done elsewhere",
  waived: "Not needed",
};
const STATE_BADGE = {
  overdue: "destructive",
  due: "warning",
  upcoming: "info",
  waiting: "neutral",
  done: "success",
  elsewhere: "success",
  waived: "neutral",
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
  const [allAlerts, setAllAlerts] = useState(false);

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

  const resolveMany = (targets: ScheduleItem[], resolution: Exclude<Resolution, "">, note: string, onDate = "") =>
    act(async () => {
      for (const item of targets) {
        await request(`/pregnancies/${pregnancy.id}/items/${item.spec_id}/resolve/`, "POST", {
          resolution,
          note,
          on_date: onDate || null,
          facility: currentFacilityId(),
        });
      }
      const what = resolution === "elsewhere" ? "done elsewhere" : "not needed";
      return targets.length === 1
        ? `Marked ${what}: ${targets[0].label}`
        : `${targets.length} checks marked ${what}.`;
    });

  const reopen = (item: ScheduleItem) =>
    act(async () => {
      await request(`/pregnancies/${pregnancy.id}/items/${item.spec_id}/reopen/`, "POST", { facility: currentFacilityId() });
      return `Reopened: ${item.label}`;
    });

  const addCheck = async (check: NewCheck) => {
    let added = false;
    await act(async () => {
      await request(`/pregnancies/${pregnancy.id}/add-check/`, "POST", {
        label: check.label,
        kind: check.kind,
        due_from: check.due_from || null,
        due_to: check.due_to || null,
        priority: check.priority,
        facility: currentFacilityId(),
      });
      added = true;
      return `Added for this patient: ${check.label}`;
    });
    return added;
  };

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

        <ReviewEarlier items={items.filter((i) => i.state === "overdue")}
          onResolve={(targets, resolution, note) => resolveMany(targets, resolution, note)} />

        <section className="flex flex-col gap-4" aria-label="Schedule of checks">
          {grouped.filter((g) => g.rows.length).map((g) => (
            // Only what needs action is open; the rest is one tap away, so a long schedule stays readable.
            <details key={g.state} open={g.state === "overdue" || g.state === "due"} className="flex flex-col">
              <summary className="flex cursor-pointer items-center gap-2 text-sm font-semibold text-foreground">
                {STATE_LABEL[g.state]}
                <Badge variant={STATE_BADGE[g.state]}>{g.rows.length}</Badge>
              </summary>
              <ul className="mt-2 flex flex-col gap-2">
                {g.rows.map((item) => (
                  <ItemRow key={item.id} item={item} pregnancyId={pregnancy.id}
                    onDone={markDone} onBook={bookVisit} onNoShow={noShow}
                    onResolve={(i, resolution, note, onDate) => resolveMany([i], resolution, note, onDate)}
                    onReopen={reopen} />
                ))}
              </ul>
            </details>
          ))}
          <AddCheck onAdd={addCheck} />
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
            {(allAlerts ? alerts : alerts.slice(0, 5)).map((a) => (
              <li key={a.id} className="flex flex-wrap items-start gap-2 rounded-md border bg-soft-background px-3 py-2 text-sm">
                <Badge variant={a.audience === "patient" ? "info" : "neutral"}>{a.audience}</Badge>
                <span className="min-w-0 flex-1 text-foreground">{a.message}</span>
                {a.sms_sent && <Badge variant="success">SMS sent</Badge>}
              </li>
            ))}
          </ul>
          {alerts.length > 5 && (
            <div>
              <Button type="button" size="sm" variant="ghost" onClick={() => setAllAlerts((v) => !v)}>
                {allAlerts ? "Show only the latest 5" : `Show all ${alerts.length} alerts`}
              </Button>
            </div>
          )}
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
  onResolve,
  onReopen,
}: {
  item: ScheduleItem;
  pregnancyId: string;
  onDone: (i: ScheduleItem, d: string) => void;
  onBook: (i: ScheduleItem, d: string, time: string) => Promise<void>;
  onNoShow: (i: ScheduleItem) => void;
  onResolve: (i: ScheduleItem, resolution: Exclude<Resolution, "">, note: string, onDate: string) => Promise<void>;
  onReopen: (i: ScheduleItem) => void;
}) {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [booking, setBooking] = useState(false);
  const [closing, setClosing] = useState(false);
  const resolved = item.state === "elsewhere" || item.state === "waived";
  const open = item.state !== "done" && item.state !== "waiting" && !resolved;
  const bookable = item.state !== "done" && !resolved;
  const appointment = item.appointment_at
    ? new Date(item.appointment_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
    : null;
  const when = item.done_on
    ? `Done ${item.done_on}`
    : item.state === "elsewhere"
      ? `Done elsewhere${item.resolved_on ? ` on ${item.resolved_on}` : ""}${item.resolution_note ? `: ${item.resolution_note}` : ""}`
      : item.state === "waived"
        ? `Not needed: ${item.resolution_note}`
        : item.due_to ? `Due by ${item.due_to}` : item.waiting_on;

  return (
    <li className="flex flex-col gap-3 rounded-lg border bg-background p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 flex-col gap-1">
          <span className="text-sm font-medium text-foreground">
            {item.label}
            <Badge variant="neutral" className="ml-2 align-middle">{kindLabel(item.kind)}</Badge>
            {item.priority !== "medium" && (
              <Badge variant={priorityMeta(item.priority).badge} className="ml-1 align-middle">
                {priorityMeta(item.priority).label}
              </Badge>
            )}
          </span>
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
          {(open || item.state === "waiting") && !item.appointment_at && (
            <Button type="button" size="sm" variant="ghost" onClick={() => setClosing((c) => !c)}>
              {closing ? "Cancel" : "Not done here"}
            </Button>
          )}
          {resolved && (
            <Button type="button" size="sm" variant="ghost" onClick={() => onReopen(item)}>Reopen</Button>
          )}
        </div>
      </div>
      {closing && (
        <CloseCheck onResolve={async (resolution, note, onDate) => {
          await onResolve(item, resolution, note, onDate);
          setClosing(false);
        }} />
      )}
      {bookable && booking && (
        <BookVisit pregnancyId={pregnancyId} item={item} onBook={async (i, d, t) => {
          await onBook(i, d, t);
          setBooking(false);
        }} />
      )}
    </li>
  );
}
