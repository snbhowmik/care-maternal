import { useEffect, useState } from "react";

import { Alert, AlertDescription } from "@/components/careui/alert";
import { Badge } from "@/components/careui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/careui/card";
import { Skeleton } from "@/components/careui/skeleton";
import CreatePregnancy from "@/components/CreatePregnancy";
import HomeVisits from "@/components/HomeVisits";
import PregnancyCard from "@/components/PregnancyCard";
import type { Pregnancy, ScheduleItem } from "@/types";
import { errorMessage, request } from "@/utils/api";

import Page from "./Page";

/** The host renders this inside its tile grid: span the full row so it reads as its own section. */
const FULL_ROW = { gridColumn: "1 / -1" } as const;

/** Shown on CARE's staff patient home (PatientHomeQuickActions). Structural mirror of the host props. */
interface PatientHomeProps {
  patient: { id: string };
  facilityId?: string;
  className?: string;
}

/**
 * Maternal checks for this patient: enrol if needed, the history of checks already made,
 * home visits, and the full schedule with actions (mark done, book, no-show, referral).
 */
function Panel({ patient }: PatientHomeProps) {
  const [pregnancies, setPregnancies] = useState<Pregnancy[] | null>(null);
  const [history, setHistory] = useState<Record<string, ScheduleItem[]>>({});
  const [error, setError] = useState("");

  useEffect(() => {
    setPregnancies(null);
    setError("");
    request<Pregnancy[]>(`/pregnancies/?patient=${encodeURIComponent(patient.id)}`)
      .then(async (list) => {
        const entries = await Promise.all(
          list.map(async (p) => [p.id, await request<ScheduleItem[]>(`/pregnancies/${p.id}/items/`)] as const),
        );
        setHistory(Object.fromEntries(entries));
        setPregnancies(list);
      })
      .catch((err) => {
        setPregnancies([]);
        setError(errorMessage(err));
      });
  }, [patient.id]);

  return (
    <Card style={FULL_ROW}>
      <CardHeader>
        <CardTitle>Maternal checks</CardTitle>
        <CardDescription>Pregnancy to postpartum checks, visits and referrals for this patient.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        {pregnancies === null && (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-24" />
          </div>
        )}
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {pregnancies?.length === 0 && !error && (
          <>
            <p className="text-sm text-muted-foreground">No pregnancy recorded. Enrol to start the checks.</p>
            <CreatePregnancy patientId={patient.id}
              onCreated={(p) => {
                setHistory((h) => ({ ...h, [p.id]: [] }));
                setPregnancies((prev) => [p, ...(prev ?? [])]);
              }} />
          </>
        )}

        {pregnancies?.map((p) => {
          const items = (history[p.id] ?? []).filter((i) => i.state !== "waived");
          const notNeeded = (history[p.id] ?? []).length - items.length;
          const done = items
            .filter((i) => i.done_on || i.state === "elsewhere")
            .sort((a, b) => (b.done_on ?? b.resolved_on ?? "").localeCompare(a.done_on ?? a.resolved_on ?? ""));
          return (
            <div key={p.id} className="flex flex-col gap-4">
              <section className="flex flex-col gap-2" aria-label="Checks made">
                <h4 className="flex items-center gap-2 text-sm font-semibold text-foreground">
                  Checks made
                  <Badge variant={done.length ? "success" : "neutral"}>{done.length} of {items.length}</Badge>
                  {notNeeded > 0 && <span className="text-xs font-normal text-muted-foreground">{notNeeded} marked not needed</span>}
                </h4>
                {done.length > 0 && (
                  <ul className="flex flex-col divide-y rounded-lg border text-sm">
                    {done.map((i) => (
                      <li key={i.id} className="flex flex-wrap justify-between gap-2 px-3 py-2">
                        <span className="text-foreground">{i.label}</span>
                        <span className="text-muted-foreground">
                          {i.done_on ?? `Elsewhere${i.resolved_on ? `, ${i.resolved_on}` : ""}${i.resolution_note ? `: ${i.resolution_note}` : ""}`}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
              <HomeVisits pregnancyId={p.id} />
              <PregnancyCard pregnancy={p} />
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

export default function PatientMaternalPanel(props: PatientHomeProps) {
  return (
    <Page>
      <Panel {...props} />
    </Page>
  );
}
