import { useEffect, useState } from "react";

import Page from "@/components/Page";
import type { WorklistRow } from "@/types";
import { errorMessage, request } from "@/utils/api";

/** Shown on CARE's patient search page (PatientSearchActions). Structural mirror of the host props. */
interface SearchActionsProps {
  facilityId: string;
  className?: string;
}

function Link({ facilityId }: { facilityId: string }) {
  const [rows, setRows] = useState<WorklistRow[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    request<WorklistRow[]>(`/pregnancies/worklist/?facility=${encodeURIComponent(facilityId)}`)
      .then(setRows)
      .catch((err) => setError(errorMessage(err)));
  }, [facilityId]);

  if (error) return null;
  const count = rows?.length ?? 0;
  return (
    <a href={`/facility/${facilityId}/maternal`}
      className="inline-flex items-center gap-2 rounded border border-primary-700 px-3 py-2 text-sm font-medium text-primary-700 hover:bg-primary-50">
      Maternal care
      <span className="rounded bg-primary-100 px-2 py-0.5 text-xs text-primary-800">{rows === null ? "…" : count}</span>
    </a>
  );
}

export default function MaternalSearchLink({ facilityId }: SearchActionsProps) {
  return (
    <Page>
      <Link facilityId={facilityId} />
    </Page>
  );
}
