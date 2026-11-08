# care_maternal (ECHO-OB Caretrail)

A maternal care plugin for [CARE](https://github.com/ohcnetwork/care), built for a two-hospital referral
demo: a rural PHC refers a pregnant patient to a district hospital, with consent, deadlines and escalation.

**Synthetic data only. The clinical pathway was reviewed and approved by the doctor partner (Dr. Jershita Vakkalagadda); no clinical validation has been done yet. Not for clinical use.**

Built by team MedAI Minds (code F44W5G) for Health-a-thon 2026, started 13 Oct 2026. It is a plugin for the real
CARE EMR. A clinic with no EMR can run CARE plus this plugin as one standalone system on one server. Tech team: SRM
Institute of Science and Technology. Sarvam AI translation of reminders is a test implementation and is not built yet.

## What it does

- **A check list doctors can edit.** The checks every pregnancy gets (43 seeded from a clinician-authored PDF)
  are data. Doctors and facility admins add, edit, retire and prioritise checks in the app, with no code.
- **Priority and reminders.** Each check is `high`, `medium`, `low` or `optional`. Reminders go to everyone on
  duty (doctors, nurses, ASHA workers) and to the patient: earlier and more often for high priority, once on the
  due date for low, never for optional (which is not mandatory).
- **Late patients.** A patient who enrols at 20 weeks has overdue checks. The doctor marks the ones she had
  elsewhere, or that are not needed for her (with a reason), one at a time or in bulk.
- **A Maternal tag and worklist.** A CARE patient tag, set while a mandatory check is open and removed after the
  last. A worklist of tagged patients, and a panel on CARE's Patient Home.
- **Booking.** Book a check at a chosen date and time as a real CARE appointment.
- **No-show.** Marked by hand or automatically; the check is due again; three no-shows raise an ASHA home visit.
- **Referrals between hospitals** with patient consent, a 24 hour acknowledgement deadline, escalation (check
  the patient, refer again, manage here) and a timeline.
- **Hospital-wide access.** Every staff member can open every patient registered at their hospital.
- **Eka Care scribe** with a server-side token proxy, so the client secret never reaches a browser.

## Layout

```
backend/      Django plugin `care_maternal` (OHC plugin template: src/, pyproject.toml, Makefile, docs/)
frontend/     React plugin `care_maternal_fe`: a Vite Module Federation remote for CARE's frontend, on CARE UI
eka-scribe/   A modified copy of OHC's care_eka_scribe_fe: it asks the backend for a token (MIT)
```

| Read | For |
|---|---|
| [backend/README.md](backend/README.md) | the API, settings, reminders, commands, tests, known limits |
| [frontend/README.md](frontend/README.md) | the screens, CARE UI, build and caching notes |
| [backend/DEMO.md](backend/DEMO.md) | a step-by-step test runbook for the live hospitals |
| [backend/DEMO-HANDOVER.md](backend/DEMO-HANDOVER.md) | the two-hospital deployment, deploying a change, the referral stories |
| [backend/HISTORY.md](backend/HISTORY.md) | what changed in each version |

## Where it runs

Two separate CARE instances on one EC2 server, public through named Cloudflare tunnels on `ccoogo.co`:

| | Hospital A: Rural PHC Alpha | Hospital B: District Hospital Beta |
|---|---|---|
| App | `hospital-a.ccoogo.co` | `hospital-b.ccoogo.co` |
| API | `api-hospital-a.ccoogo.co` | `api-hospital-b.ccoogo.co` |
| Plugin files | `plugin-hospital-a.ccoogo.co` | `plugin-hospital-b.ccoogo.co` |

They refer to each other over a private Docker network with bearer tokens. Logins, the Eka client secret and
tunnel tokens are kept out of this repository (private files on the laptop and the server).

## Quick start (development)

Run the CARE scaffold's `bootstrap.prompt.md` through Phase 6 so the plugin is mounted into the backend and worker
containers, then:

```bash
.agent/compose.sh exec -T backend python manage.py migrate
.agent/compose.sh exec -T backend python manage.py test \
  care_maternal.tests.test_schedule care_maternal.tests.test_services_api care_maternal.tests.test_referrals \
  care_maternal.tests.test_tags care_maternal.tests.test_booking care_maternal.tests.test_no_show \
  care_maternal.tests.test_registrar_link care_maternal.tests.test_access care_maternal.tests.test_eka \
  care_maternal.tests.test_check_list care_maternal.tests.test_reminders          # 96 tests

cd frontend && npm install && npx tsc --noEmit -p . && npm run build
```

## Configuration

Set these in the plugin's Compose override (no secrets in code):

| Setting | Meaning |
|---|---|
| `MATERNAL_FACILITY_NAME` | name shown for this hospital in referrals |
| `MATERNAL_PEERS` | JSON of peer hospitals: URL and token |
| `MATERNAL_INBOUND_TOKEN` | secret other hospitals send to refer here |
| `MATERNAL_HANDOVER_HOURS` | acknowledgement deadline (default 24) |
| `MATERNAL_DEMO_SMS_ENABLED` | demo OTP logger; `false` on public hospitals |
| `MATERNAL_NOTIFY_ROLES` | roles that get reminders (default `Doctor,Nurse,ASHA Worker`) |
| `MATERNAL_EKA_CLIENT_ID`, `MATERNAL_EKA_CLIENT_SECRET` | Eka Care (keep the secret in an env file) |

## Known limits (MVP)

- The pathway is approved by the doctor partner, but the approval is not yet recorded in the spec's `meta.signoff`
  block. Every seeded check is `medium` until priorities are set in the app, and reminder timings are defaults.
- SMS is console only. Nothing reaches a real phone.
- Patient login uses a fixed code in non-production builds (CARE core behaviour).
- Districts are not loaded; the address list has states and union territories only.
- Any staff member at the receiving hospital can acknowledge an inbound referral.
- The frontends run on Vite's dev server on the demo hosts, with no login wall in front of the tunnels.
- Cloudflare's 4 hour browser cache can keep an old copy of the plugin until Browser Cache TTL is set to
  "Respect Existing Headers".

See `backend/README.md` for the full list.
