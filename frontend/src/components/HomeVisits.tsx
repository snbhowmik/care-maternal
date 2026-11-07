import { useCallback, useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/careui/alert";
import { Badge } from "@/components/careui/badge";
import { Button } from "@/components/careui/button";
import { Textarea } from "@/components/careui/textarea";
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

  if (visits.length === 0 && !error) return null;

  return (
    <Alert variant="warning">
      <AlertTitle>Home visits</AlertTitle>
      <AlertDescription>
        <div className="mt-2 flex flex-col gap-3">
          {error && <p className="text-destructive">{error}</p>}
          {visits.map((v) => (
            <div key={v.id} className="flex flex-col gap-2 rounded-md border bg-background p-3 text-foreground">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-medium">{v.reason}</span>
                {v.visited_on
                  ? <Badge variant="success">Visited {v.visited_on}</Badge>
                  : <Badge variant="warning">Due {v.due_on}</Badge>}
              </div>
              <p className="text-sm text-muted-foreground">Address: {v.address || "not recorded"}</p>
              <p className="text-sm text-muted-foreground">
                {v.assigned_to ? `Assigned to ${v.assigned_to}` : "No ASHA worker assigned yet"}
              </p>
              {v.visited_on ? (
                v.visit_note && <p className="text-sm">{v.visit_note}</p>
              ) : (
                <>
                  <Textarea value={note[v.id] ?? ""} onChange={(e) => setNote({ ...note, [v.id]: e.target.value })}
                    placeholder="What was found at the home visit" aria-label="What was found at the home visit" />
                  <div>
                    <Button type="button" size="sm" onClick={() => visited(v)}>Record home visit</Button>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      </AlertDescription>
    </Alert>
  );
}
