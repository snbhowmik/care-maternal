# Demo script: a patient escalated from a rural hospital to a district hospital

Synthetic data only. Not for clinical use. The clinical wording is pending clinician review.
For the full feature walkthrough see `DEMO.md`.

## What is running

Two separate CARE instances on one EC2 server (`13.200.255.164`), each with the `care_maternal` plugin.
They are public through named Cloudflare tunnels on the `ccoogo.co` domain.

| | Hospital A | Hospital B |
|---|---|---|
| Name | Rural PHC Alpha (refers) | District Hospital Beta (receives) |
| App | https://hospital-a.ccoogo.co | https://hospital-b.ccoogo.co |
| API | https://api-hospital-a.ccoogo.co | https://api-hospital-b.ccoogo.co |
| Plugin files | https://plugin-hospital-a.ccoogo.co | https://plugin-hospital-b.ccoogo.co |
| Plugin files, scribe | `.../eka/assets/remoteEntry.js` on the same host | same |
| On the server (loopback) | frontend 18417, API 18416, plugin 18418 | frontend 28417, API 28416, plugin 28418 |

The hospitals refer to each other over a private Docker network (`hospital-link`), not over the internet:
A calls `http://hospital-b-backend:9000` and B calls `http://hospital-a-backend:9000`, each with a bearer token.
The tunnels run as systemd services (`cloudflared-hospital-a`, `cloudflared-hospital-b`), with their tokens in
root-only files under `/etc/cloudflared/`.

- **Logins:** `care-doctor` and `care-admin` at each hospital. The passwords are in a private file on the
  laptop (`~/.config/care-clinic/demo-hospital-logins.txt`), not in this document.
- **Eka Care:** the client ID and secret are in `~/hospital-{a,b}/.agent/eka.env` (mode 600) on the server.
- The demo SMS endpoint is off on both hospitals. Patient login uses CARE's fixed dev code `45612`.
- The first page load takes up to a minute (development server). Access is not behind a login wall in front of
  the tunnels; add Cloudflare Access before any real use.
- Cloudflare caches plugin files in browsers for 4 hours. Press Ctrl+Shift+R after a deploy, or set Browser Cache
  TTL to "Respect Existing Headers".

## Deploy a change (from the laptop)

```bash
KEY=~/Downloads/thinkpad.pem; H=ubuntu@13.200.255.164
for h in hospital-a hospital-b; do
  rsync -az -e "ssh -i $KEY" --exclude node_modules --exclude dist care_maternal_fe/ $H:/home/ubuntu/$h/care_maternal_fe/
  rsync -az -e "ssh -i $KEY" --exclude __pycache__ --exclude '*.egg-info' care/care_maternal/ $H:/home/ubuntu/$h/care/care_maternal/
done
ssh -i $KEY $H 'for h in hospital-a hospital-b; do
  cd ~/$h && ./.agent/compose.sh exec -T backend python manage.py migrate care_maternal
  ./.agent/compose.sh restart backend celery
  cd ~/$h/care_maternal_fe && npx vite build
done'
```

Notes: the Eka scribe is built into `dist/eka` (`npx vite build --base /eka/ --outDir ../care_maternal_fe/dist/eka`
in `care_eka_scribe_fe`); a plugin build keeps it because `emptyOutDir` is false. Both CARE frontends read
`REACT_ENABLED_APPS` from `.agent/frontend.env` at start, so changing it needs `.agent/frontend.sh` restarted.

## The three stories

Use any patient registered in the UI, enrolled with an LMP, at hospital A.

### Routine care
Show the schedule, mark one check done, book a visit from the calendar (see `DEMO.md` section 4).

### A handover that completes
On A, in **Refer to another hospital**: choose District Hospital Beta, give a reason, **Create referral**,
**Record consent**, **Send**. On B, **Referrals received**: **Acknowledge**, write the findings, **Record examination**.
On A the referral shows "Patient examined" with its timeline. B now holds the patient with the Maternal tag.

### An escalation
Send a referral that B does not acknowledge. The deadline is 24 hours; to expire it for the demo, on the server:
`~/hospital-a/.agent/compose.sh exec -T backend python manage.py demo_expire_handover <referral id>` (demo only,
refused in production). Within 5 minutes A shows "Handover incomplete: deadline passed" with a clinician alert.
Choose **Record check**, **Refer again** (a new referral to the hospital you pick, with new consent), or
**Manage here** (the plan is recorded and the clinician alerted).

## Known limits (say these out loud)

- **No test data is preloaded.** The synthetic patients were removed. Register patients in the UI; patients made
  through the API do not appear on the hospital's lists.
- **Any logged-in staff member at hospital B can acknowledge or examine any inbound referral.** Acknowledging links
  that doctor to the patient. Scope the inbox to the facility before real use.
- **Consent is recorded as text** ("by: patient"). A patient-side consent endpoint exists; its portal screen is not built.
- **SMS is console only.** Nothing reaches a real phone.
- **Development servers.** The frontends run Vite's dev server, not a production build.
- **Public access has no login wall** in front of the tunnels.
- **Passwords and fixed codes** in a private file and `45612` are for this test only.

## Checks that were run

- 96 backend tests pass (schedule, services and API, referrals, tags, booking, no-show, registrar link, access,
  Eka token, check list, reminders), on the laptop and on hospital A's server.
- A two-hospital HTTP test (`.agent/e2e/handover_two_hospitals.py`) passed 19 of 19 checks across the two instances.
- Browser checks on the public hostnames (Playwright scripts in `.agent/e2e/`) for the worklist, the patient panel,
  the check list, the duty and reminders cards, and the referral inbox, with no page errors.
- Not checked in a browser: clicking through the booking calendar, the no-show buttons, the late-enrolment review
  actions, and a real Eka scribe recording.
