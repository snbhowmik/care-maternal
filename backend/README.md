# care_maternal (backend)

Pregnancy-to-postpartum care for CARE. MVP demo for a two-hospital referral story: a rural PHC
refers, a district hospital receives. **Synthetic data only. Not for clinical use.**

A [CARE](https://github.com/ohcnetwork/care) backend plugin: an ordinary Django app installed in
CARE's runtime and registered through `ADDITIONAL_PLUGS`. It follows the OHC plugin template
layout (`src/`, `pyproject.toml`, `Makefile`, `docs/`). CARE core is unchanged.

The pathway comes from a clinician-authored PDF (`IMG_1737.pdf`). It is transcribed into
`src/care_maternal/spec/maternal_pathway.yaml` (each item records its source page). **Clinician
sign-off is still pending**, and spec open questions Q1 to Q7 are unanswered.

## What it does

| Area | Behaviour |
|---|---|
| Check list | 43 checks seeded from the spec the first time they are needed. Doctors and facility admins then add, edit, retire and set the priority of checks, with no code. Changes apply to patients enrolled afterwards. Each hospital has its own list. |
| Schedule | Each pregnancy gets its checks with due windows computed from the LMP. States: `overdue`, `due`, `upcoming`, `waiting`, `done`, `elsewhere`, `waived` (not needed). |
| Late enrolment | Overdue checks can be marked **done elsewhere** (optional place and date) or **not needed** (reason required), one at a time or in bulk, and reopened. Closed checks leave the tag, the worklist counts and the overdue alerts. |
| Priority and reminders | `high`, `medium`, `low`, `optional`. See [Reminders and duty](#reminders-and-duty). |
| Maternal tag | A CARE facility tag, set while any mandatory check is open and removed after the last. It can also be added by hand. |
| Booking | Book a check at a chosen date and time as a real CARE appointment (`TokenBooking`). Taken slots are refused. |
| No-show | A booked visit can be marked no-show, or a sweep does it 30 minutes after the slot. The check becomes due again. At three no-shows an ASHA home visit is raised for the same day. |
| Referrals | Hospital to hospital over HTTP with patient consent, a 24 hour acknowledgement deadline, escalation (check the patient, refer again, manage here), and an append-only timeline. |
| Emergency | Report symptoms: clinician alert plus a patient SMS (console only in the demo). |
| Access | Every staff member at a hospital can open every patient registered there (a role on each state), and the registering staff member is linked to the patient. |
| Eka Care scribe | Server-side token proxy, so the Eka client secret never reaches a browser. |
| Patient portal | A plain HTML demo page with OTP login (read-only). |

## Layout

```
pyproject.toml, Makefile, MANIFEST.in, HISTORY.md, docs/
src/care_maternal/
  models/              pregnancy, schedule item, alert, referral (+ events), home visit, check template, duty
  utils/schedule.py    pure schedule engine (no Django): gestational age, due windows, item state
  spec/                clinician spec (YAML)
  services.py          business rules: enrol, complete, resolve/reopen, custom check, alerts, emergency
  check_templates.py   the hospital's check list: seed, validate, edit permission
  booking.py           slots and booking at a chosen time
  no_show.py           no-show, sweep, ASHA home visit
  reminders.py         priority rules and the reminder sweep
  duty.py              who is on duty
  tags.py              Maternal tag and worklist query
  access.py            hospital-wide patient access for staff
  referrals.py         referral lifecycle between hospitals
  eka.py               Eka Care token minting and caching
  viewsets/            staff API, referral API, patient (OTP) API, check list, duty, Eka token
  signals.py           link the registrar to a new patient; give new staff patient access
  tasks/               Celery periodic tasks
  management/commands/ seed, backfill and demo commands
  tests/               96 tests
```

## Staff API

Base path `/api/care_maternal/`. Every patient endpoint checks CARE's own `can_view_patient_obj` /
`can_write_patient_obj` (the registering user counts as allowed). A user with no access gets 404, so
the API does not reveal that the patient exists. Requests that touch the Maternal tag take the
hospital as `facility=<facility id>`.

| Method | Path | Notes |
|---|---|---|
| GET | `pregnancies/?patient=<id>` | a patient's pregnancies |
| POST | `pregnancies/` | enrol (`patient`, `lmp`, G/P/A/L, `facility`) |
| GET | `pregnancies/worklist/?facility=` | every patient with the Maternal tag, with open and overdue counts |
| GET | `pregnancies/<id>/items/` | the schedule |
| POST | `pregnancies/<id>/items/<spec_id>/complete/` | record done |
| POST | `.../resolve/` | `resolution` = `elsewhere` or `not_needed`, `note`, optional `on_date` |
| POST | `.../reopen/` | undo a resolution |
| POST | `.../book/` | `on_date`, `start_time` (HH:MM) |
| POST | `.../no-show/` | mark a booked visit as missed |
| GET | `pregnancies/<id>/slots/?date=` | the day's 15 minute slots, 09:00 to 17:00, free or taken |
| POST | `pregnancies/<id>/add-check/` | a check for this patient only (`label`, `kind`, `priority`, optional dates) |
| GET | `pregnancies/<id>/home-visits/` | ASHA home visits |
| POST | `pregnancies/<id>/home-visits/<id>/visited/` | record the visit |
| POST | `pregnancies/<id>/emergency/`, `.../sweep/` | emergency report, overdue sweep |
| GET | `pregnancies/<id>/alerts/` | alerts (without per-person staff reminders) |
| GET, POST, PATCH | `check-templates/` | the check list. Anyone on staff reads; doctors and facility admins change |
| GET, POST | `duty/` | who is on duty; switch yourself on or off (`on`) |
| GET | `reminders/` | your own reminders |
| POST | `reminders/<id>/acknowledge/` | mark seen |
| GET | `eka/token/` | a 30 minute Eka access token (`?renew=1` after a 401). Staff only, never cached |
| GET | `config/` | any logged-in user |

Referrals (`referrals/`): `GET peers/`, `POST` create, `POST <id>/consent/`, `<id>/send/`,
`<id>/check-patient/`, `<id>/refer-again/`, `<id>/manage-here/`, `GET inbox/`, `POST <id>/acknowledge/`,
`<id>/examined/`, `POST sweep/`. Between hospitals: `POST referrals/inbound/` and `referrals/status/`
(bearer peer token, compared in constant time).

### Patient portal

`GET portal/` is the demo page. Login uses CARE core: `POST /api/v1/otp/send/`, `/api/v1/otp/login/`
(non-production stacks accept the fixed code `45612`). Then read-only `otp/pregnancies/`,
`otp/pregnancies/<id>/{items,alerts}/` and `otp/referrals/`, scoped to the phone number in the token.
`otp/demo-sms/` writes the latest code to the log and is switched off on public hospitals
(`MATERNAL_DEMO_SMS_ENABLED=false`).

## Reminders and duty

CARE has no duty roster, so staff switch themselves on and off (`duty/`); a forgotten switch expires
after 12 hours. Reminders go to **everyone on duty** in the notify roles (default Doctor, Nurse, ASHA
Worker) and to the patient. If nobody is on duty, the whole team is told, so a reminder is never lost.

| Priority | First reminder | Repeats | Stops |
|---|---|---|---|
| high | 3 days before it is due | up to 3 a day, 4 hours apart; staff on duty also get an SMS | 14 days after the due date |
| medium | 1 day before | twice a day, 6 hours apart | 7 days after the due date |
| low | on the due date | never | after one reminder |
| optional | never | never | the record is not mandatory: it never keeps the tag or counts as overdue |

Reminders go out between 08:00 and 20:00 (local). A check with a booked appointment is not reminded.
Each person gets one message per patient listing all that patient's due checks. **These numbers are my
defaults and need clinician review.**

## Periodic tasks (Celery)

| Task | Every | Does |
|---|---|---|
| `care_maternal.sweep_handovers` | 5 min | marks referrals past their deadline as incomplete and alerts |
| `care_maternal.sweep_no_shows` | 5 min | marks missed bookings as no-show |
| `care_maternal.sweep_reminders` | 15 min | sends due reminders by priority |

## Settings

Resolution order: `PLUGIN_CONFIGS["care_maternal"][key]` → environment variable → default
(`src/care_maternal/settings.py`).

| Key | Meaning |
|---|---|
| `MATERNAL_FACILITY_NAME` | name shown for this hospital in referrals |
| `MATERNAL_PEERS` | JSON: peer hospital name → `{url, token}` |
| `MATERNAL_INBOUND_TOKEN` | secret other hospitals send to refer to this one |
| `MATERNAL_HANDOVER_HOURS` | acknowledgement deadline (default 24) |
| `MATERNAL_DEMO_SMS_ENABLED` | demo OTP logger; **false** on any public hospital |
| `MATERNAL_NOTIFY_ROLES` | roles that receive reminders (default `Doctor,Nurse,ASHA Worker`) |
| `MATERNAL_EKA_CLIENT_ID`, `MATERNAL_EKA_CLIENT_SECRET`, `MATERNAL_EKA_API_BASE` | Eka Care. Keep the secret in an env file, never in code |

## Management commands

| Command | Use |
|---|---|
| `sync_maternal_tags --facility <id>` | set the Maternal tag to match open checks at one hospital |
| `load_india_states` | add the 36 states and union territories as geo organizations, then grant staff access |
| `grant_staff_patient_access` | give every staff member access to all patients here (idempotent) |
| `seed_maternal_demo`, `seed_handover_demo`, `demo_expire_handover` | demo data only |

## Install and test

Run `care_scaffold/bootstrap.prompt.md` through Phase 6. `.agent/plugin.compose.yaml` mounts this
repo into the backend and worker containers, installs it in editable mode at startup
(`pip install -e /plugins/care_maternal`) and registers it through `ADDITIONAL_PLUGS`. Use
`.agent/compose.sh` for every command so the isolated project and ports are kept.

```bash
.agent/compose.sh exec -T backend python manage.py migrate
.agent/compose.sh exec -T backend python manage.py test \
  care_maternal.tests.test_schedule care_maternal.tests.test_services_api care_maternal.tests.test_referrals \
  care_maternal.tests.test_tags care_maternal.tests.test_booking care_maternal.tests.test_no_show \
  care_maternal.tests.test_registrar_link care_maternal.tests.test_access care_maternal.tests.test_eka \
  care_maternal.tests.test_check_list care_maternal.tests.test_reminders     # 96 tests
```

After changing models: `manage.py makemigrations care_maternal`. After changing the Celery tasks,
restart the `celery` service so it re-registers them.

## Known limits

**Clinical (need a clinician)**
1. The spec is unsigned and open questions Q1 to Q7 are unanswered (emergency wording, high-risk
   criteria, postnatal schedule, labour thresholds, missed-visit grace period, mandatory results,
   Td protocol).
2. Every seeded check is `medium`; nothing is `high` until a clinician sets it. Reminder timings are defaults.
3. Patient SMS wording is marked `[DEMO]` and must not reach a real patient.
4. `high_risk` is never set automatically; its criteria are Q2.

**Product**
5. SMS is console only. A real provider and patient consent are needed.
6. ASHA workers are found by the `ASHA Worker` role. If none exists, a home visit is raised unassigned.
7. Check list edits record who last changed a check, but there is no change history view.
8. Check list changes do not touch patients already enrolled.
9. Districts are not loaded; only states and union territories.
10. Any staff member at the receiving hospital can acknowledge an inbound referral (scope it to the facility before real use).
11. Emergency reports are not rate limited.

**Technical**
12. Reminder timing uses a fixed window (08:00 to 20:00) and fixed gaps in `reminders.py`.
13. `date.today()` (serializers) and `timezone.localdate()` (services) can disagree around midnight.
14. Tested on CARE `develop` only.
15. The patient portal is a plain HTML page; the React host has no patient page surface to plug into.
16. The fixed dev login code `45612` is CARE core behaviour on non-production stacks.

## Rules for this plugin

- Work only in this repo. Do not edit CARE core or its configuration.
- Use synthetic patients and phone numbers only.
- No clinical rule or patient-facing text goes live until a clinician signs off the spec.
