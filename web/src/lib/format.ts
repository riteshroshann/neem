// One way to write numbers: a no-break space before every unit, a true minus sign, en-IN rupees.

export const NBSP = " ";
const MINUS = "−";
const inr = new Intl.NumberFormat("en-IN");

const signed = (v: number, dp: number) => `${v < 0 ? MINUS : "+"}${Math.abs(v).toFixed(dp)}`;

export const temp = (v: number, dp = 1) => `${v.toFixed(dp).replace("-", MINUS)}${NBSP}°C`;

/** A rise above rest, always signed: "+0.93 °C". */
export const rise = (v: number, dp = 2) => `${signed(v, dp)}${NBSP}°C`;

/** A change against today; "No change" when it rounds to zero. */
export function delta(v: number, dp = 1): string {
  return Math.abs(v) < 0.5 * 10 ** -dp ? "No change" : `${signed(v, dp)}${NBSP}°C`;
}

export const ml = (v: number) => `${Math.round(v)}${NBSP}ml`;

export const pct = (v: number) => `${Math.round(v * 100)}%`;

export const rupees = (v: number) => `₹${inr.format(Math.round(v))}`;

/** Whole lakh read the way people say them: "₹3 lakh". */
export const lakh = (v: number) => (v % 100_000 === 0 ? `₹${v / 100_000}${NBSP}lakh` : rupees(v));

/** "27 April 2026" */
export const longDate = (day: string) =>
  new Date(`${day}T00:00:00Z`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });

/** OpenStreetMap names as a person would write them: title case if all lower, small "of". */
export function schoolName(raw: string): string {
  if (!raw.trim() || raw === "Unnamed school") return "Unnamed school";
  const titled = raw === raw.toLowerCase() ? raw.replace(/\b\p{L}/gu, (c) => c.toUpperCase()) : raw;
  return titled.replace(/(?<=\S )(Of|And|For|The)(?= )/g, (w) => w.toLowerCase());
}
