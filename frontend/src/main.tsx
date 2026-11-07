import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import Page from "./components/Page";
import MaternalPage from "./pages/MaternalPage";

/**
 * Standalone harness only. The host loads ./manifest, not this file.
 * Uses the staff token from localStorage, so sign in to CARE in the same browser first.
 */
window.CARE_API_URL ??= "http://localhost:29416";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Page>
      <MaternalPage />
    </Page>
  </StrictMode>,
);
