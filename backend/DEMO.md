# Test runbook: Care Maternal (MVP)

Synthetic data only. Not for clinical use. Use this to try every feature on the live hospitals.

| | Hospital A: Rural PHC Alpha (refers) | Hospital B: District Hospital Beta (receives) |
|---|---|---|
| App | https://hospital-a.ccoogo.co | https://hospital-b.ccoogo.co |
| API | https://api-hospital-a.ccoogo.co | https://api-hospital-b.ccoogo.co |
| Facility | FACILITY WITH PATIENTS (`70429f2a-8b2e-458f-ac6e-66c6fd2bd8e5`) | FACILITY WITH PATIENTS (`5d48f127-106e-4d73-933c-c6220c0da91f`) |

**Logins** are in a private file on the laptop (`~/.config/care-clinic/demo-hospital-logins.txt`), never in
this repo: `care-doctor` (a Doctor), `care-admin` (Facility Admin), at each hospital.

Before you start: press **Ctrl+Shift+R** to clear a cached copy of the plugin. The first page load can sit on
"LOADING..." for up to a minute (the development server is preparing its files).

## 1. Register and enrol

1. Patients → **Add New Patient** and fill in the form. Register in the UI, not through the API: patients made
   through the API do not appear on the hospital's lists. The **State** list should show every state.
2. You land on the patient page. Press **Patient Home** (under Actions on the right) and scroll to **Maternal checks**.
3. Enter an LMP (for example 20 weeks ago) and press **Create pregnancy**.
4. Check: the profile shows the **Maternal** tag; Patients → **Maternal care** lists the patient.

## 2. A patient who enrols late

The patient's overdue checks appear in a box: "N earlier checks are overdue". Ask the patient which she has
had. Tick them and press **Had these elsewhere** (add where, if known) or **Not needed** (a reason is
required). Each check also has **Not done here** for one at a time. **Reopen** undoes it. Closed checks stop
counting as overdue.

## 3. The check list (doctors and facility admins)

Left menu → **Maternal check list**. Add a check (by weeks of pregnancy, after another check, or the doctor
sets the date), set its **priority**, edit it, or turn it off with the switch. It applies to patients enrolled
from now on. Nurses can read the list but not change it. On one patient, use **Add a check for this patient**.

## 4. Book, no-show, home visit

1. **Book visit** on a check: pick a date on the calendar and a time. Taken times are disabled. The check
   shows an **Appointment** badge; the patient's **Appointments** tab lists it.
2. **No-show** turns it back into a due check. After three no-shows on one check a **Home visits** box appears
   with the patient's address (unassigned unless an `ASHA Worker` is set up).
3. Automatic: book a time that has already passed today (at least 30 minutes ago). Within about 5 minutes it is
   marked no-show.

## 5. Priority, reminders and duty

Maternal care page: switch **On duty**. Reminders go to everyone on duty (and to the whole team if nobody is).
Set a check to **High** on the check list, or add one for a patient, and watch **Your reminders** (the sweep runs
every 15 minutes, 08:00 to 20:00). Rules: high 3 days early, up to 3 a day; medium 1 day early, twice a day; low
once, on the due date; optional never (and never keeps the tag). **Mark seen** closes a reminder.

## 6. Refer to hospital B

1. On hospital A, in the patient card: **Refer to another hospital**, choose District Hospital Beta, give a reason,
   **Create referral**, **Record consent**, **Send**.
2. On hospital B, left menu → **Referrals received**: **Acknowledge**, write the findings, **Record examination**.
3. Back on A the referral says "Patient examined", with a timeline. B now shows the patient with the Maternal tag.
4. Escalation: if B does not acknowledge within 24 hours the referral becomes "Handover incomplete" and A can
   record a check, refer again, or manage the patient here. To expire a referral for a demo, on the server run
   `~/hospital-a/.agent/compose.sh exec -T backend python manage.py demo_expire_handover <referral id>`.

## 7. Eka Care scribe

Patient Home → **Create Encounter** → open a questionnaire form (for example Vitals) → **AI Scribe**. Allow the
microphone, talk, **Stop and process**, and review the filled fields before submitting. The scribe asks CARE for a
30 minute token; the Eka secret stays on the server.

## 8. Facility settings

Log in as `care-admin` and open the facility's settings: the details can be edited.

## 9. Check it from a terminal

```bash
.agent/compose.sh exec -T backend python manage.py test \
  care_maternal.tests.test_schedule care_maternal.tests.test_services_api care_maternal.tests.test_referrals \
  care_maternal.tests.test_tags care_maternal.tests.test_booking care_maternal.tests.test_no_show \
  care_maternal.tests.test_registrar_link care_maternal.tests.test_access care_maternal.tests.test_eka \
  care_maternal.tests.test_check_list care_maternal.tests.test_reminders       # 96 tests
(cd care_maternal_fe && npx tsc --noEmit -p . && npm run build)
```

## Say these out loud

- The pathway is approved by the doctor partner, but the approval is not recorded in the spec file and open questions Q1 to Q7 are not recorded as answered. No clinical validation yet.
- Every check is `medium` until a clinician sets priorities; reminder timings are defaults.
- SMS is console only. Nothing reaches a real phone.
- Patient login uses CARE's fixed dev code `45612` on non-production stacks. All patients are synthetic.
- Any staff member at the receiving hospital can acknowledge an inbound referral.
- Districts are not loaded; the address list has states and union territories only.
