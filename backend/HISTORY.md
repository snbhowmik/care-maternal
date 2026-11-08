# History

## 0.2.0 (MVP demo, current)

- **Check list:** the checks every pregnancy gets are now data, not a file. Doctors and facility admins add,
  edit, retire and prioritise checks in the app, with no code. Seeded from the clinician spec.
- **Priority and reminders:** `high`, `medium`, `low`, `optional`. Reminders go to everyone on duty and to the
  patient, with lead time, frequency and an end that depend on the priority. Optional checks are not mandatory.
- **On duty:** staff switch themselves on and off; reminders go to people on duty, or the whole team if nobody is.
- **Late enrolment:** overdue checks can be marked done elsewhere or not needed, with a reason, in bulk or one at
  a time, and reopened. A check can also be added for one patient only.
- **Access:** every staff member at a hospital can open every patient registered there; the registering staff
  member is linked to a new patient.
- **Eka Care scribe:** a server-side token proxy, so the client secret never reaches a browser.
- **Booking:** book at a chosen date and time; no-show handling (manual and automatic) and ASHA home visits.
- **Maternal tag:** can be added by hand; patients not yet enrolled show on the worklist.
- **UI:** every screen rebuilt on CARE UI.
- **Layout:** moved to the OHC plugin template (`src/`, `pyproject.toml`, `Makefile`, `docs/`).
- Referral panel blocks double-submits and the server refuses identical draft referrals.
- 96 tests.

## 0.1.0

- Pregnancy schedule from the clinician spec, with overdue alerts.
- Maternal patient tag, worklist, and patient-home panel.
- Referrals between two hospitals with consent, deadlines and escalation.
