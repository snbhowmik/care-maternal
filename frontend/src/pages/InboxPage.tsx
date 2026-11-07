import { useCallback, useEffect, useState } from "react";

import type { Referral } from "@/types";
import { currentFacilityId, errorMessage, request } from "@/utils/api";

/** Receiving hospital: referrals sent to this hospital, to acknowledge and examine. */
export default function InboxPage() {
  const [items, setItems] = useState<Referral[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [note, setNote] = useState<Record<string, string>>({});

  const reload = useCallback(async () => {
    try {
      setItems(await request<Referral[]>("/referrals/inbox/"));
    } catch (err) {
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
    <main className="mx-auto max-w-3xl space-y-4 p-4 text-secondary-900">
      <h2 className="text-xl font-bold">Referrals received</h2>
      {error && <p className="text-sm text-danger-500">{error}</p>}
      {notice && <p className="text-sm text-primary-700">{notice}</p>}
      {items.length === 0 && <p className="text-sm text-secondary-600">No referrals received.</p>}
      {items.map((r) => (
        <section key={r.id} className="space-y-2 rounded border border-secondary-400 bg-white p-3 text-sm">
          <div className="flex flex-wrap justify-between gap-2">
            <span className="font-semibold">{r.patient_name}</span>
            <span className="rounded bg-secondary-100 px-2 py-0.5">{r.status.replace(/_/g, " ")}</span>
          </div>
          <p>From {r.from_facility}. Reason: {r.reason}</p>
          <p className="text-secondary-700">Consent: {r.consent_by || "not recorded"}</p>
          {r.status === "received" && (
            <button type="button" onClick={() => act("Acknowledged. The referring hospital is told.", () =>
              request(`/referrals/${r.id}/acknowledge/`, "POST", { facility: currentFacilityId() }))}
              className="rounded bg-primary-700 px-3 py-1 text-white">Acknowledge</button>
          )}
          {(r.status === "received" || r.status === "acknowledged") && (
            <div className="flex flex-wrap gap-2">
              <input value={note[r.id] ?? ""} onChange={(e) => setNote({ ...note, [r.id]: e.target.value })}
                placeholder="Examination findings and plan" className="flex-1 rounded border border-secondary-400 px-2 py-1" />
              <button type="button" disabled={!(note[r.id] ?? "").trim()}
                onClick={() => act("Examination recorded. The referring hospital is told.", () =>
                  request(`/referrals/${r.id}/examined/`, "POST", { note: note[r.id], facility: currentFacilityId() }))}
                className="rounded border border-primary-700 px-3 py-1 text-primary-700">Record examination</button>
            </div>
          )}
          {r.outcome_note && <p className="text-secondary-700">Outcome: {r.outcome_note}</p>}
        </section>
      ))}
    </main>
  );
}
