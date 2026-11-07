import { useEffect, useState } from "react";

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

/** Calendar date, then a time from that day's slots. Taken slots cannot be picked. */
export default function BookVisit({ pregnancyId, item, onBook }: Props) {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [slots, setSlots] = useState<Slot[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!date) return;
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

  return (
    <div className="w-full space-y-2 rounded border border-secondary-300 bg-secondary-50 p-2">
      <label className="flex flex-wrap items-center gap-2 text-sm">
        Date
        <input type="date" value={date} min={new Date().toISOString().slice(0, 10)}
          onChange={(e) => setDate(e.target.value)}
          className="rounded border border-secondary-400 px-2 py-1" />
      </label>

      {loading && <p className="text-sm text-secondary-600">Loading times…</p>}
      {error && <p className="text-sm text-danger-500">{error}</p>}

      {!loading && slots.length > 0 && (
        <div className="grid grid-cols-3 gap-1 sm:grid-cols-6">
          {slots.map((slot) => (
            <button key={slot.start} type="button" disabled={!slot.free || busy}
              onClick={() => pick(slot)}
              className={`rounded px-2 py-1 text-sm ${slot.free
                ? "border border-primary-700 text-primary-700 hover:bg-primary-50"
                : "cursor-not-allowed bg-secondary-200 text-secondary-500 line-through"}`}>
              {clock(slot.start)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
