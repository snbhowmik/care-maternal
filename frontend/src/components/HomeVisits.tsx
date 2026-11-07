import { useCallback, useEffect, useState } from "react";

import type { HomeVisit } from "@/types";
import { errorMessage, request } from "@/utils/api";

/** ASHA home visits raised after repeated missed appointments. Closed by recording the visit. */
export default function HomeVisits({ pregnancyId }: { pregnancyId: string }) {
  const [visits, setVisits] = useState<HomeVisit[]>([]);
  const [note, setNote] = useState<Record<string, string>>({});
  const [error, setError] = useState("");

  const load = useCallback(() => {
    request<HomeVisit[]>(`/pregnancies/${pregnancyId}/home-visits/`)
      .then(setVisits)
      .catch((err) => setError(errorMessage(err)));
  }, [pregnancyId]);

  useEffect(() => {
    load();
  }, [load]);

  async function visited(v: HomeVisit) {
    setError("");
    try {
      await request(`/pregnancies/${pregnancyId}/home-visits/${v.id}/visited/`, "POST", { note: note[v.id] ?? "" });
      load();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  if (visits.length === 0) return null;

  return (
    <div className="space-y-2 rounded border border-warning-500 bg-warning-100 p-3 text-sm">
      <p className="font-semibold text-warning-700">Home visits</p>
      {error && <p className="text-danger-500">{error}</p>}
      {visits.map((v) => (
        <div key={v.id} className="space-y-1">
          <p>{v.reason}</p>
          <p className="text-secondary-700">Address: {v.address || "not recorded"}</p>
          <p className="text-secondary-700">
            Due {v.due_on}{v.assigned_to ? `, assigned to ${v.assigned_to}` : ", no ASHA worker assigned yet"}
          </p>
          {v.visited_on ? (
            <p className="text-primary-800">Visited {v.visited_on}. {v.visit_note}</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              <input value={note[v.id] ?? ""} onChange={(e) => setNote({ ...note, [v.id]: e.target.value })}
                placeholder="What was found at the home visit"
                className="flex-1 rounded border border-secondary-400 bg-white px-2 py-1" />
              <button type="button" onClick={() => visited(v)}
                className="rounded bg-primary-700 px-3 py-1 text-white">Record home visit</button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
