import { useCallback, useEffect, useState } from "react";

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

const STATUS_CLASS: Record<string, string> = {
  incomplete: "bg-danger-100 text-danger-700",
  examined: "bg-primary-100 text-primary-800",
  acknowledged: "bg-primary-100 text-primary-800",
  self_managed: "bg-warning-100 text-warning-700",
};

interface Props {
  pregnancyId: string;
}

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

  const start = () =>
    act("Referral created. Record the patient's consent before sending.", () =>
      request("/referrals/", "POST", { pregnancy: pregnancyId, peer, reason }),
    ).then(() => setReason(""));

  return (
    <section className="space-y-3 rounded border border-secondary-400 bg-white p-3">
      <h4 className="font-semibold text-secondary-900">Refer to another hospital</h4>
      {error && <p className="text-sm text-danger-500">{error}</p>}
      {notice && <p className="text-sm text-primary-700">{notice}</p>}

      <div className="grid gap-2 sm:grid-cols-[1fr_2fr_auto]">
        <select value={peer} onChange={(e) => setPeer(e.target.value)}
          className="rounded border border-secondary-400 px-2 py-1 text-sm">
          {peers.length === 0 && <option value="">No hospitals configured</option>}
          {peers.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <input value={reason} onChange={(e) => setReason(e.target.value)}
          placeholder="Why is the patient being referred?"
          className="rounded border border-secondary-400 px-2 py-1 text-sm" />
        <button type="button" disabled={!peer || !reason.trim()} onClick={start}
          className="rounded bg-primary-700 px-3 py-1 text-sm text-white disabled:opacity-50">
          Create referral
        </button>
      </div>

      {referrals.length === 0 && <p className="text-sm text-secondary-600">No referrals for this pregnancy.</p>}
      {referrals.map((r) => (
        <ReferralRow key={r.id} referral={r} onAct={act} />
      ))}
    </section>
  );
}

function ReferralRow({
  referral: r,
  onAct,
}: {
  referral: Referral;
  onAct: (label: string, fn: () => Promise<unknown>) => Promise<void>;
}) {
  const [consentBy, setConsentBy] = useState("patient");
  const [note, setNote] = useState("");
  const [again, setAgain] = useState("");
  const base = `/referrals/${r.id}`;
  return (
    <div className="space-y-2 rounded border border-secondary-300 p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium">To {r.to_facility}</span>
        <span className={`rounded px-2 py-0.5 text-xs ${STATUS_CLASS[r.status] ?? "bg-secondary-200"}`}>
          {STATUS_LABEL[r.status] ?? r.status}
        </span>
      </div>
      <p className="text-secondary-700">Reason: {r.reason}</p>
      {r.deadline_at && (
        <p className="text-secondary-700">Acknowledgement due by {new Date(r.deadline_at).toLocaleString()}</p>
      )}
      {r.outcome_note && <p className="text-secondary-700">Outcome: {r.outcome_note}</p>}

      {r.status === "draft" && (
        <div className="flex flex-wrap gap-2">
          <input value={consentBy} onChange={(e) => setConsentBy(e.target.value)}
            placeholder="Who gave consent" className="rounded border border-secondary-400 px-2 py-1" />
          <button type="button" onClick={() => onAct("Consent recorded.", () =>
            request(`${base}/consent/`, "POST", { by: consentBy }))}
            className="rounded border border-primary-700 px-2 py-1 text-primary-700">Record consent</button>
        </div>
      )}
      {r.status === "ready" && (
        <button type="button" onClick={() => onAct("Referral sent.", () => request(`${base}/send/`, "POST"))}
          className="rounded bg-primary-700 px-2 py-1 text-white">Send to {r.to_facility}</button>
      )}

      {r.status === "incomplete" && (
        <div className="space-y-2 rounded bg-danger-50 p-2">
          <p className="font-medium text-danger-700">The other hospital has not acknowledged this referral. Choose a next step:</p>
          <div className="flex flex-wrap gap-2">
            <input value={note} onChange={(e) => setNote(e.target.value)}
              placeholder="What did you find when you checked on the patient?"
              className="flex-1 rounded border border-secondary-400 px-2 py-1" />
            <button type="button" disabled={!note.trim()} onClick={() => onAct("Check recorded.", () =>
              request(`${base}/check-patient/`, "POST", { note }))}
              className="rounded border border-secondary-500 px-2 py-1">Record check</button>
          </div>
          <div className="flex flex-wrap gap-2">
            <input value={again} onChange={(e) => setAgain(e.target.value)}
              placeholder="Refer again: why?" className="flex-1 rounded border border-secondary-400 px-2 py-1" />
            <button type="button" disabled={!again.trim()} onClick={() => onAct("New referral created. Record consent for it.", () =>
              request(`${base}/refer-again/`, "POST", { reason: again }))}
              className="rounded border border-secondary-500 px-2 py-1">Refer again</button>
          </div>
          <div className="flex flex-wrap gap-2">
            <input value={note} onChange={(e) => setNote(e.target.value)}
              placeholder="Plan for managing the patient here" className="flex-1 rounded border border-secondary-400 px-2 py-1" />
            <button type="button" disabled={!note.trim()} onClick={() => onAct("Managing here. Clinician alerted.", () =>
              request(`${base}/manage-here/`, "POST", { note }))}
              className="rounded border border-secondary-500 px-2 py-1">Manage here</button>
          </div>
        </div>
      )}

      <details>
        <summary className="cursor-pointer text-secondary-700">Timeline ({r.events.length})</summary>
        <ol className="mt-2 space-y-1 border-l border-secondary-300 pl-3">
          {r.events.map((e, i) => (
            <li key={i}>
              <span className="text-secondary-600">{new Date(e.at).toLocaleString()}</span> · {e.action.replace(/_/g, " ")}
              {e.actor && <span className="text-secondary-600"> · {e.actor}</span>}
              {e.note && <span> · {e.note}</span>}
            </li>
          ))}
        </ol>
      </details>
    </div>
  );
}
