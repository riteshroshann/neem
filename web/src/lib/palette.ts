import palette from "../data/palette.json";

export interface Stop {
  utci: number;
  hex: string;
}

/** A UTCI heat-stress category: lower bound (null for the open bottom), name and a ramp colour. */
export interface Band {
  min: number | null;
  name: string;
  hex: string;
}

export const STOPS: Stop[] = palette.stops;
export const BANDS: Band[] = palette.bands;

function hexToRgb(hex: string): [number, number, number] {
  return [
    Number.parseInt(hex.slice(1, 3), 16),
    Number.parseInt(hex.slice(3, 5), 16),
    Number.parseInt(hex.slice(5, 7), 16),
  ];
}

/** Map drawing, shared with the 1 pm PNGs so swapping in the live canvas never flashes. */
export const MAP: {
  schoolRoof: [number, number, number];
  nearbyRoof: [number, number, number];
  outsideAlpha: number;
  tallM: number;
} = {
  schoolRoof: hexToRgb(palette.map.school_roof),
  nearbyRoof: hexToRgb(palette.map.nearby_roof),
  outsideAlpha: palette.map.outside_alpha,
  tallM: palette.map.tall_m,
};

const RGB = STOPS.map((s) => hexToRgb(s.hex));

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

/** Name of the UTCI heat-stress band a value falls in, exactly like palette.band. */
export function band(utci: number): string {
  let name = BANDS[0]?.name ?? "";
  for (const b of BANDS) if (b.min !== null && utci >= b.min) name = b.name;
  return name;
}
