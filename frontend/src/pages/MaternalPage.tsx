import { useEffect, useState } from "react";

import type { WorklistRow } from "@/types";
import { currentFacilityId, errorMessage, request } from "@/utils/api";

/**
 * Staff worklist: every patient at this hospital with the Maternal tag, and their open checks.
 * A row opens the patient's home, where the checks and history are shown.
 */
export default function MaternalPage() {
  const facilityId = currentFacilityId();
  const [rows, setRows] = useState<WorklistRow[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!facilityId) return;
    setLoading(true);
    setError("");
    request<WorklistRow[]>(`/pregnancies/worklist/?facility=${encodeURIComponent(facilityId)}`)
      .then(setRows)
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }, [facilityId]);

  return (
    <main className="mx-auto max-w-3xl space-y-4 p-4 text-secondary-900">
      <h2 className="text-xl font-bold">Maternal care</h2>
      <p className="text-sm text-secondary-700">
        Patients with the Maternal tag stay here until their last check is done.
        Open a patient to see their history and checks.
      </p>

      {loading && <p className="text-sm text-secondary-600">Loading…</p>}
      {error && <p className="text-sm text-danger-500">{error}</p>}
      {!loading && !error && rows.length === 0 && (
        <p className="text-sm text-secondary-600">No patients with the Maternal tag at this hospital.</p>
      )}

      {rows.length > 0 && (
        <ul className="divide-y divide-secondary-300 rounded border border-secondary-300 bg-white">
          {rows.map((row) => (
            <li key={row.pregnancy_id}>
              <a href={`/facility/${facilityId}/patient/${row.patient_id}`}
                className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 hover:bg-secondary-100">
                <span className="font-medium">{row.patient_name}</span>
                <span className="text-sm text-secondary-700">
                  EDD {row.edd} · {row.open_checks} open
                  {row.overdue_checks > 0 && (
                    <span className="ml-2 font-semibold text-danger-500">{row.overdue_checks} overdue</span>
                  )}
                </span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
