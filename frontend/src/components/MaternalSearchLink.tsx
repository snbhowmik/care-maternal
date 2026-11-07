import { useEffect, useState } from "react";

import { Badge } from "@/components/careui/badge";
import { buttonVariants } from "@/components/careui/button";
import Page from "@/components/Page";
import type { WorklistRow } from "@/types";
import { request } from "@/utils/api";

/** Shown on CARE's patient search page (PatientSearchActions). Structural mirror of the host props. */
interface SearchActionsProps {
  facilityId: string;
  className?: string;
}

function MaternalLink({ facilityId }: { facilityId: string }) {
  const [count, setCount] = useState<number | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    request<WorklistRow[]>(`/pregnancies/worklist/?facility=${encodeURIComponent(facilityId)}`)
      .then((rows) => setCount(rows.length))
      .catch(() => setFailed(true));
  }, [facilityId]);

  if (failed) return null;
  return (
    <a href={`/facility/${facilityId}/maternal`} className={buttonVariants({ variant: "secondary", size: "sm" })}>
      Maternal care
      <Badge variant="primary">{count ?? "…"}</Badge>
    </a>
  );
}

export default function MaternalSearchLink({ facilityId }: SearchActionsProps) {
  return (
    <Page>
      <MaternalLink facilityId={facilityId} />
    </Page>
  );
}
