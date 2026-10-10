import { Resend } from "resend";

// Without a verified domain Resend only delivers from its test sender to the account owner, so
// the recipient is fixed by configuration and never taken from the request.
const FROM = "Neem <onboarding@resend.dev>";

interface Plan {
  school_id: string;
  school: string;
  hour: string;
  today_utci: number;
  plan_utci: number | null;
  verified: boolean;
  trees: number;
  sails: number;
  cost_rs: number;
  child_today: { peak_rise: number; water_ml: number };
  child_plan: { peak_rise: number; water_ml: number } | null;
  url: string;
}

const num = (v: unknown, lo: number, hi: number): number | null =>
  typeof v === "number" && Number.isFinite(v) && v >= lo && v <= hi ? v : null;

const text = (v: unknown, max: number): string =>
  typeof v === "string" ? v.replace(/[<>]/g, "").slice(0, max) : "";

function parse(body: Record<string, unknown>): Plan | null {
  const school = text(body.school, 120);
  const id = text(body.school_id, 40);
  const today = num(body.today_utci, 0, 70);
  const childToday = body.child_today as Record<string, unknown> | undefined;
  const childPlan = body.child_plan as Record<string, unknown> | null | undefined;
  if (!school || !/^osm-[nwr]\d+$/.test(id) || today === null || !childToday) return null;
  const peak = num(childToday.peak_rise, -1, 5);
  const water = num(childToday.water_ml, 0, 5000);
  if (peak === null || water === null) return null;
  return {
    school_id: id,
    school,
    hour: text(body.hour, 8),
    today_utci: today,
    plan_utci: num(body.plan_utci, 0, 70),
    verified: body.verified === true,
    trees: num(body.trees, 0, 500) ?? 0,
    sails: num(body.sails, 0, 100) ?? 0,
    cost_rs: num(body.cost_rs, 0, 1e8) ?? 0,
    child_today: { peak_rise: peak, water_ml: water },
    child_plan:
      childPlan &&
      num(childPlan.peak_rise, -1, 5) !== null &&
      num(childPlan.water_ml, 0, 5000) !== null
        ? { peak_rise: childPlan.peak_rise as number, water_ml: childPlan.water_ml as number }
        : null,
    url: text(body.url, 300),
  };
}

function render(p: Plan): { subject: string; html: string } {
  const inr = new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  });
  const delta = p.plan_utci === null ? null : p.plan_utci - p.today_utci;
  const label = p.verified ? "verified by SOLWEIG" : "preview, not yet verified";
  const row = (k: string, v: string) =>
    `<tr><td style="padding:6px 16px 6px 0;color:#6b6b6b">${k}</td><td style="padding:6px 0">${v}</td></tr>`;
  const html = `
  <div style="font-family:Georgia,serif;color:#0a0a0a;max-width:560px">
    <p style="font-size:13px;color:#6b6b6b;font-family:Arial,sans-serif">Neem heat plan</p>
    <h1 style="font-weight:400;font-size:32px;line-height:1.1;margin:0 0 16px">${p.school}</h1>
    <table style="font-family:Arial,sans-serif;font-size:15px;border-collapse:collapse">
      ${row(`Grounds at ${p.hour}, today`, `${p.today_utci.toFixed(1)} °C feels-like`)}
      ${p.plan_utci === null ? "" : row("With this plan", `${p.plan_utci.toFixed(1)} °C (${delta && delta > 0 ? "+" : ""}${delta?.toFixed(1)} °C, ${label})`)}
      ${row("Changes", `${p.trees} trees, ${p.sails} shade sails, ${inr.format(p.cost_rs)}`)}
      ${row("Child core rise by 12:45", `+${p.child_today.peak_rise.toFixed(2)} °C today${p.child_plan ? `, +${p.child_plan.peak_rise.toFixed(2)} °C with the plan` : ""}`)}
      ${row("Water lost", `${Math.round(p.child_today.water_ml)} ml today${p.child_plan ? `, ${Math.round(p.child_plan.water_ml)} ml with the plan` : ""}`)}
    </table>
    <p style="font-family:Arial,sans-serif;font-size:13px;color:#6b6b6b;margin-top:24px">
      Modelled for Monday 27 April 2026 with SOLWEIG on open data. ${p.url ? `<a href="${p.url}" style="color:#0a0a0a">Open the twin</a>.` : ""}
    </p>
  </div>`;
  return { subject: `Heat plan: ${p.school}`, html };
}

/** Vercel Function (web handler signature): POST /api/email. */
export async function POST(request: Request): Promise<Response> {
  const key = process.env.RESEND_API_KEY;
  const to = process.env.RESEND_TO;
  if (!key || !to) return new Response("email is not configured", { status: 503 });
  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return new Response("expected JSON", { status: 400 });
  }
  const plan = parse(body);
  if (!plan) return new Response("invalid plan", { status: 422 });
  const { subject, html } = render(plan);
  const { error } = await new Resend(key).emails.send({ from: FROM, to, subject, html });
  if (error) return new Response(error.message, { status: 502 });
  return new Response(JSON.stringify({ sent: true }), {
    headers: { "content-type": "application/json" },
  });
}
