// @ts-check
import react from "@astrojs/react";
import vercel from "@astrojs/vercel";
import { defineConfig } from "astro/config";

// Pages are prerendered; only /api/email runs as a function (it opts out of prerendering).
export default defineConfig({
  site: process.env.SITE_URL ?? "https://neem.vercel.app",
  output: "static",
  adapter: vercel(),
  integrations: [react()],
  server: { port: 4321 },
  devToolbar: { enabled: false },
});
