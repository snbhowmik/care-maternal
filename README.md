# care_maternal (ECHO-OB Caretrail)

A maternal care plugin for [CARE](https://github.com/ohcnetwork/care), built for a two-hospital referral demo:
a rural PHC (refers) and a district hospital (receives).

It covers pregnancy-to-postpartum checks, a Maternal patient tag, booking at a chosen time, no-show
handling with ASHA home visits, and referrals between the two hospitals with consent, deadlines and
escalation.

**Clinical content is synthetic and pending clinician review. Not for clinical use.**

## Layout

```
backend/    Django app `care_maternal` (CARE plugin: models, API, Celery sweeps, tests, demo docs)
frontend/   React plugin `care_maternal_fe` (Vite Module Federation remote for CARE's frontend)
```

## What it adds to CARE

| Where | What |
|---|---|
| Patient search | "Maternal care" link with the number of tagged patients |
| Patient home | "Maternal checks" panel: enrol, schedule, mark done, book at a time, no-show, home visits, referral |
| Maternal page | Worklist of every patient with the Maternal tag at this hospital |
| Referrals received | Inbox to acknowledge and examine incoming referrals |

The Maternal tag is a CARE facility tag. It is set while any check is open and removed after the last one.

## Backend

- Python 3.13, Django, CARE core (`care`) as the host application.
- Settings come from `PluginSettings` (`settings.py`) through `ADDITIONAL_PLUGS` in the Compose override.
- Periodic tasks (every 5 min): handover deadlines, and no-show sweep (booked visits past the
  appointment time plus a 30-minute grace period, with nothing recorded, are marked no-show).
- Tests:

```bash
python manage.py test care_maternal.tests.test_schedule care_maternal.tests.test_services_api \
  care_maternal.tests.test_referrals care_maternal.tests.test_tags \
  care_maternal.tests.test_booking care_maternal.tests.test_no_show
```

Management commands:

- `sync_maternal_tags --facility <uuid>`: set the Maternal tag to match open checks at one hospital.
- `load_india_states`: add the 36 states and union territories as geo organizations (idempotent).
- `seed_maternal_demo`, `seed_handover_demo`, `demo_expire_handover`: demo data only.

## Frontend

- React + TypeScript + Vite, Tailwind scoped under `.care-maternal-container`.
- The manifest registers routes, nav items and extension points: `PatientHomeQuickActions`
  (patient panel) and `PatientSearchActions` (search link).
- Build: `npm run build`. Type-check: `npx tsc --noEmit -p .`.

## Configuration

Set these in the plugin's Compose override (no secrets in code):

| Setting | Meaning |
|---|---|
| `MATERNAL_FACILITY_NAME` | Name shown for this hospital in referrals |
| `MATERNAL_PEERS` | JSON of peer hospitals and their API URLs |
| `MATERNAL_INBOUND_TOKEN` | Bearer token peers use to send referrals here |
| `MATERNAL_HANDOVER_HOURS` | Deadline for a receiving hospital to acknowledge (default 24) |
| `MATERNAL_DEMO_SMS_ENABLED` | Demo OTP logger; set to `false` on public hospitals |

## Known limits (MVP)

- SMS is console-only. Nothing reaches a real phone.
- Patient OTP login uses a fixed code in non-production builds (CARE core behaviour).
- ASHA workers are found by the `ASHA Worker` role at the hospital. If none is set up, the home visit
  is raised unassigned and the clinician is alerted.
- Districts are not loaded yet; only states and union territories (see `load_india_states`).
- Any logged-in staff at the receiving hospital can acknowledge an inbound referral.
- The frontend runs on Vite's dev server on the demo hosts.

See `backend/DEMO-HANDOVER.md` for the demo script.
