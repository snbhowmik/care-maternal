import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import { Alert, AlertDescription } from "@/components/careui/alert";
import { Badge } from "@/components/careui/badge";
import { Button } from "@/components/careui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/careui/card";
import { Checkbox } from "@/components/careui/checkbox";
import { Field, FieldLabel } from "@/components/careui/field";
import { Input } from "@/components/careui/input";
import { Label } from "@/components/careui/label";
import { Skeleton } from "@/components/careui/skeleton";
import { Switch } from "@/components/careui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/careui/table";
import { CHECK_KINDS, PRIORITIES, kindLabel, priorityMeta } from "@/types";
import type { CheckTemplate, Priority } from "@/types";

import PriorityPicker from "@/components/PriorityPicker";
import { errorMessage, request } from "@/utils/api";

type Mode = "age" | "after" | "manual";

const MODES: { value: Mode; label: string; help: string }[] = [
  { value: "age", label: "By weeks of pregnancy", help: "Due between two gestational ages, counted from the LMP." },
  { value: "after", label: "After another check", help: "Due a set number of days after another check is recorded." },
  { value: "manual", label: "Doctor sets the date", help: "No automatic date; the doctor fills it in for each patient." },
];

const NATIVE_SELECT =
  "h-9 w-full rounded-md border bg-background px-3 text-sm text-foreground outline-none focus-visible:ring-3 focus-visible:ring-ring/50";

function whenText(t: CheckTemplate, byId: Record<string, CheckTemplate>): string {
  if (t.relative_to) {
    const base = byId[t.relative_to]?.label ?? t.relative_to;
    return `${t.after_days} days after "${base}"${t.to_weeks ? `, by ${t.to_weeks} weeks` : ""}`;
  }
  if (!t.from_weeks) return t.waiting_note || "Doctor sets the date";
  return `${t.from_weeks} to ${t.to_weeks} weeks`;
}

function modeOf(t?: CheckTemplate): Mode {
  if (!t) return "age";
  if (t.relative_to) return "after";
  return t.from_weeks ? "age" : "manual";
}

