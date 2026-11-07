import type { PropsWithChildren } from "react";

import "@/style/index.css";

/**
 * Scopes this plugin's Tailwind under one class so its styles cannot leak into the host.
 * `display: contents` keeps the wrapper out of the host's layout flow.
 * Wrap every root this plugin renders.
 */
export default function Page({ children }: PropsWithChildren) {
  return (
    <div className="care-maternal-container" style={{ display: "contents" }}>
      {children}
    </div>
  );
}
