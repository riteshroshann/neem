import type { Grid, HourModel } from "./physics";

export interface HourMeta {
  time: string;
  ta: number;
  rh: number;
  global_rad: number;
  ws: number;
}

export interface Exposure {
  utci_mean: number;
  utci_peak_hour_mean: number;
  extreme_fraction: number;
  very_strong_fraction: number;
  shade_fraction: number;
  tmrt_mean: number;
  ground_m2: number;
}

export interface TwinSummary {
  school_id: string;
  name: string;
  day: string;
  site: { latitude: number; longitude: number; altitude: number };
  grid: Grid & { crs: string };
  hours: HourMeta[];
  exposure: Exposure;
  quality: {
    buildings: number;
    with_height: number;
    canopy_cover: number;
    height_coverage: number;
  };
  calibration_mae_changed: number[];
  timings: { base: { total_s: number }; total_s: number };
  layers: { name: string; count: number; scale: number; offset: number }[];
  height_ref: number;
}

export interface ChildDay {
  minutes: number[];
  rise: number[];
  core_display: number[];
  water_ml: number[];
  labels: string[];
  peak_rise: number;
  total_water_ml: number;
  minutes_strained: number;
}

export interface Twin {
  summary: TwinSummary;
  dsm: Float32Array;
  dem: Float32Array;
  cdsm: Float32Array;
  svf: Float32Array;
  zones: Uint8Array;
  tmrt: Float32Array[];
  utci: Float32Array[];
  hours: HourModel[];
  child: { morning: ChildDay; afternoon: ChildDay };
}

function decode(buf: ArrayBuffer, cells: number, offset: number, scale: number): Float32Array {
  const raw = new Int16Array(buf, offset, cells);
  const out = new Float32Array(cells);
  for (let i = 0; i < cells; i++) out[i] = (raw[i] as number) / scale;
  return out;
}

export async function loadTwin(id: string, base = "/twins"): Promise<Twin> {
  const root = `${base}/${id}`;
  const [summary, cal, child, bin] = await Promise.all([
    fetch(`${root}/twin.json`).then((r) => r.json() as Promise<TwinSummary>),
    fetch(`${root}/calibration.json`).then((r) => r.json() as Promise<{ hours: HourModel[] }>),
    fetch(`${root}/child.json`).then((r) => r.json() as Promise<Twin["child"]>),
    fetch(`${root}/layers.bin`).then((r) => r.arrayBuffer()),
  ]);
  const cells = summary.grid.rows * summary.grid.cols;
  const layer = (name: string) => {
    const l = summary.layers.find((x) => x.name === name);
    if (!l) throw new Error(`layer ${name} missing`);
    return l;
  };
  const single = (name: string) => {
    const l = layer(name);
    return decode(bin, cells, l.offset, l.scale);
  };
  const stack = (name: string) => {
    const l = layer(name);
    return Array.from({ length: l.count }, (_, k) =>
      decode(bin, cells, l.offset + k * cells * 2, l.scale),
    );
  };
  const zonesF = single("zones");
  return {
    summary,
    dsm: single("dsm"),
    dem: single("dem"),
    cdsm: single("cdsm"),
    svf: single("svf"),
    zones: Uint8Array.from(zonesF, (v) => Math.round(v)),
    tmrt: stack("tmrt"),
    utci: stack("utci"),
    hours: cal.hours,
    child,
  };
}

/** Mean over school ground cells. */
export function groundMean(values: Float32Array, zones: Uint8Array): number {
  let sum = 0;
  let n = 0;
  for (let i = 0; i < values.length; i++) {
    if (zones[i] === 1) {
      sum += values[i] as number;
      n++;
    }
  }
  return n ? sum / n : Number.NaN;
}

/** Share of ground cells in each UTCI band, given ascending lower bounds. */
export function bandShares(values: Float32Array, zones: Uint8Array, bounds: number[]): number[] {
  const counts = new Array(bounds.length).fill(0) as number[];
  let n = 0;
  for (let i = 0; i < values.length; i++) {
    if (zones[i] !== 1) continue;
    n++;
    const v = values[i] as number;
    let k = 0;
    for (let b = 0; b < bounds.length; b++) if (v >= (bounds[b] as number)) k = b;
    counts[k] = (counts[k] ?? 0) + 1;
  }
  return counts.map((c) => (n ? c / n : 0));
}

export function hourLabel(iso: string): string {
  const h = Number(iso.slice(11, 13));
  const suffix = h < 12 ? "am" : "pm";
  return `${h % 12 === 0 ? 12 : h % 12} ${suffix}`;
}
