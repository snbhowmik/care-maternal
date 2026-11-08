import { useCallback, useEffect, useState } from "react";

import { Alert, AlertDescription } from "@/components/careui/alert";
import { Badge } from "@/components/careui/badge";
import { Button } from "@/components/careui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/careui/card";
import type { Reminder } from "@/types";
import { currentFacilityId, errorMessage, request } from "@/utils/api";

/** The signed-in person's own reminders: checks that are due, for patients they look after. */
export default function RemindersCard() {
  const facilityId = currentFacilityId();
  const [items, setItems] = useState<Reminder[] | null>(null);
  const [error, setError] = useState("");
  const [all, setAll] = useState(false);

  const load = useCallback(() => {
    request<Reminder[]>("/reminders/").then(setItems).catch((err) => {
      setItems([]);
      setError(errorMessage(err));
    });
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function seen(r: Reminder) {
    try {
      await request(`/reminders/${r.id}/acknowledge/`, "POST");
      load();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  const unseen = (items ?? []).filter((r) => !r.acknowledged).length;
  const shown = all ? items ?? [] : (items ?? []).slice(0, 8);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Your reminders
          {unseen > 0 && <Badge variant="destructive">{unseen} new</Badge>}
        </CardTitle>
        <CardDescription>Checks that are due, sent to you while you are on duty.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
        {items !== null && items.length === 0 && !error && (
          <p className="text-sm text-muted-foreground">No reminders yet.</p>
        )}
        <ul className="flex flex-col gap-2">
          {shown.map((r) => (
            <li key={r.id} className={`flex flex-wrap items-start gap-2 rounded-md border p-3 text-sm ${r.acknowledged ? "bg-background" : "bg-soft-background"}`}>
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <a href={`/facility/${facilityId}/patient/${r.patient_id}`} className="font-medium text-foreground hover:underline">
                  {r.patient_name}
                </a>
                <span className="text-foreground">{r.message}</span>
                <span className="text-xs text-muted-foreground">
                  {new Date(r.created).toLocaleString()}{r.sms_sent ? " · SMS sent" : ""}
                </span>
              </div>
              {r.acknowledged
                ? <Badge variant="neutral">Seen</Badge>
                : <Button type="button" size="sm" variant="secondary" onClick={() => seen(r)}>Mark seen</Button>}
            </li>
          ))}
        </ul>
        {(items?.length ?? 0) > 8 && (
          <div>
            <Button type="button" size="sm" variant="ghost" onClick={() => setAll((v) => !v)}>
              {all ? "Show fewer" : `Show all ${items?.length}`}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
