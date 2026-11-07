import { useState } from "react";
import type { FormEvent } from "react";

import type { Pregnancy } from "@/types";
import { currentFacilityId, errorMessage, request } from "@/utils/api";

interface Props {
  patientId: string;
  onCreated: (p: Pregnancy) => void;
}

export default function CreatePregnancy({ patientId, onCreated }: Props) {
  const [lmp, setLmp] = useState("");
  const [gravida, setGravida] = useState(1);
  const [para, setPara] = useState(0);
  const [abortions, setAbortions] = useState(0);
  const [living, setLiving] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const created = await request<Pregnancy>("/pregnancies/", "POST", {
        patient: patientId,
        facility: currentFacilityId(),
        lmp,
        gravida,
        para,
        abortions,
        living,
      });
      onCreated(created);
      setLmp("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const num = (set: (n: number) => void) => (e: React.ChangeEvent<HTMLInputElement>) =>
    set(Number(e.target.value));

  return (
    <form onSubmit={submit} className="rounded-lg border border-secondary-400 bg-white p-4 space-y-3">
      <h3 className="font-bold text-secondary-900">New pregnancy</h3>
      <label className="block text-sm text-secondary-700">
        Last menstrual period (LMP)
        <input type="date" required value={lmp} onChange={(e) => setLmp(e.target.value)}
          className="mt-1 w-full rounded border border-secondary-400 px-2 py-1" />
      </label>
      <div className="grid grid-cols-2 gap-2">
        {[
          ["Gravida", gravida, setGravida],
          ["Para", para, setPara],
          ["Abortions", abortions, setAbortions],
          ["Living", living, setLiving],
        ].map(([label, value, set]) => (
          <label key={label as string} className="block text-sm text-secondary-700">
            {label as string}
            <input type="number" min={0} value={value as number}
              onChange={num(set as (n: number) => void)}
              className="mt-1 w-full rounded border border-secondary-400 px-2 py-1" />
          </label>
        ))}
      </div>
      {error && <p className="text-sm text-danger-500">{error}</p>}
      <button type="submit" disabled={busy || !lmp}
        className="rounded bg-primary-700 px-3 py-2 text-white disabled:opacity-50">
        {busy ? "Saving…" : "Create pregnancy"}
      </button>
    </form>
  );
}
