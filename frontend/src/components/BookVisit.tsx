import { format, startOfToday } from "date-fns";
import { useEffect, useState } from "react";

import { Alert, AlertDescription } from "@/components/careui/alert";
import { Button } from "@/components/careui/button";
import { Calendar } from "@/components/careui/calendar";
import { Skeleton } from "@/components/careui/skeleton";
import type { ScheduleItem } from "@/types";
import { errorMessage, request } from "@/utils/api";

interface Slot {
  start: string;
  free: boolean;
}

interface Props {
  pregnancyId: string;
  item: ScheduleItem;
  onBook: (item: ScheduleItem, date: string, time: string) => Promise<void>;
}

/** The server's wall-clock time from an ISO string such as 2026-11-08T09:15:00+05:30 → 09:15. */
function clock(iso: string): string {
  return iso.slice(11, 16);
}

/** Pick a day on the calendar, then a time from that day's slots. Taken slots cannot be picked. */
export default function BookVisit({ pregnancyId, item, onBook }: Props) {
  const [day, setDay] = useState<Date>(startOfToday());
  const [slots, setSlots] = useState<Slot[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const date = format(day, "yyyy-MM-dd");

  useEffect(() => {
    setLoading(true);
    setError("");
    request<Slot[]>(`/pregnancies/${pregnancyId}/slots/?date=${encodeURIComponent(date)}`)
      .then(setSlots)
      .catch((err) => {
        setSlots([]);
        setError(errorMessage(err));
      })
      .finally(() => setLoading(false));
  }, [pregnancyId, date]);

  async function pick(slot: Slot) {
    setBusy(true);
    setError("");
    try {
      await onBook(item, date, clock(slot.start));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const free = slots.filter((s) => s.free).length;

  return (
    <div className="flex w-full flex-col gap-4 rounded-lg border bg-soft-background p-3 md:flex-row">
      <Calendar
        selected={day}
        onSelect={(d: Date | undefined) => d && setDay(d)}
        disabled={{ before: startOfToday() }}
        className="rounded-md border bg-background"
      />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <p className="text-sm font-semibold text-foreground">
          {format(day, "EEEE, d MMMM")}
          {!loading && slots.length > 0 && (
            <span className="ml-2 font-normal text-muted-foreground">{free} free</span>
          )}
        </p>
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {loading ? (
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
            {Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="h-8" />)}
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
            {slots.map((slot) => (
              <Button key={slot.start} type="button" size="sm" variant={slot.free ? "outline" : "ghost"}
                disabled={!slot.free || busy} onClick={() => pick(slot)}
                className={slot.free ? undefined : "line-through"}
                aria-label={`${clock(slot.start)}${slot.free ? "" : " (taken)"}`}>
                {clock(slot.start)}
              </Button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
