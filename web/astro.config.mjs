// @ts-check
import react from "@astrojs/react";
import { defineConfig } from "astro/config";

// Fully static; the one server route is a plain Vercel Function in web/api/email.ts.
export default defineConfig({
  site: process.env.SITE_URL ?? "https://neem-lemon.vercel.app",
  integrations: [react()],
  server: { port: 4321 },
  devToolbar: { enabled: false },
});
