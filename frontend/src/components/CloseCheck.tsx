import { useId, useState } from "react";

import { Button } from "@/components/careui/button";
import { Input } from "@/components/careui/input";
import type { Resolution } from "@/types";

export type ResolveFn = (resolution: Exclude<Resolution, "">, note: string, onDate: string) => Promise<void>;

/**
 * Close one check without doing it here: the patient had it elsewhere, or it is not needed for her.
 * The doctor decides while talking to the patient; the reason is saved with the check.
 */
export default function CloseCheck({ onResolve }: { onResolve: ResolveFn }) {
  const [choice, setChoice] = useState<Exclude<Resolution, ""> | null>(null);
  const [note, setNote] = useState("");
  const [onDate, setOnDate] = useState("");
  const [busy, setBusy] = useState(false);
  const uid = useId();

  async function save() {
    if (!choice) return;
    setBusy(true);
    try {
      await onResolve(choice, note, choice === "elsewhere" ? onDate : "");
      setChoice(null);
      setNote("");
      setOnDate("");
    } finally {
      setBusy(false);
    }
  }

  if (!choice) {
    return (
      <div className="flex flex-wrap gap-2">
        <Button type="button" size="sm" variant="tertiary" onClick={() => setChoice("elsewhere")}>
          Had it elsewhere
        </Button>
        <Button type="button" size="sm" variant="tertiary" onClick={() => setChoice("not_needed")}>
          Not needed
        </Button>
      </div>
    );
  }

  const needsReason = choice === "not_needed";
  return (
    <div className="flex flex-wrap items-end gap-2 rounded-md border bg-soft-background p-2">
      <div className="flex min-w-48 flex-1 flex-col gap-1">
        <label className="text-xs text-muted-foreground" htmlFor={`${uid}-note`}>
          {needsReason ? "Why is it not needed for this patient?" : "Where was it done? (optional)"}
        </label>
        <Input id={`${uid}-note`} value={note} onChange={(e) => setNote(e.target.value)} className="h-8" />
      </div>
      {!needsReason && (
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground" htmlFor={`${uid}-date`}>When? (optional)</label>
          <Input id={`${uid}-date`} type="date" value={onDate} max={new Date().toISOString().slice(0, 10)}
            onChange={(e) => setOnDate(e.target.value)} className="h-8 w-auto" />
        </div>
      )}
      <Button type="button" size="sm" disabled={busy || (needsReason && !note.trim())} onClick={save}>
        {needsReason ? "Mark not needed" : "Mark done elsewhere"}
      </Button>
      <Button type="button" size="sm" variant="ghost" onClick={() => setChoice(null)}>Cancel</Button>
    </div>
  );
}
