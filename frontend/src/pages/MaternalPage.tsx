import { useEffect, useState } from "react";

import { Alert, AlertDescription } from "@/components/careui/alert";
import { Badge } from "@/components/careui/badge";
import { Card, CardContent } from "@/components/careui/card";
import { Skeleton } from "@/components/careui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/careui/table";
import type { WorklistRow } from "@/types";
import { currentFacilityId, errorMessage, request } from "@/utils/api";

/**
 * Staff worklist: every patient at this hospital with the Maternal tag, and their open checks.
 * A row opens the patient, where the checks and history are shown on the Patient Home.
 */
export default function MaternalPage() {
  const facilityId = currentFacilityId();
  const [rows, setRows] = useState<WorklistRow[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!facilityId) return;
    setError("");
    request<WorklistRow[]>(`/pregnancies/worklist/?facility=${encodeURIComponent(facilityId)}`)
      .then(setRows)
      .catch((err) => {
        setRows([]);
        setError(errorMessage(err));
      });
  }, [facilityId]);

  const open = (row: WorklistRow) => {
    window.location.href = `/facility/${facilityId}/patient/${row.patient_id}`;
  };

  return (
    <main className="flex w-full flex-col gap-6 p-4 md:p-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold text-foreground">Maternal care</h1>
        <p className="text-sm text-muted-foreground">
          Patients with the Maternal tag stay here until their last check is done. Open a patient to see their
          history and checks on the Patient Home.
        </p>
      </header>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardContent>
          {rows === null ? (
            <div className="flex flex-col gap-2">
              {Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-10" />)}
            </div>
          ) : rows.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No patients with the Maternal tag at this hospital.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Patient</TableHead>
                  <TableHead>EDD</TableHead>
                  <TableHead>Open checks</TableHead>
                  <TableHead>Overdue</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.pregnancy_id ?? row.patient_id} className="cursor-pointer"
                    tabIndex={0} onClick={() => open(row)}
                    onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && open(row)}>
                    <TableCell>
                      <a href={`/facility/${facilityId}/patient/${row.patient_id}`}
                        className="font-medium text-foreground hover:underline"
                        onClick={(e) => e.stopPropagation()}>
                        {row.patient_name}
                      </a>
                    </TableCell>
                    {row.pregnancy_id === null ? (
                      <TableCell colSpan={3}>
                        <Badge variant="neutral">Not enrolled: open to enrol</Badge>
                      </TableCell>
                    ) : (
                      <>
                        <TableCell>{row.edd}</TableCell>
                        <TableCell>{row.open_checks}</TableCell>
                        <TableCell>
                          {row.overdue_checks > 0
                            ? <Badge variant="destructive">{row.overdue_checks} overdue</Badge>
                            : <span className="text-muted-foreground">None</span>}
                        </TableCell>
                      </>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
