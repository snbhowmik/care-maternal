import { useCallback, useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/careui/alert";
import { Badge } from "@/components/careui/badge";
import { Button } from "@/components/careui/button";
import { Field, FieldLabel } from "@/components/careui/field";
import { Input } from "@/components/careui/input";
import type { Referral } from "@/types";
import { errorMessage, request } from "@/utils/api";

const STATUS_LABEL: Record<string, string> = {
  draft: "Needs consent",
  ready: "Consent recorded, ready to send",
  sent: "Sent, waiting for acknowledgement",
  received: "Received by the other hospital",
  acknowledged: "Acknowledged by the other hospital",
  examined: "Patient examined by the other hospital",
  incomplete: "Handover incomplete: deadline passed",
  referred_again: "Referred again",
  self_managed: "Being managed here",
  closed: "Closed",
};

const STATUS_BADGE: Record<string, "destructive" | "success" | "warning" | "info" | "neutral"> = {
  incomplete: "destructive",
  examined: "success",
  acknowledged: "success",
  self_managed: "warning",
  sent: "info",
  ready: "info",
};

interface Props {
  pregnancyId: string;
}

type Act = (label: string, fn: () => Promise<unknown>) => Promise<boolean>;

export default function Referrals({ pregnancyId }: Props) {
  const [referrals, setReferrals] = useState<Referral[]>([]);
  const [peers, setPeers] = useState<string[]>([]);
  const [peer, setPeer] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const reload = useCallback(async () => {
    try {
      setReferrals(await request<Referral[]>(`/referrals/?pregnancy=${pregnancyId}`));
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [pregnancyId]);

  useEffect(() => {
    reload();
    request<{ facility: string; peers: string[] }>("/referrals/peers/")
      .then((r) => {
        setPeers(r.peers);
        setPeer((p) => p || r.peers[0] || "");
      })
      .catch(() => setPeers([]));
  }, [reload]);

  const act: Act = async (label, fn) => {
    setError("");
    setNotice("");
    try {
      await fn();
      setNotice(label);
      await reload();
      return true;
    } catch (err) {
      setError(errorMessage(err));
      return false;
    }
  };

  const start = async () => {
    const ok = await act("Referral created. Record the patient's consent before sending.", () =>
      request("/referrals/", "POST", { pregnancy: pregnancyId, peer, reason }),
    );
    if (ok) setReason("");
  };

  return (
    <section className="flex flex-col gap-4" aria-label="Referrals">
      <h4 className="text-sm font-semibold text-foreground">Refer to another hospital</h4>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {notice && (
        <Alert variant="success">
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      )}

      <div className="flex flex-col gap-3 rounded-lg border bg-soft-background p-3">
        <Field>
          <FieldLabel>Hospital</FieldLabel>
          {peers.length === 0 ? (
            <p className="text-sm text-muted-foreground">No other hospitals are configured.</p>
          ) : (
            <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Hospital">
              {peers.map((p) => (
                <Button key={p} type="button" size="sm" role="radio" aria-checked={peer === p}
                  variant={peer === p ? "default" : "outline"} onClick={() => setPeer(p)}>
                  {p}
                </Button>
              ))}
            </div>
          )}
        </Field>
        <Field>
          <FieldLabel htmlFor={`referral-reason-${pregnancyId}`}>Reason</FieldLabel>
          <Input id={`referral-reason-${pregnancyId}`} value={reason} onChange={(e) => setReason(e.target.value)}
            placeholder="Why is the patient being referred?" />
        </Field>
        <div>
          <Button type="button" size="sm" disabled={!peer || !reason.trim()} onClick={start}>
            Create referral
          </Button>
        </div>
      </div>

      {referrals.length === 0 && <p className="text-sm text-muted-foreground">No referrals for this pregnancy.</p>}
      {referrals.map((r) => (
        <ReferralRow key={r.id} referral={r} onAct={act} />
      ))}
    </section>
  );
}

function ReferralRow({ referral: r, onAct }: { referral: Referral; onAct: Act }) {
  const [consentBy, setConsentBy] = useState("patient");
  const [check, setCheck] = useState("");
  const [again, setAgain] = useState("");
  const [plan, setPlan] = useState("");
  const base = `/referrals/${r.id}`;

  return (
    <div className="flex flex-col gap-3 rounded-lg border bg-background p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium text-foreground">To {r.to_facility}</span>
        <Badge variant={STATUS_BADGE[r.status] ?? "neutral"}>{STATUS_LABEL[r.status] ?? r.status}</Badge>
      </div>
      <p className="text-muted-foreground">Reason: {r.reason}</p>
      {r.deadline_at && (
        <p className="text-muted-foreground">Acknowledgement due by {new Date(r.deadline_at).toLocaleString()}</p>
      )}
      {r.outcome_note && <p className="text-muted-foreground">Outcome: {r.outcome_note}</p>}

      {r.status === "draft" && (
        <div className="flex flex-wrap items-end gap-2">
          <Field className="w-auto">
            <FieldLabel htmlFor={`consent-${r.id}`}>Consent given by</FieldLabel>
            <Input id={`consent-${r.id}`} value={consentBy} onChange={(e) => setConsentBy(e.target.value)} />
          </Field>
          <Button type="button" size="sm" variant="secondary" disabled={!consentBy.trim()}
            onClick={() => onAct("Consent recorded.", () => request(`${base}/consent/`, "POST", { by: consentBy }))}>
            Record consent
          </Button>
        </div>
      )}
      {r.status === "ready" && (
        <div>
          <Button type="button" size="sm" onClick={() => onAct("Referral sent.", () => request(`${base}/send/`, "POST"))}>
            Send to {r.to_facility}
          </Button>
        </div>
      )}

      {r.status === "incomplete" && (
        <Alert variant="destructive">
          <AlertTitle>The other hospital has not acknowledged this referral</AlertTitle>
          <AlertDescription>
            <div className="mt-2 flex flex-col gap-2">
              <NextStep value={check} onChange={setCheck} placeholder="What did you find when you checked on the patient?"
                label="Record check" onSubmit={() => onAct("Check recorded.", () =>
                  request(`${base}/check-patient/`, "POST", { note: check }))} />
              <NextStep value={again} onChange={setAgain} placeholder="Refer again: why?"
                label="Refer again" onSubmit={() => onAct("New referral created. Record consent for it.", () =>
                  request(`${base}/refer-again/`, "POST", { reason: again }))} />
              <NextStep value={plan} onChange={setPlan} placeholder="Plan for managing the patient here"
                label="Manage here" onSubmit={() => onAct("Managing here. The clinician is alerted.", () =>
                  request(`${base}/manage-here/`, "POST", { note: plan }))} />
            </div>
          </AlertDescription>
        </Alert>
      )}

      <details>
        <summary className="cursor-pointer text-muted-foreground">Timeline ({r.events.length})</summary>
        <ol className="mt-2 flex flex-col gap-1 border-l pl-3">
          {r.events.map((e, i) => (
            <li key={i} className="text-foreground">
              <span className="text-muted-foreground">{new Date(e.at).toLocaleString()}</span> · {e.action.replace(/_/g, " ")}
              {e.actor && <span className="text-muted-foreground"> · {e.actor}</span>}
              {e.note && <span> · {e.note}</span>}
            </li>
          ))}
        </ol>
      </details>
    </div>
  );
}

function NextStep({ value, onChange, placeholder, label, onSubmit }: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  label: string;
  onSubmit: () => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      <Input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
        aria-label={placeholder} className="min-w-48 flex-1 bg-background" />
      <Button type="button" size="sm" variant="secondary" disabled={!value.trim()} onClick={onSubmit}>
        {label}
      </Button>
    </div>
  );
}