function CheckForm({ initial, templates, saveLabel, onSave, onCancel }: {
  initial?: CheckTemplate;
  templates: CheckTemplate[];
  saveLabel: string;
  onSave: (payload: Partial<CheckTemplate>) => Promise<boolean>;
  onCancel?: () => void;
}) {
  const [label, setLabel] = useState(initial?.label ?? "");
  const [kind, setKind] = useState(initial?.kind ?? "visit_check");
  const [mode, setMode] = useState<Mode>(modeOf(initial));
  const [from, setFrom] = useState(initial?.from_weeks ?? "");
  const [to, setTo] = useState(initial?.to_weeks ?? "");
  const [relativeTo, setRelativeTo] = useState(initial?.relative_to ?? "");
  const [afterDays, setAfterDays] = useState(String(initial?.after_days ?? ""));
  const [note, setNote] = useState(initial?.waiting_note ?? "");
  const [priority, setPriority] = useState<Priority>(initial?.priority ?? "medium");
  const [busy, setBusy] = useState(false);
  const others = templates.filter((t) => t.id !== initial?.id && t.active);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    const payload: Partial<CheckTemplate> = { label, kind, priority, waiting_note: mode === "manual" ? note : "" };
    if (mode === "age") Object.assign(payload, { from_weeks: from, to_weeks: to, relative_to: "", after_days: null });
    if (mode === "after") Object.assign(payload, { from_weeks: "", to_weeks: to, relative_to: relativeTo, after_days: Number(afterDays) });
    if (mode === "manual") Object.assign(payload, { from_weeks: "", to_weeks: "", relative_to: "", after_days: null });
    try {
      const ok = await onSave(payload);
      if (ok && !initial) { setLabel(""); setFrom(""); setTo(""); setRelativeTo(""); setAfterDays(""); setNote(""); }
    } finally {
      setBusy(false);
    }
  }

  const ready = label.trim() && (mode === "manual" || (mode === "age" ? from.trim() && to.trim() : relativeTo && afterDays));

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <Field>
        <FieldLabel htmlFor="check-label">What is checked?</FieldLabel>
        <Input id="check-label" value={label} onChange={(e) => setLabel(e.target.value)}
          placeholder="For example: Haemoglobin test" required />
      </Field>
      <Field>
        <FieldLabel>Kind</FieldLabel>
        <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Kind of check">
          {CHECK_KINDS.map((k) => (
            <Button key={k.value} type="button" size="sm" role="radio" aria-checked={kind === k.value}
              variant={kind === k.value ? "default" : "outline"} onClick={() => setKind(k.value)}>
              {k.label}
            </Button>
          ))}
          {!CHECK_KINDS.some((k) => k.value === kind) && <Badge variant="neutral">{kindLabel(kind)}</Badge>}
        </div>
      </Field>
      <PriorityPicker value={priority} onChange={setPriority} />
      <Field>
        <FieldLabel>When is it due?</FieldLabel>
        <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="When is it due">
          {MODES.map((m) => (
            <Button key={m.value} type="button" size="sm" role="radio" aria-checked={mode === m.value}
              variant={mode === m.value ? "default" : "outline"} onClick={() => setMode(m.value)}>
              {m.label}
            </Button>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">{MODES.find((m) => m.value === mode)?.help}</p>
      </Field>

      {mode === "age" && (
        <div className="grid gap-3 sm:grid-cols-2">
          <Field>
            <FieldLabel htmlFor="check-from">From (weeks)</FieldLabel>
            <Input id="check-from" value={from} onChange={(e) => setFrom(e.target.value)} placeholder="11 or 13+6" />
          </Field>
          <Field>
            <FieldLabel htmlFor="check-to">To (weeks)</FieldLabel>
            <Input id="check-to" value={to} onChange={(e) => setTo(e.target.value)} placeholder="14 or 27+6" />
          </Field>
        </div>
      )}
      {mode === "after" && (
        <div className="grid gap-3 sm:grid-cols-3">
          <Field className="sm:col-span-3">
            <FieldLabel htmlFor="check-after">After which check?</FieldLabel>
            <select id="check-after" className={NATIVE_SELECT} value={relativeTo} onChange={(e) => setRelativeTo(e.target.value)}>
              <option value="">Choose a check</option>
              {others.map((t) => <option key={t.id} value={t.spec_id}>{t.label}</option>)}
            </select>
          </Field>
          <Field>
            <FieldLabel htmlFor="check-days">Days after</FieldLabel>
            <Input id="check-days" type="number" min={0} value={afterDays} onChange={(e) => setAfterDays(e.target.value)} />
          </Field>
          <Field>
            <FieldLabel htmlFor="check-by">Due by (weeks, optional)</FieldLabel>
            <Input id="check-by" value={to} onChange={(e) => setTo(e.target.value)} placeholder="40" />
          </Field>
        </div>
      )}
      {mode === "manual" && (
        <Field>
          <FieldLabel htmlFor="check-note">Note shown while there is no date (optional)</FieldLabel>
          <Input id="check-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="For example: doctor decides" />
        </Field>
      )}

      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={busy || !ready}>{saveLabel}</Button>
        {onCancel && <Button type="button" size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>}
      </div>
    </form>
  );
}

/**
 * The hospital's check list. Doctors and facility admins add, change and retire checks here, with no code.
 * Changes apply to patients enrolled from now on. A single patient's checks are changed on that patient.
 */
export default function CheckListPage() {
  const [templates, setTemplates] = useState<CheckTemplate[] | null>(null);
  const [canEdit, setCanEdit] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [showRetired, setShowRetired] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await request<{ can_edit: boolean; results: CheckTemplate[] }>("/check-templates/");
      setTemplates(r.results);
      setCanEdit(r.can_edit);
    } catch (err) {
      setTemplates([]);
      setError(errorMessage(err));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const byId = useMemo(
    () => Object.fromEntries((templates ?? []).map((t) => [t.spec_id, t])),
    [templates],
  );

  async function save(call: () => Promise<unknown>, message: string): Promise<boolean> {
    setError("");
    setNotice("");
    try {
      await call();
      setNotice(message);
      await load();
      return true;
    } catch (err) {
      setError(errorMessage(err));
      return false;
    }
  }

  const visible = (templates ?? []).filter(
    (t) => (showRetired || t.active) && t.label.toLowerCase().includes(search.trim().toLowerCase()),
  );

  return (
    <main className="flex w-full flex-col gap-6 p-4 md:p-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold text-foreground">Maternal check list</h1>
        <p className="text-sm text-muted-foreground">
          The checks created for every new pregnancy. Changes apply to patients enrolled from now on; patients
          already enrolled keep their checks. To change one patient's checks, open that patient.
        </p>
      </header>

      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
      {notice && <Alert variant="success"><AlertDescription>{notice}</AlertDescription></Alert>}
      {templates !== null && !canEdit && (
        <Alert variant="info">
          <AlertDescription>You can read this list. Ask a doctor or a facility admin to change it.</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>What priority does</CardTitle>
          <CardDescription>
            Priority decides who is reminded and how often. The people reminded are everyone on duty (doctors,
            nurses and the other roles in the reminder list) and the patient.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="flex flex-col gap-2 text-sm">
            {PRIORITIES.map((p) => (
              <li key={p.value} className="flex flex-wrap items-start gap-2">
                <Badge variant={p.badge}>{p.label}</Badge>
                <span className="min-w-0 flex-1 text-foreground">{p.rule}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-muted-foreground">
            Reminders go out between 08:00 and 20:00. A patient with a booked appointment for the check is not
            reminded to come. These timings are defaults and still need clinician review.
          </p>
        </CardContent>
      </Card>

      {canEdit && templates !== null && (
        <Card>
          <CardHeader>
            <CardTitle>Add a check</CardTitle>
            <CardDescription>It will be created for every pregnancy enrolled from now on.</CardDescription>
          </CardHeader>
          <CardContent>
            <CheckForm templates={templates} saveLabel="Add to the list"
              onSave={(payload) => save(() => request("/check-templates/", "POST", payload), `Added: ${payload.label}`)} />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Checks</CardTitle>
          <CardDescription>
            Turn a check off to stop creating it for new patients. It is never deleted, so past records stay intact.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-4">
            <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search checks"
              aria-label="Search checks" className="max-w-sm" />
            <Label className="flex items-center gap-2 font-normal">
              <Checkbox checked={showRetired} onCheckedChange={(on) => setShowRetired(Boolean(on))} />
              Show turned-off checks
            </Label>
          </div>

          {templates === null ? (
            <div className="flex flex-col gap-2">{Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-10" />)}</div>
          ) : visible.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">No checks match.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Check</TableHead>
                  <TableHead>Kind</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>When</TableHead>
                  <TableHead>On</TableHead>
                  <TableHead><span className="sr-only">Edit</span></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {visible.map((t) => (
                  <Fragment key={t.id}>
                    <TableRow className={t.active ? undefined : "opacity-60"}>
                      <TableCell className="whitespace-normal">
                        {t.label}
                        {t.source === "custom" && <Badge variant="info" className="ml-2">Added here</Badge>}
                      </TableCell>
                      <TableCell><Badge variant="neutral">{kindLabel(t.kind)}</Badge></TableCell>
                      <TableCell><Badge variant={priorityMeta(t.priority).badge}>{priorityMeta(t.priority).label}</Badge></TableCell>
                      <TableCell className="whitespace-normal text-muted-foreground">{whenText(t, byId)}</TableCell>
                      <TableCell>
                        <Switch checked={t.active} disabled={!canEdit} aria-label={`${t.label}: create for new patients`}
                          onCheckedChange={(on) => save(
                            () => request(`/check-templates/${t.id}/`, "PATCH", { active: on }),
                            on ? `Turned on: ${t.label}` : `Turned off: ${t.label}`,
                          )} />
                      </TableCell>
                      <TableCell>
                        {canEdit && (
                          <Button type="button" size="sm" variant="ghost" onClick={() => setEditing(editing === t.id ? null : t.id)}>
                            {editing === t.id ? "Close" : "Edit"}
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                    {editing === t.id && (
                      <TableRow>
                        <TableCell colSpan={6} className="bg-soft-background">
                          <CheckForm initial={t} templates={templates ?? []} saveLabel="Save changes"
                            onCancel={() => setEditing(null)}
                            onSave={async (payload) => {
                              const ok = await save(() => request(`/check-templates/${t.id}/`, "PATCH", payload), `Saved: ${payload.label}`);
                              if (ok) setEditing(null);
                              return ok;
                            }} />
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
