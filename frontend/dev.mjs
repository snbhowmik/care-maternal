// Build once, then serve the built files. shortcut: no watch build. The watch build drops the
// federation expose modules (scaffold issue #6). Rebuild with `npm run build` after edits.
import { build, preview } from "vite";

await build();
const server = await preview();
console.log("care_maternal_fe serving built remote on", server.resolvedUrls?.local?.[0] ?? "http://127.0.0.1:29418");

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.once(signal, () => {
    server.httpServer.close();
    process.exit(0);
  });
}
