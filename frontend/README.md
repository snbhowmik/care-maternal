# Care Maternal (frontend)

Pregnancy-to-postpartum care pathway for rural clinics. MVP demo, not the real app, and not
for clinical use.

A [care_fe](https://github.com/ohcnetwork/care_fe) plugin, loaded at runtime through Vite
Module Federation. It is a separate build and never imports from `care_fe`. This directory is an
independent Git repository with no commits or remote yet.

## What is built

A staff page inside a facility, reached from the facility sidebar ("Maternal care").

- **Pick a patient** by CARE patient ID (`?patient=<id>` keeps it in the URL).
- **Create a pregnancy** from the LMP and obstetric history (G/P/A/L).
- **Pregnancy header**: gestational age, EDD, and obstetric history.
- **Schedule**: items grouped as overdue, due, upcoming, waiting and done. Each open item has
  a date box and a "Mark done" button. Completing Td-1 moves Td-2's due date.
- **Emergency report**: tick symptoms, then report. Raises a clinician alert and a patient SMS.
- **Overdue check**: runs the backend sweep and reports how many new alerts were raised.
- **Alerts**: every alert for the pregnancy, labelled by audience, with "(SMS sent)" where relevant.

The backend (`care_maternal`) does all the rules and permission checks. The page only calls it.

## Develop

```bash
npm install
npm run build      # typecheck and bundle
npx vite preview --host 127.0.0.1 --port 29418 --strictPort   # serves dist/ for the host
```

Enable it in the host through its external environment file (never edit core):

```text
REACT_ENABLED_APPS='ohcnetwork/care_maternal_fe@localhost:29418/assets/remoteEntry.js'
```

Then restart the host with `.agent/frontend.sh`. After rebuilding the plugin, hard-reload the
host browser tab. There is no hot reload across the federation boundary.

**Use `npm run build` plus `vite preview`, not `npm run dev`.** See known issue 1.

## Known issues

1. **`npm run dev` serves a broken remote.** Its watch build leaves a template placeholder
   (`${__federation_expose_./manifest}`) in `remoteEntry.js`, so the host cannot load the
   plugin. `npm run build` is clean. The dev script needs fixing before it is used.
2. **`minify: true` breaks the remote.** The scaffold template enables minification, and
   that breaks `@originjs/vite-plugin-federation` 1.4.1. `vite.config.ts` sets `minify: false`
   to work around it. Upgrade the plugin, or re-check this, before relying on minified builds.
3. **No patient-facing React page.** The host has no full-page surface for patients. The
   patient portal is a plain HTML demo page in the backend (`/api/care_maternal/portal/`).
4. **No worklist across patients.** The page shows one patient at a time. A "due this week"
   list needs a backend list endpoint first.
5. **Patient picked by ID.** Staff must paste a patient UUID. A name search is needed.
6. **Text is not translated.** The page uses plain English. The `maternal__` keys in
   `public/locale/en.json` are not used yet.
7. **No alert acknowledgement.** The backend cannot close alerts, so the page cannot either.
8. **Two cards per patient show the same emergency panel.** Each pregnancy has its own panel,
   so the "Report emergency" button must be pressed on the right card.
9. **Plain elements, not the CARE component library.** Native inputs and buttons in CARE's
   colours, not shadcn/ui. Radix dialogs were avoided, so no portal scoping is needed yet.
10. **Overdue items are shown as overdue for old LMPs** (for example 14 weeks with booking
    tests due by the 13+6 window). This is correct under the spec and shows the clinician
    what is outstanding.

## Structure

| Path | Purpose |
| --- | --- |
| `src/manifest.tsx` | The only module federation exposes. Route, nav item. |
| `src/pages/MaternalPage.tsx` | Picks a patient, lists pregnancies, creates one. |
| `src/components/PregnancyCard.tsx` | Schedule, "Mark done", emergency, overdue check, alerts. |
| `src/components/CreatePregnancy.tsx` | New-pregnancy form. |
| `src/utils/api.ts` | Staff API client. Uses the host's staff token and `CARE_API_URL`. |
| `src/types.ts` | Response types and the emergency symptom list. |
| `src/components/Page.tsx` | Tailwind scoping wrapper. |
| `src/style/index.css` | CARE palette, scoped to `.care-maternal-container`. |
| `src/main.tsx` | Standalone harness. The host never loads it. |

## Rules for this plugin

- Work only in this repo. Do not edit CARE core or its configuration.
- Use synthetic patients and phone numbers only.
- No clinical rule or patient-facing text goes live until a clinician signs off the spec.
