import { useEffect, useState } from "react";

import CreatePregnancy from "@/components/CreatePregnancy";
import HomeVisits from "@/components/HomeVisits";
import PregnancyCard from "@/components/PregnancyCard";
import type { Pregnancy, ScheduleItem } from "@/types";
import { errorMessage, request } from "@/utils/api";

import Page from "./Page";

/** Shown on CARE's staff patient home (PatientHomeQuickActions). Structural mirror of the host props. */
interface PatientHomeProps {
  patient: { id: string };
  facilityId?: string;
  className?: string;
}

/**
 * Maternal checks for this patient: enrol if needed, the history of checks already made,
 * and the full schedule with actions (mark done, book, referral).
 */
function Panel({ patient }: PatientHomeProps) {
  const [pregnancies, setPregnancies] = useState<Pregnancy[]>([]);
  const [history, setHistory] = useState<Record<string, ScheduleItem[]>>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setError("");
    request<Pregnancy[]>(`/pregnancies/?patient=${encodeURIComponent(patient.id)}`)
      .then(async (list) => {
        setPregnancies(list);
        const entries = await Promise.all(
          list.map(async (p) => [p.id, await request<ScheduleItem[]>(`/pregnancies/${p.id}/items/`)] as const),
        );
        setHistory(Object.fromEntries(entries));
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }, [patient.id]);

  if (loading) return <p className="text-sm text-secondary-600">Loading maternal checks…</p>;
  if (error) return <p className="text-sm text-danger-500">{error}</p>;

  return (
    <section className="care-maternal-container space-y-3 rounded border border-secondary-300 bg-white p-4">
      <h3 className="font-semibold">Maternal checks</h3>

      {pregnancies.length === 0 && (
        <>
          <p className="text-sm text-secondary-700">No pregnancy recorded. Enrol to start the checks.</p>
          <CreatePregnancy patientId={patient.id}
            onCreated={(p) => setPregnancies((prev) => [p, ...prev])} />
        </>
      )}

      {pregnancies.map((p) => {
        const items = history[p.id] ?? [];
        const done = items.filter((i) => i.done_on).sort((a, b) => (b.done_on ?? "").localeCompare(a.done_on ?? ""));
        return (
          <div key={p.id} className="space-y-2">
            <p className="text-sm text-secondary-700">
              Checks made: {done.length} of {items.length}
            </p>
            {done.length > 0 && (
              <ul className="text-sm text-secondary-800">
                {done.map((i) => (
                  <li key={i.id}>{i.label}: {i.done_on}</li>
                ))}
              </ul>
            )}
            <HomeVisits pregnancyId={p.id} />
            <PregnancyCard pregnancy={p} />
          </div>
        );
      })}
    </section>
  );
}

/** The host renders this inside its own page, so the plugin styles are scoped here. */
export default function PatientMaternalPanel(props: PatientHomeProps) {
  return (
    <Page>
      <Panel {...props} />
    </Page>
  );
}
