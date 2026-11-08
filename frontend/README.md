# care_maternal_fe (frontend)

The staff screens for the `care_maternal` backend plugin. MVP demo: **synthetic data only, not for
clinical use.**

A [care_fe](https://github.com/ohcnetwork/care_fe) plugin, loaded at runtime through Vite Module
Federation. It is a separate build and never imports from `care_fe`. The backend does all the rules and
permission checks; this app only calls it.

## What it adds to CARE

| Where | What |
|---|---|
| Patient search (`PatientSearchActions`) | a **Maternal care** button with the number of tagged patients |
| Patient Home (`PatientHomeQuickActions`) | the **Maternal checks** panel: enrol, history, review of earlier checks, schedule, booking, no-show, home visits, referrals, alerts |
| `/facility/:id/maternal` (nav: Maternal care) | the worklist of tagged patients, the **On duty** switch, and **Your reminders** |
| `/facility/:id/maternal-checks` (nav: Maternal check list) | the no-code check list editor, with priority |
| `/facility/:id/maternal-inbox` (nav: Referrals received) | the inbox to acknowledge and examine incoming referrals |

A patient row opens the CARE patient page; the **Patient Home** button there shows the panel. (CARE's
own Patient Home address carries the phone number and birth year, so this plugin does not build links to it.)

### The panel, per patient
- **Enrol** from the LMP and G/P/A/L when there is no pregnancy.
- **Checks made** (X of Y, optional and not-needed checks left out) with the history.
- **Review earlier checks**: for a patient who enrols late, tick the overdue checks she has already had
  and mark them done elsewhere or not needed, with a note.
- **Schedule** grouped as Overdue, Due, Upcoming, Waiting, Done, Done elsewhere, Not needed. Only Overdue
  and Due are open by default. Each check shows its kind and priority, and has Mark done, Book visit
  (an inline calendar and the day's slots), No-show, and **Not done here** (done elsewhere or not needed).
- **Add a check for this patient** with a priority.
- **Home visits** raised after three no-shows, with the address.
- **Referrals** to the other hospital: consent, send, escalation, timeline.
- **Emergency symptoms** and the latest five alerts.

## UI: CARE UI

Every screen is built on [CARE UI](https://github.com/ohcnetwork/careui) (`ohcnetwork/careui`).
- Components are pulled from the registry into `src/components/careui/` (see `components.json`, registry
  `@careui`). Install one with `npx shadcn@latest add @careui/<name>`.
- The light theme is `src/style/careui-theme.css`, generated from careui's `src/index.css` and scoped to
  `.care-maternal-container`, so it cannot restyle the host. It also repeats the token mappings on the
  container, because Tailwind emits them on `:root`, where the scoped variables do not exist.
- **Popover, Select and Dialog are not used.** They render outside the plugin's styled area and would
  appear unstyled. Choices use button groups, and the booking calendar is inline.

## Develop

```bash
npm install
npm run build                      # type-check and bundle
npx tsc --noEmit -p .              # type-check only
npx vite preview --host 127.0.0.1 --port 29418 --strictPort   # serve dist/ for the host
```

Enable it in the host through its environment file (never edit core):

```text
REACT_ENABLED_APPS='ohcnetwork/care_maternal_fe@localhost:29418/assets/remoteEntry.js'
```

Several plugins are comma separated (the Eka scribe is a second entry). After rebuilding, hard-reload the
host tab (Ctrl+Shift+R); there is no hot reload across the federation boundary.

**Use `npm run build` plus `vite preview`, not `npm run dev`** (its watch build leaves an unreplaced
placeholder in `remoteEntry.js`). `vite.config.ts` also sets:
- `minify: false`, because minify breaks `@originjs/vite-plugin-federation` 1.4.1;
- `emptyOutDir: false`, so earlier chunks stay and a cached `remoteEntry.js` still loads (the Eka scribe
  also lives in `dist/eka`, which a clean build would delete);
- `preview.headers: Cache-Control: no-cache`.

**Caching:** Cloudflare sets a 4 hour browser cache on plugin files, overriding the server header. Set
Browser Cache TTL to "Respect Existing Headers" for the zone, or users keep an old copy after a deploy.

## Structure

| Path | Purpose |
|---|---|
| `src/manifest.tsx` | the only module federation exposes: routes, nav items, extension points |
| `src/pages/MaternalPage.tsx` | worklist, on-duty card, reminders |
| `src/pages/CheckListPage.tsx` | the check list editor |
| `src/pages/InboxPage.tsx` | referrals received |
| `src/components/PatientMaternalPanel.tsx` | the Patient Home panel |
| `src/components/PregnancyCard.tsx` | schedule, emergency, alerts; uses the components below |
| `src/components/{CreatePregnancy,ReviewEarlier,CloseCheck,AddCheck,BookVisit,HomeVisits,Referrals,PriorityPicker,DutyCard,RemindersCard,MaternalSearchLink}.tsx` | the pieces |
| `src/components/careui/` | CARE UI components (generated from the registry) |
| `src/utils/api.ts` | staff API client: the host's token and `CARE_API_URL`; `currentFacilityId()` |
| `src/types.ts` | response types, priorities, check kinds |
| `src/components/Page.tsx` | styling scope wrapper (wrap every root this plugin renders) |
| `src/style/` | `index.css` and the generated `careui-theme.css` |

## Known limits

1. No patient-facing React page: the host has no full-page surface for patients. The patient portal is a
   plain HTML page served by the backend.
2. The worklist links to the patient page, not straight to the Patient Home (see above).
3. English only. The `maternal__` keys in `public/locale/en.json` are not used yet.
4. The booking calendar lists 09:00 to 17:00 in 15 minute slots; there is no per-doctor working-hours setup.
5. CARE's patient search does not draw tags on result rows, so the tag shows on the patient page and in
   the worklist, not in search results.

## Rules for this plugin

- Work only in this repo. Do not edit CARE core or its configuration.
- Use synthetic patients and phone numbers only.
- No clinical rule or patient-facing text goes live until a clinician signs off the spec.
