import { useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/careui/alert";
import { Button } from "@/components/careui/button";
import { Checkbox } from "@/components/careui/checkbox";
import { Input } from "@/components/careui/input";
import { Label } from "@/components/careui/label";
import type { Resolution, ScheduleItem } from "@/types";
import { kindLabel } from "@/types";

interface Props {
  items: ScheduleItem[];
  onResolve: (items: ScheduleItem[], resolution: Exclude<Resolution, "">, note: string) => Promise<void>;
}

/**
 * For a patient who enrols late: the checks that are already overdue. The doctor asks which ones she
 * has had elsewhere, then marks them together. Nothing here is guessed: each choice is the doctor's.
 */
export default function ReviewEarlier({ items, onResolve }: Props) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  if (items.length === 0) return null;

  const chosen = items.filter((i) => selected.has(i.spec_id));
  const allSelected = chosen.length === items.length;
  const toggle = (id: string, on: boolean) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (on) next.add(id); else next.delete(id);
      return next;
    });

  async function apply(resolution: Exclude<Resolution, "">) {
    setBusy(true);
    try {
      await onResolve(chosen, resolution, note);
      setSelected(new Set());
      setNote("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Alert variant="info">
      <AlertTitle>{items.length} earlier {items.length === 1 ? "check is" : "checks are"} overdue</AlertTitle>
      <AlertDescription>
        <p>
          Ask the patient which of these she has already had, and where. Tick them and mark them below.
          Anything you leave unticked stays open.
        </p>
        <div className="mt-3 flex flex-col gap-2">
          <Label className="flex items-center gap-2 font-semibold text-foreground">
            <Checkbox checked={allSelected}
              onCheckedChange={(on) => setSelected(on ? new Set(items.map((i) => i.spec_id)) : new Set())} />
            Select all
          </Label>
          <ul className="flex max-h-64 flex-col gap-1 overflow-y-auto rounded-md border bg-background p-2">
            {items.map((i) => (
              <li key={i.id}>
                <Label className="flex items-start gap-2 font-normal text-foreground">
                  <Checkbox className="mt-0.5" checked={selected.has(i.spec_id)}
                    onCheckedChange={(on) => toggle(i.spec_id, Boolean(on))} />
                  <span className="flex-1">{i.label}</span>
                  <span className="text-xs text-muted-foreground">{kindLabel(i.kind)} · due by {i.due_to}</span>
                </Label>
              </li>
            ))}
          </ul>
          <Input value={note} onChange={(e) => setNote(e.target.value)} className="bg-background"
            placeholder="Where it was done, or why it is not needed" aria-label="Where it was done, or why it is not needed" />
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" disabled={busy || chosen.length === 0} onClick={() => apply("elsewhere")}>
              Had these elsewhere ({chosen.length})
            </Button>
            <Button type="button" size="sm" variant="secondary"
              disabled={busy || chosen.length === 0 || !note.trim()} onClick={() => apply("not_needed")}>
              Not needed ({chosen.length})
            </Button>
          </div>
        </div>
      </AlertDescription>
    </Alert>
  );
}
