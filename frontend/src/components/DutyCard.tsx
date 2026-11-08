import { useCallback, useEffect, useState } from "react";

import { Alert, AlertDescription } from "@/components/careui/alert";
import { Badge } from "@/components/careui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/careui/card";
import { Label } from "@/components/careui/label";
import { Switch } from "@/components/careui/switch";
import type { DutyState } from "@/types";
import { errorMessage, request } from "@/utils/api";

/** Who is on duty. Reminders for due checks go to the people on duty, so switch yourself on at the start of a shift. */
export default function DutyCard() {
  const [duty, setDuty] = useState<DutyState | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    request<DutyState>("/duty/").then(setDuty).catch((err) => setError(errorMessage(err)));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function toggle(on: boolean) {
    setError("");
    try {
      setDuty(await request<DutyState>("/duty/", "POST", { on }));
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  if (!duty && !error) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>On duty</CardTitle>
        <CardDescription>
          Reminders for due checks go to everyone on duty. The switch turns itself off after {duty?.hours ?? 12} hours.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
        {duty && (
          <>
            <Label className="flex items-center gap-3 font-medium text-foreground">
              <Switch checked={duty.mine} onCheckedChange={toggle} aria-label="I am on duty" />
              {duty.mine ? "You are on duty" : "You are off duty"}
            </Label>
            {!duty.in_team && (
              <p className="text-sm text-muted-foreground">
                Your role is not in the reminder list ({duty.roles.join(", ")}), so you will not receive reminders.
              </p>
            )}
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-muted-foreground">On duty now:</span>
              {duty.on_duty.length === 0
                ? <span className="text-muted-foreground">nobody. Reminders go to the whole team instead.</span>
                : duty.on_duty.map((p) => <Badge key={p.id} variant="success">{p.name}</Badge>)}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
