# care_maternal

Pregnancy-to-postpartum care pathway for rural clinics. This is an MVP demo, not the real
app, and it is not for clinical use.

A [CARE](https://github.com/ohcnetwork/care) backend plugin. It is an ordinary Django app,
installed in CARE's runtime and registered through `ADDITIONAL_PLUGS`. This directory is an
independent Git repository with no commits or remote yet.

The clinical pathway comes from a clinician-authored PDF (`IMG_1737.pdf`). The spec is in
`care_maternal/spec/maternal_pathway.yaml`, and each item records its source page.

## Status

| Stage | What | State |
|---|---|---|
| 0 | Host decision (laptop) | done |
| 1 | Clinical spec from the PDF | done, awaiting clinician sign-off |
| 2 | Isolated CARE stack | done (workspace `care-maternal-workspace`) |
| 3 | Backend plugin (this package) | done, checked by hand only |
| 4 | Patient portal with OTP login | done (demo portal page, checked by hand) |
| 5 | Frontend plugin `care_maternal_fe` | not started |

## What is built

### Models (`care_maternal/models/__init__.py`)
- `MaternalPregnancy`: one pregnancy for one CARE patient. Holds LMP, EDD (LMP + 280 days),
  gravida/para/abortions/living, `high_risk` (for a clinician to set), and `status`.
- `MaternalScheduleItem`: one spec item for one pregnancy. Holds the due window, the done
  date, who completed it, and whether it is waiting on another event.
- `MaternalAlert`: a clinician alert, or a patient SMS record.

All three extend CARE's `EMRBaseModel` and link to CARE's `emr.Patient` by foreign key.
CARE core is unchanged.

### Schedule engine (`care_maternal/utils/schedule.py`)
- Pure Python with no Django imports.
- Parses gestational ages such as `13+6`.
- Builds 43 schedule items from the spec, each with a due window from the LMP.
- Td-2 has no date until Td-1 is recorded. The Td booster is marked for a clinician decision.
- Item states: `done`, `waiting`, `upcoming`, `due`, `overdue`.

### Business rules (`care_maternal/services.py`)
- `create_pregnancy`: creates the pregnancy and its schedule items.
- `complete_item`: records a done date. Completing Td-1 sets Td-2 to four weeks later.
- `sweep_overdue`: raises one clinician alert per newly overdue item.
- `report_emergency`: raises a clinician alert, and sends a patient SMS through CARE's SMS backend.

### Staff API (`care_maternal/viewsets/pregnancy.py`)
Base path: `/api/care_maternal/`

| Method | Path | Access |
|---|---|---|
| GET | `pregnancies/?patient=<patient id>` | can view the patient |
| POST | `pregnancies/` | can write the patient |
| GET | `pregnancies/<id>/` | can view the patient |
| GET | `pregnancies/<id>/items/` | can view the patient |
| POST | `pregnancies/<id>/items/<spec_id>/complete/` | can write the patient |
| POST | `pregnancies/<id>/emergency/` | can write the patient |
| POST | `pregnancies/<id>/sweep/` | can write the patient |
| GET | `pregnancies/<id>/alerts/` | can view the patient |
| GET | `config/` | any logged-in user |

### Patient portal (Stage 4)

| Method | Path | Access |
|---|---|---|
| GET | `/api/care_maternal/portal/` | the demo portal page (HTML, no login to load) |
| POST | `/api/v1/otp/send/` | CARE core: sends a login code |
| POST | `/api/v1/otp/login/` | CARE core: returns a patient token |
| POST | `/api/care_maternal/otp/demo-sms/` | demo only: writes the latest code to the server log. Disabled in production |
| GET | `otp/pregnancies/` | patient token: the patient's own pregnancies |
| GET | `otp/pregnancies/<id>/` | patient token: one of the patient's pregnancies |
| GET | `otp/pregnancies/<id>/items/` | patient token: schedule items |
| GET | `otp/pregnancies/<id>/alerts/` | patient token: alerts addressed to the patient only |

Patient endpoints are read-only and scoped to the phone number in the token. A patient token
gets 403 on the staff endpoints.

**Demo login:** open `/api/care_maternal/portal/`, enter the synthetic phone number, then the
code. In this non-production stack CARE uses the fixed dev code `45612`, and the demo SMS line
in the server log shows it.

Access uses CARE's own `can_view_patient_obj` and `can_write_patient_obj`. A user with no link
to the patient gets 404, so the API does not reveal that the patient exists.

### Tests
- `care_maternal/tests/test_schedule.py`: 10 unit tests for the engine, all passing.
  Run with `python manage.py test care_maternal.tests.test_schedule`.
- The API was checked by hand with curl against the running stack. It is not automated.

## Known issues

These will be fixed later. Some need a clinician decision first.

### Clinical (need clinician input)
1. **Td-1 window is too wide.** The spec gives Td-1 the whole pregnancy (LMP to 40 weeks), while
   the PDF says "as early as possible at first ANC visit". The window probably should start at
   booking.
2. **Spec open questions Q1–Q7 are unanswered.** See `spec/maternal_pathway.yaml`: emergency
   patient SMS wording, high-risk criteria, postnatal visit schedule, labour alert thresholds,
   missed-visit grace period, mandatory results, and the Td protocol for this clinic.
3. **Td booster has no workflow.** It is marked for a clinician decision, but no screen or
   endpoint lets a clinician make that decision.
4. **Emergency patient text is not approved.** It is marked `[DEMO]` and "pending review". It
   must not reach a real patient.
5. **High-risk flag is never set.** The `high_risk` field exists, but nothing sets it until a
   clinician decides the criteria (Q2).

### Product and design
6. **Alert flood.** A pregnancy with an old LMP raised 41 overdue alerts in one sweep. Alerts
   need grouping, or one summary per pregnancy, before real use.
7. **Alerts cannot be acknowledged.** They are read-only, so they can never be closed.
8. **Overdue sweep is manual.** It runs only when someone calls the endpoint. No scheduled
   Celery job exists yet.
9. **Emergency reports are not rate-limited.** Repeated reports send repeated patient SMS.
10. **Emergency reporting needs write access.** A community health worker with read-only access
    cannot report an emergency. The permission model needs deciding.
11. **Patients must be linked by hand.** A user sees a patient only after a `PatientUser` role
    link exists. There is no UI for this.

### Technical
12. **Date handling is inconsistent.** Serializers use `date.today()`, while services use
    `timezone.localdate()`. They can disagree around midnight. Use one function everywhere.
13. **No automated API tests.** Permission checks and state changes were verified by hand.
14. **Dependency added late.** `pyyaml` was added to `setup.py` during Stage 3. Confirm a clean
    install still works.
15. **Not committed.** The repo has untracked files and no commits.
16. **SMS is console only.** Nothing reaches a real phone. Real SMS needs a provider and patient
    consent.
17. **Tested on CARE `develop` only.** The live clinic at `hmis.ccoogo.co` runs pinned feature
    branches. This plugin has not been tested against them.
18. **OHC's `care_notifications_be` not yet reviewed.** It may already cover some of this.
    Review it before building more alerts.
19. **Dev login code is fixed.** CARE uses `45612` in non-production, so anyone who knows the
    phone number can log in on a dev stack. Fine on a laptop, never on a shared server.
20. **Demo SMS endpoint prints live codes.** `otp/demo-sms/` writes the latest login code to the
    server log. It is disabled when `IS_PRODUCTION` is set, but it must be removed before any
    real use.
21. **CARE's own SMS is off.** Core sends login codes by SMS only when `USE_SMS` is on, and that
    setting is hardcoded off. Real patients need an SMS provider first.
22. **Portal is plain HTML.** It is a demo page, not the React frontend. Stage 5 builds the real
    portal. The token is kept in memory, so a page reload signs the patient out.
23. **Portal shows every pregnancy and alert for the phone number.** A patient with two
    pregnancies sees both. Confirm this matches the clinical rules before real use.

## Install (local development)

Run `care_scaffold/bootstrap.prompt.md` through Phase 6. The repo lives at
`$WORKSPACE/care/care_maternal`, where `$WORKSPACE` is the scaffold checkout. It has its own Git
root, and core excludes it through `.git/info/exclude`. `.agent/plugin.compose.yaml` mounts it
into the backend and worker containers, installs it in editable mode at startup, and registers
it through `ADDITIONAL_PLUGS`.

```bash
source "$WORKSPACE/care-scaffold.env"
"$WORKSPACE/.agent/compose.sh" up -d --wait
"$WORKSPACE/.agent/compose.sh" exec backend python manage.py makemigrations care_maternal
"$WORKSPACE/.agent/compose.sh" exec backend python manage.py migrate
"$WORKSPACE/.agent/compose.sh" exec backend python manage.py test care_maternal.tests.test_schedule
```

Use `.agent/compose.sh` for every backend command so the isolated project and ports are kept.
To stop safely, run `"$WORKSPACE/.agent/compose.sh" down` without `-v`.

## Settings

Resolution order: `PLUGIN_CONFIGS["care_maternal"][key]` → environment variable → default.
See `care_maternal/settings.py`.

## Rules for this plugin

- Work only in this repo. Do not edit CARE core or its configuration.
- Use synthetic patients and phone numbers only.
- No clinical rule or patient-facing text goes live until a clinician signs off the spec.
