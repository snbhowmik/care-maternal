import { useState } from "react";
import type { FormEvent } from "react";

import { Alert, AlertDescription } from "@/components/careui/alert";
import { Button } from "@/components/careui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/careui/card";
import { Field, FieldGroup, FieldLabel } from "@/components/careui/field";
import { Input } from "@/components/careui/input";
import type { Pregnancy } from "@/types";
import { currentFacilityId, errorMessage, request } from "@/utils/api";

interface Props {
  patientId: string;
  onCreated: (p: Pregnancy) => void;
}

const COUNTS = [
  ["gravida", "Gravida"],
  ["para", "Para"],
  ["abortions", "Abortions"],
  ["living", "Living"],
] as const;

type Counts = Record<(typeof COUNTS)[number][0], number>;

export default function CreatePregnancy({ patientId, onCreated }: Props) {
  const [lmp, setLmp] = useState("");
  const [counts, setCounts] = useState<Counts>({ gravida: 1, para: 0, abortions: 0, living: 0 });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const created = await request<Pregnancy>("/pregnancies/", "POST", {
        patient: patientId,
        facility: currentFacilityId(),
        lmp,
        ...counts,
      });
      onCreated(created);
      setLmp("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>New pregnancy</CardTitle>
        <CardDescription>The schedule of checks starts from the last menstrual period.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit}>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="maternal-lmp">Last menstrual period (LMP)</FieldLabel>
              <Input id="maternal-lmp" type="date" required value={lmp}
                max={new Date().toISOString().slice(0, 10)}
                onChange={(e) => setLmp(e.target.value)} />
            </Field>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              {COUNTS.map(([key, label]) => (
                <Field key={key}>
                  <FieldLabel htmlFor={`maternal-${key}`}>{label}</FieldLabel>
                  <Input id={`maternal-${key}`} type="number" min={0} value={counts[key]}
                    onChange={(e) => setCounts({ ...counts, [key]: Number(e.target.value) })} />
                </Field>
              ))}
            </div>
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <div>
              <Button type="submit" disabled={busy || !lmp}>
                {busy ? "Saving…" : "Create pregnancy"}
              </Button>
            </div>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  );
}
