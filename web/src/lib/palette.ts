import stops from "../data/palette.json";

export interface Stop {
  utci: number;
  hex: string;
  band: string;
}

export const STOPS: Stop[] = stops;

const RGB = STOPS.map((s) => [
  Number.parseInt(s.hex.slice(1, 3), 16),
  Number.parseInt(s.hex.slice(3, 5), 16),
  Number.parseInt(s.hex.slice(5, 7), 16),
]);

/** UTCI to RGB, linear between stops and clamped at the ends, exactly like palette.colorize. */
export function heatRgb(utci: number): [number, number, number] {
  const first = STOPS[0];
  const last = STOPS[STOPS.length - 1];
  if (!first || !last) return [0, 0, 0];
  if (!(utci > first.utci)) return RGB[0] as [number, number, number];
  if (utci >= last.utci) return RGB[RGB.length - 1] as [number, number, number];
  for (let i = 1; i < STOPS.length; i++) {
    const hi = STOPS[i];
    const lo = STOPS[i - 1];
    if (hi && lo && utci < hi.utci) {
      const t = (utci - lo.utci) / (hi.utci - lo.utci);
      const a = RGB[i - 1] as number[];
      const b = RGB[i] as number[];
      return [0, 1, 2].map((k) => Math.round((a[k] ?? 0) + t * ((b[k] ?? 0) - (a[k] ?? 0)))) as [
        number,
        number,
        number,
      ];
    }
  }
  return RGB[RGB.length - 1] as [number, number, number];
}

export function heatHex(utci: number): string {
  return `#${heatRgb(utci)
    .map((v) => v.toString(16).padStart(2, "0"))
    .join("")}`;
}

/** Name of the UTCI heat-stress band a value falls in. */
export function band(utci: number): string {
  let name = STOPS[0]?.band ?? "";
  for (const s of STOPS) if (utci >= s.utci) name = s.band;
  return name;
}
