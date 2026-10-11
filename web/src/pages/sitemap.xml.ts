import type { APIRoute } from "astro";
import twins from "../data/twins.json";

export const GET: APIRoute = ({ site }) => {
  const base = site ?? new URL("https://neem-lemon.vercel.app");
  const paths = ["/", "/story", "/method", "/docs", ...twins.map((t) => `/school/${t.school_id}`)];
  const urls = paths
    .map((p) => `  <url><loc>${new URL(p, base).toString()}</loc></url>`)
    .join("\n");
  const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls}
</urlset>
`;
  return new Response(body, { headers: { "content-type": "application/xml" } });
};
