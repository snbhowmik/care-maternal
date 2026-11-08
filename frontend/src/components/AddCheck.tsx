import { useState } from "react";
import type { FormEvent } from "react";

import { Button } from "@/components/careui/button";
import { Field, FieldLabel } from "@/components/careui/field";
import { Input } from "@/components/careui/input";
import { CHECK_KINDS } from "@/types";

export interface NewCheck {
  label: string;
  kind: string;
  due_from: string;
  due_to: string;
}

/** A check for this patient only, for example a repeat scan the doctor wants. */
export default function AddCheck({ onAdd }: { onAdd: (check: NewCheck) => Promise<boolean> }) {
  const [open, setOpen] = useState(false);
  const [label, setLabel] = useState("");
  const [kind, setKind] = useState("visit_check");
  const [dueFrom, setDueFrom] = useState("");
  const [dueTo, setDueTo] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const ok = await onAdd({ label, kind, due_from: dueFrom, due_to: dueTo });
      if (ok) {
        setLabel(""); setDueFrom(""); setDueTo(""); setOpen(false);
      }
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <div>
        <Button type="button" size="sm" variant="tertiary" onClick={() => setOpen(true)}>
          Add a check for this patient
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3 rounded-lg border bg-soft-background p-3">
      <Field>
        <FieldLabel htmlFor="add-check-label">What needs to be checked?</FieldLabel>
        <Input id="add-check-label" value={label} onChange={(e) => setLabel(e.target.value)} required />
      </Field>
      <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Kind of check">
        {CHECK_KINDS.map((k) => (
          <Button key={k.value} type="button" size="sm" role="radio" aria-checked={kind === k.value}
            variant={kind === k.value ? "default" : "outline"} onClick={() => setKind(k.value)}>
            {k.label}
          </Button>
        ))}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field>
          <FieldLabel htmlFor="add-check-from">Due from (optional)</FieldLabel>
          <Input id="add-check-from" type="date" value={dueFrom} onChange={(e) => setDueFrom(e.target.value)} />
        </Field>
        <Field>
          <FieldLabel htmlFor="add-check-to">Due by (optional)</FieldLabel>
          <Input id="add-check-to" type="date" value={dueTo} min={dueFrom || undefined}
            onChange={(e) => setDueTo(e.target.value)} />
        </Field>
      </div>
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={busy || !label.trim()}>Add check</Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
      </div>
    </form>
  );
}
