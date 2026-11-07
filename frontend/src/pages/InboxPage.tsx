import { useCallback, useEffect, useState } from "react";

import { Alert, AlertDescription } from "@/components/careui/alert";
import { Badge } from "@/components/careui/badge";
import { Button } from "@/components/careui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/careui/card";
import { Field, FieldLabel } from "@/components/careui/field";
import { Skeleton } from "@/components/careui/skeleton";
import { Textarea } from "@/components/careui/textarea";
import type { Referral } from "@/types";
import { currentFacilityId, errorMessage, request } from "@/utils/api";

const STATUS_BADGE: Record<string, "info" | "success" | "neutral"> = {
  received: "info",
  acknowledged: "success",
  examined: "success",
};

/** Receiving hospital: referrals sent to this hospital, to acknowledge and examine. */
export default function InboxPage() {
  const [items, setItems] = useState<Referral[] | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [note, setNote] = useState<Record<string, string>>({});

  const reload = useCallback(async () => {
    try {
      setItems(await request<Referral[]>("/referrals/inbox/"));
    } catch (err) {
      setItems([]);
      setError(errorMessage(err));
    }
  }, []);

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

  return (
    <main className="flex w-full flex-col gap-6 p-4 md:p-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold text-foreground">Referrals received</h1>
        <p className="text-sm text-muted-foreground">
          Acknowledge each referral, then record the examination. The referring hospital is told at each step.
        </p>
      </header>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {notice && (
        <Alert variant="success">
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      )}

      {items === null && (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
        </div>
      )}
      {items?.length === 0 && !error && (
        <p className="text-sm text-muted-foreground">No referrals received.</p>
      )}

      {items?.map((r) => {
        const draft = note[r.id] ?? "";
        const open = r.status === "received" || r.status === "acknowledged";
        return (
          <Card key={r.id}>
            <CardHeader>
              <CardTitle>{r.patient_name}</CardTitle>
              <CardDescription>From {r.from_facility}</CardDescription>
              <CardAction>
                <Badge variant={STATUS_BADGE[r.status] ?? "neutral"}>{r.status.replace(/_/g, " ")}</Badge>
              </CardAction>
            </CardHeader>
            <CardContent className="flex flex-col gap-2 text-sm">
              <p className="text-foreground">Reason: {r.reason}</p>
              <p className="text-muted-foreground">Consent: {r.consent_by || "not recorded"}</p>
              {r.outcome_note && <p className="text-muted-foreground">Outcome: {r.outcome_note}</p>}
              {open && (
                <Field className="mt-2">
                  <FieldLabel htmlFor={`exam-${r.id}`}>Examination findings and plan</FieldLabel>
                  <Textarea id={`exam-${r.id}`} value={draft}
                    onChange={(e) => setNote({ ...note, [r.id]: e.target.value })} />
                </Field>
              )}
            </CardContent>
            {open && (
              <CardFooter className="flex flex-wrap gap-2">
                {r.status === "received" && (
                  <Button type="button" size="sm" onClick={() => act("Acknowledged. The referring hospital is told.", () =>
                    request(`/referrals/${r.id}/acknowledge/`, "POST", { facility: currentFacilityId() }))}>
                    Acknowledge
                  </Button>
                )}
                <Button type="button" size="sm" variant="secondary" disabled={!draft.trim()}
                  onClick={() => act("Examination recorded. The referring hospital is told.", () =>
                    request(`/referrals/${r.id}/examined/`, "POST", { note: draft, facility: currentFacilityId() }))}>
                  Record examination
                </Button>
              </CardFooter>
            )}
          </Card>
        );
      })}
    </main>
  );
}
