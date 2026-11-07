import { lazy } from "react";

import Page from "./components/Page";
import InboxPage from "./pages/InboxPage";
import MaternalPage from "./pages/MaternalPage";

/**
 * The only module the host loads (Module Federation). Keep it light: no heavy imports here.
 * Structural mirror of the host's NavigationLink; the host type is not importable across builds.
 */
interface NavigationLink {
  url: string;
  name: string;
}

interface Manifest {
  plugin: string;
  routes: Record<string, () => React.ReactNode>;
  components: Record<string, React.ComponentType<never>>;
  extends: string[];
  navItems: NavigationLink[];
}

const manifest: Manifest = {
  plugin: "care_maternal_fe",
  routes: {
    // Facility-scoped page (the sidebar link lives under the selected facility).
    "/facility/:facilityId/maternal": () => (
      <Page>
        <MaternalPage />
      </Page>
    ),
    "/facility/:facilityId/maternal-inbox": () => (
      <Page>
        <InboxPage />
      </Page>
    ),
  },
  components: {
    // Staff patient home: checks made so far and the schedule, for every patient.
    PatientHomeQuickActions: lazy(() => import("./components/PatientMaternalPanel")),
    // Staff patient search: a way into the Maternal worklist, where tagged patients are listed.
    PatientSearchActions: lazy(() => import("./components/MaternalSearchLink")),
  },
  extends: [],
  navItems: [
    { url: "maternal", name: "Maternal care" },
    { url: "maternal-inbox", name: "Referrals received" },
  ],
};

export default manifest;
