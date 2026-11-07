# Demo runbook: Care Maternal (MVP)

Synthetic data only. Not for clinical use. Everything runs on this laptop.

## 1. Start the system

From the scaffold workspace (`/home/snbhowmik/CODE/care-maternal-workspace`):

```bash
# Backend (CARE + care_maternal). Safe to run when already up.
.agent/compose.sh up -d --wait
.agent/compose.sh exec -T backend python manage.py seed_maternal_demo

# Plugin remote (serves the built maternal page on :29418)
(cd care_maternal_fe && npm run dev)            # keep running

# Host frontend (CARE on :29417, with the maternal plugin enabled)
.agent/frontend.sh                              # keep running
```

Wait for `backend` to show `healthy` in `.agent/compose.sh ps`.

## 2. Accounts and URLs

| What | Where | Login |
|---|---|---|
| CARE staff app | http://localhost:29417 | `care-doctor` / `(see the private logins file)` |
| Maternal staff page | http://localhost:29417/facility/27a7244d-8daa-4234-90d5-cb2d27aebc4b/maternal?patient=5be80b0e-faa2-48c6-86d0-5c61ea3839d3 | (same as above) |
| Patient portal | http://localhost:29416/api/care_maternal/portal/ | phone `+919999000001`, code `45612` |
| Server log (demo SMS) | `.agent/compose.sh logs backend \| grep DEMO` | — |

The demo patient is `SYNTHETIC Demo Patient`. The seed command prints its ID.
The facility is in the fixtures. The doctor is linked to the patient with the Doctor role.

## 3. Demo script (about 5 minutes)

**Staff side (CARE app, as `care-doctor`):**
1. Open the maternal page above. Show the header: gestational age, EDD, G/P/A/L.
2. Show the schedule grouped by state: overdue, due, upcoming, waiting, done.
3. Under "Td-1", set a date and press **Mark done**. Show that Td-2 is now due 4 weeks later.
4. Under "Report emergency symptoms", tick **Vaginal bleeding** and press **Report emergency**.
   Show the clinician alert and "(SMS sent)" on the patient alert.
5. Show the server log line: `[DEMO] Please come to the clinic now.` This is the patient SMS.

**Patient side (portal):**
6. Open the portal. Enter `+919999000001` and press **Send login code**.
7. Read the code from the server log (`[DEMO] Your CARE Maternal login code is ...`), or use
   `45612`, the dev code. Enter it and press **Sign in**.
8. Show the patient's pregnancy, schedule and messages. Note that clinician alerts are not
   shown to the patient.

## 4. Check it works

```bash
.agent/compose.sh exec -T backend python manage.py test care_maternal.tests.test_schedule care_maternal.tests.test_services_api
(cd care_maternal_fe && npm run build)
```

Expected: 18 backend tests pass, and the frontend builds with no errors.

## 5. Known limits to say out loud

- **Clinical content is unreviewed.** The schedule is from the PDF. Clinician sign-off is
  pending, and open questions Q1–Q7 are unanswered (see `spec/maternal_pathway.yaml`).
- **Patient SMS is console only.** Nothing reaches a real phone. The emergency text is marked
  `[DEMO]` and awaits clinician wording.
- **Dev login code is fixed** (`45612`) and the demo SMS endpoint prints live codes. Both are
  disabled in production, and this stack is not production.
- **Staff page picks a patient by ID.** No name search yet.
- **No worklist across patients** and **no alert acknowledgement** yet.
- **Patient portal is an HTML demo page**, not the React app. The host has no patient page
  surface to host a React one.
- **Overdue alerts can flood.** An old pregnancy raised 41 overdue alerts in one check.

See `README.md` and `care_maternal_fe/README.md` for the full list of known issues.

## 6. Stop

```bash
.agent/compose.sh down        # stops this stack; keeps data (never add -v without approval)
```

Stop the two `npm run dev` and `frontend.sh` terminals with Ctrl+C.
