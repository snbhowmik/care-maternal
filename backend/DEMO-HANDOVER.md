# Demo script: a patient escalated from a rural hospital to a district hospital

Synthetic data only. Not for clinical use. The clinical wording is pending clinician review.

## What is running

Both hospitals are separate CARE instances on one server (13.200.255.164), each with the
care_maternal plugin:

| | Hospital A | Hospital B |
|---|---|---|
| Name | Rural PHC Alpha (refers) | District Hospital Beta (receives) |
| Frontend | 127.0.0.1:18417 | 127.0.0.1:28417 |
| API | 127.0.0.1:18416 | 127.0.0.1:28416 |
| Plugin files | 127.0.0.1:18418 | 127.0.0.1:28418 |

They talk to each other over a private Docker link (`hospital-link`). Nothing is published to
the internet. The ports listen on the server's loopback address only.

## Public access (live now)

Both hospitals are reachable from the internet through Cloudflare quick tunnels:

| | Hospital A (Rural PHC Alpha) | Hospital B (District Hospital Beta) |
|---|---|---|
| Open the app | https://moss-juan-older-refinance.trycloudflare.com | https://electro-equally-dial-linear.trycloudflare.com |
| API | https://elliott-boston-spent-struggle.trycloudflare.com | https://encoding-performances-provides-identifies.trycloudflare.com |

- Quick-tunnel addresses change if the tunnels or the server restart. Ask for the current ones.
- Logins: `care-doctor` and `care-admin` at each hospital. The passwords are in a private file on
  the laptop: `~/.config/care-clinic/demo-hospital-logins.txt`. They are not in this document.
- The demo SMS endpoint is off on both public hospitals. The fixed patient login code `45612`
  still works, because it is built into CARE for non-production stacks. All patients are synthetic.
- The first page load takes one to two minutes (the development server builds its files).
- Access is not gated by a login wall in front of the tunnels. Add Cloudflare Access before real use.

## Private access (fallback)

```bash
ssh -i ~/Downloads/thinkpad.pem -N \
  -L 18416:127.0.0.1:18416 -L 18417:127.0.0.1:18417 -L 18418:127.0.0.1:18418 \
  -L 28416:127.0.0.1:28416 -L 28417:127.0.0.1:28417 -L 28418:127.0.0.1:28418 \
  ubuntu@13.200.255.164
```

Then open http://localhost:18417 (Hospital A) and http://localhost:28417 (Hospital B).

## How to open the demo from your laptop (private, via SSH)

```bash
ssh -i ~/Downloads/thinkpad.pem -N \
  -L 18416:127.0.0.1:18416 -L 18417:127.0.0.1:18417 -L 18418:127.0.0.1:18418 \
  -L 28416:127.0.0.1:28416 -L 28417:127.0.0.1:28417 -L 28418:127.0.0.1:28418 \
  ubuntu@13.200.255.164
```

Then open:
- Hospital A: http://localhost:18417
- Hospital B: http://localhost:28417

Log in as `care-doctor` (password in the private file above).

Facility: "FACILITY WITH PATIENTS" on both hospitals (from the CARE fixtures).

## The three patients (at Hospital A)

| Patient | Story | Patient ID |
|---|---|---|
| SYNTHETIC Anita (routine) | Routine antenatal care. No referral. | `ed9887c2-6a74-4a01-a09f-36e612b6261b` |
| SYNTHETIC Lakshmi (handover) | Referred to District Hospital Beta. Consent given, acknowledged, examined. | `7755ae63-5d03-4238-aeee-ed0c0c99d4b3` |
| SYNTHETIC Meena (escalation) | Referred. District Hospital Beta never acknowledges. Deadline passes. Rural PHC refers again. | `e44d4312-a641-4f6f-be52-8f50da3f6f3b` |

Open a patient: Hospital A, then "Maternal care", then paste the ID in the box, then "Open".

## Scene 1: routine care (Anita, 2 minutes)

1. Show the pregnancy header: gestational age, EDD, G/P/A/L.
2. Show the schedule grouped as overdue, due, upcoming, waiting and done.
3. Click "Book visit" on a visit. It becomes a real CARE appointment, which the patient
   sees under Appointments with its date and time.

## Scene 2: a handover that completes (Lakshmi, 4 minutes)

On Hospital A, Lakshmi's pregnancy card, "Refer to another hospital":
1. Choose "District Hospital Beta". Write the reason. Press "Create referral".
2. Press "Record consent" (consent by: patient). A referral without consent cannot be sent.
3. Press "Send to District Hospital Beta".

On Hospital B (http://localhost:28417), "Referrals received":
4. The referral is listed with the patient's name and reason. Press "Acknowledge".
5. Write the examination findings and press "Record examination".

Back on Hospital A: the referral shows "Patient examined", and its timeline lists each step.

## Scene 3: an escalation (Meena, 5 minutes)

On Hospital A, Meena's pregnancy card:
1. Create the referral to District Hospital Beta, record consent, and send it.
2. Hospital B does not acknowledge. The deadline is 24 hours. For the demo, expire it:
   on the server, run
   `~/hospital-a/.agent/compose.sh exec -T backend python manage.py demo_expire_handover <referral id>`
   (demo only; refused in production). The sweep marks it incomplete within 5 minutes, or run
   "Run overdue check" in the maternal page.
3. Hospital A now shows "Handover incomplete: deadline passed", with a clinician alert.
4. Choose a next step:
   - "Record check": write what you found on the phone call with the family.
   - "Refer again": choose the hospital, write the reason, then record consent again and send.
   - "Manage here": write the plan. The clinician is alerted.
5. The new referral appears in Hospital B's "Referrals received".

## Known limits (say these out loud)

- **Test data is already present.** A previous automated run moved these three patients
  through the flow, and Hospital B's inbox has duplicate test referrals. A clean demo needs a
  reset of both hospitals. That drops data, so it needs approval first.
- **Access is private only.** The hospitals are not on the internet. Public access needs
  approval and an access control layer (for example Cloudflare Access).
- **Any logged-in staff member at Hospital B can acknowledge or examine any inbound referral.**
  Acknowledging makes that doctor the patient's doctor. Scope the inbox to the facility before
  real use.
- **Consent is recorded as text** ("by: patient"). The patient-side consent endpoint exists;
  its portal screen is not built yet.
- **No automatic reminders to ASHA workers yet.** The deadline check is automatic (every
  5 minutes), but the ASHA home-visit reminder is not built.
- **SMS is console only.** Nothing reaches a real phone.
- **Development servers.** The frontends run Vite's dev server, not a production build.
- **Demo passwords and fixed codes** (`(see the private logins file)`, login code `45612`) are for this test only.

## Checks that were run

- `care_maternal` backend tests: 30 pass (schedule, services and API, handover).
- Two-hospital HTTP test (`handover_two_hospitals.py`): 19 of 19 checks pass across the two
  instances.
- Browser checks on the referral panel and the inbox: pass, with no page errors.
