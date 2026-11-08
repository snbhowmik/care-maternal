export type ItemState = "done" | "elsewhere" | "waived" | "waiting" | "upcoming" | "due" | "overdue";
export type Resolution = "" | "elsewhere" | "not_needed";
export type Priority = "high" | "medium" | "low" | "optional";

/** What each priority does. Mirrors the server rules in reminders.py. */
export const PRIORITIES: { value: Priority; label: string; badge: "destructive" | "warning" | "neutral" | "info"; rule: string }[] = [
  { value: "high", label: "High", badge: "destructive",
    rule: "Everyone on duty and the patient are reminded 3 days early, up to 3 times a day, until it is recorded." },
  { value: "medium", label: "Medium", badge: "warning",
    rule: "Everyone on duty and the patient are reminded 1 day early, twice a day." },
  { value: "low", label: "Low", badge: "neutral",
    rule: "A single reminder on the due date. Never earlier, never repeated." },
  { value: "optional", label: "Optional", badge: "info",
    rule: "No reminders. The record is not mandatory, and it never keeps the patient on the worklist." },
];
export const priorityMeta = (p: string) => PRIORITIES.find((x) => x.value === p) ?? PRIORITIES[1];

export interface Pregnancy {
  id: string;
  patient: string;
  lmp: string;
  edd: string;
  gravida: number;
  para: number;
  abortions: number;
  living: number;
  high_risk: boolean;
  status: string;
  gestational_age: { weeks: number; days: number };
}

export interface ScheduleItem {
  id: string;
  spec_id: string;
  kind: string;
  label: string;
  due_from: string | null;
  due_to: string | null;
  waiting_on: string;
  done_on: string | null;
  state: ItemState;
  appointment_id: string | null;
  appointment_at: string | null;
  resolution: Resolution;
  resolution_note: string;
  resolved_on: string | null;
  priority: Priority;
}

export interface ReferralEvent {
  action: string;
  note: string;
  actor: string;
  at: string;
}

export interface Referral {
  id: string;
  direction: "out" | "in";
  status: string;
  from_facility: string;
  to_facility: string;
  reason: string;
  consent_by: string;
  consent_at: string | null;
  sent_at: string | null;
  deadline_at: string | null;
  acknowledged_at: string | null;
  examined_at: string | null;
  outcome_note: string;
  patient_name: string;
  pregnancy_id: string;
  previous: string | null;
  events: ReferralEvent[];
}

export interface Alert {
  id: string;
  audience: "clinician" | "patient";
  kind: string;
  message: string;
  sms_sent: boolean;
  acknowledged_on: string | null;
  created_date: string;
}

export const EMERGENCY_SYMPTOMS: { value: string; label: string }[] = [
  { value: "vaginal_bleeding", label: "Vaginal bleeding" },
  { value: "severe_abdominal_pain", label: "Severe abdominal pain" },
  { value: "fainting_or_giddiness", label: "Fainting / giddiness" },
  { value: "severe_vomiting_or_dehydration", label: "Severe vomiting or dehydration" },
  { value: "breathlessness_or_unstable_vitals", label: "Breathlessness or unstable vitals" },
];

export interface WorklistRow {
  patient_id: string;
  patient_name: string;
  pregnancy_id: string | null;
  edd: string | null;
  open_checks: number;
  overdue_checks: number;
}

export interface HomeVisit {
  id: string;
  reason: string;
  address: string;
  due_on: string;
  assigned_to: string;
  visited_on: string | null;
  visit_note: string;
}

export interface CheckTemplate {
  id: string;
  spec_id: string;
  label: string;
  kind: string;
  from_weeks: string;
  to_weeks: string;
  relative_to: string;
  after_days: number | null;
  waiting_note: string;
  priority: Priority;
  active: boolean;
  sort_order: number;
  source: "spec" | "custom";
}

export const CHECK_KINDS: { value: string; label: string }[] = [
  { value: "visit_check", label: "Visit" },
  { value: "test", label: "Test" },
  { value: "scan", label: "Scan" },
  { value: "vaccine", label: "Vaccine" },
  { value: "medication", label: "Medicine" },
  { value: "counselling", label: "Counselling" },
  { value: "other", label: "Other" },
];

export const kindLabel = (kind: string): string =>
  CHECK_KINDS.find((k) => k.value === kind)?.label ?? kind.replace(/_/g, " ");

export interface DutyState {
  mine: boolean;
  in_team: boolean;
  hours: number;
  roles: string[];
  on_duty: { id: string; name: string }[];
}

export interface Reminder {
  id: string;
  message: string;
  created: string;
  acknowledged: boolean;
  patient_id: string;
  patient_name: string;
  sms_sent: boolean;
}
