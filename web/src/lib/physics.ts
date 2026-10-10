/**
 * T0 in the browser: the same geometry and anchored delta model as neem_core.shadow and
 * neem_core.surrogate. A differential test pins this file to the Python on shared fixtures.
 */

export const CANOPY_TRANSMISSIVITY = 0.03;
export const TRUNK_RATIO = 0.25;
export const NEAR_CANOPY_CELLS = 5;
export const ZONE_GROUND = 1;
export const ZONE_BUILDING = 2;

export interface Grid {
  rows: number;
  cols: number;
  pixel_size: number;
  x0: number;
  y0: number;
}

export type Species = "neem" | "peepal" | "jamun" | "amaltas";

/** Height m, crown radius m, cost in rupees. Mirrors neem_core.interventions.SPECIES. */
export const SPECIES: Record<Species, { height: number; radius: number; cost: number }> = {
  neem: { height: 7.0, radius: 3.5, cost: 3500 },
  peepal: { height: 8.0, radius: 4.5, cost: 3500 },
  jamun: { height: 7.5, radius: 3.5, cost: 3500 },
  amaltas: { height: 6.0, radius: 3.0, cost: 3000 },
};

export const SAIL_COST_PER_M2 = 1800;
export const SAIL_HEIGHT = 4.0;

export interface Tree {
  kind: "tree";
  x: number;
  y: number;
  species: Species;
}

export interface Sail {
  kind: "sail";
  x: number;
  y: number;
  width: number;
  depth: number;
}

export type Intervention = Tree | Sail;

export function cost(items: Intervention[]): number {
  let total = 0;
  for (const it of items) {
    total +=
      it.kind === "tree"
        ? SPECIES[it.species].cost
        : Math.round(it.width * it.depth * SAIL_COST_PER_M2);
  }
  return total;
}

/** Fraction of the direct beam reaching each cell's surface (1 lit, 0 shaded). */
export function sunlitFraction(
  dsm: Float32Array,
  dem: Float32Array,
  cdsm: Float32Array,
  rows: number,
  cols: number,
  pixelSize: number,
  altitudeDeg: number,
  azimuthDeg: number,
  tau = CANOPY_TRANSMISSIVITY,
  trunkRatio = TRUNK_RATIO,
): Float32Array {
  const out = new Float32Array(rows * cols);
  if (altitudeDeg <= 0) return out;
  const alt = (altitudeDeg * Math.PI) / 180;
  const az = (azimuthDeg * Math.PI) / 180;
  let dc = Math.sin(az);
  let dr = -Math.cos(az);
  const scale = 1 / Math.max(Math.abs(dc), Math.abs(dr));
  dc *= scale;
  dr *= scale;
  const rise = scale * pixelSize * Math.tan(alt);

  let top = -Infinity;
  for (let i = 0; i < rows * cols; i++) {
    const h = Math.max(dsm[i] as number, (dem[i] as number) + (cdsm[i] as number));
    if (h > top) top = h;
  }

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const i = r * cols + c;
      const z0 = dsm[i] as number;
      let light = 1;
      const own = cdsm[i] as number;
      if (own > 0 && (dem[i] as number) + own * trunkRatio > z0 - 0.01) light = tau;
      let z = z0;
      let fr = r;
      let fc = c;
      for (;;) {
        fr += dr;
        fc += dc;
        z += rise;
        if (z > top) break;
        const rr = Math.floor(fr + 0.5);
        const cc = Math.floor(fc + 0.5);
        if (rr < 0 || rr >= rows || cc < 0 || cc >= cols) break;
        const j = rr * cols + cc;
        if ((dsm[j] as number) > z) {
          light = 0;
          break;
        }
        const ch = cdsm[j] as number;
        if (ch > 0) {
          const g = dem[j] as number;
          if (g + ch > z && g + ch * trunkRatio < z && tau < light) light = tau;
        }
      }
      out[i] = light;
    }
  }
  return out;
}

/** Canopy anywhere in a NEAR_CANOPY_CELLS square window, clipped at the edges. */
export function nearCanopy(cdsm: Float32Array, rows: number, cols: number): Uint8Array {
  const half = Math.floor(NEAR_CANOPY_CELLS / 2);
  const rowMax = new Uint8Array(rows * cols);
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      let any = 0;
      for (let k = Math.max(0, c - half); k <= Math.min(cols - 1, c + half) && !any; k++) {
        if ((cdsm[r * cols + k] as number) > 0) any = 1;
      }
      rowMax[r * cols + c] = any;
    }
  }
  const out = new Uint8Array(rows * cols);
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      let any = 0;
      for (let k = Math.max(0, r - half); k <= Math.min(rows - 1, r + half) && !any; k++) {
        if (rowMax[k * cols + c]) any = 1;
      }
      out[r * cols + c] = any;
    }
  }
  return out;
}

export interface Features {
  lit: Float32Array;
  near: Uint8Array;
}

export function features(
  dsm: Float32Array,
  dem: Float32Array,
  cdsm: Float32Array,
  grid: Grid,
  altitude: number,
  azimuth: number,
): Features {
  return {
    lit: sunlitFraction(dsm, dem, cdsm, grid.rows, grid.cols, grid.pixel_size, altitude, azimuth),
    near: nearCanopy(cdsm, grid.rows, grid.cols),
  };
}

/** Add trees and sails to a canopy layer. Mirrors neem_core.interventions.apply. */
export function applyDesign(
  cdsm: Float32Array,
  zones: Uint8Array,
  grid: Grid,
  items: Intervention[],
): Float32Array {
  const out = Float32Array.from(cdsm);
  const { rows, cols, pixel_size: px, x0, y0 } = grid;
  for (const it of items) {
    const reach = it.kind === "tree" ? SPECIES[it.species].radius : Math.max(it.width, it.depth);
    const cMin = Math.max(0, Math.floor((it.x - reach - x0) / px) - 1);
    const cMax = Math.min(cols - 1, Math.ceil((it.x + reach - x0) / px) + 1);
    const rMin = Math.max(0, Math.floor((y0 - it.y - reach) / px) - 1);
    const rMax = Math.min(rows - 1, Math.ceil((y0 - it.y + reach) / px) + 1);
    for (let r = rMin; r <= rMax; r++) {
      const y = y0 - (r + 0.5) * px;
      for (let c = cMin; c <= cMax; c++) {
        const i = r * cols + c;
        if (zones[i] === ZONE_BUILDING) continue;
        const x = x0 + (c + 0.5) * px;
        let h = 0;
        if (it.kind === "tree") {
          const s = SPECIES[it.species];
          const d2 = (x - it.x) ** 2 + (y - it.y) ** 2;
          const r2 = s.radius ** 2;
          if (d2 <= r2) h = s.height * Math.max(0, 1 - d2 / r2) ** 0.25;
        } else if (Math.abs(x - it.x) <= it.width / 2 && Math.abs(y - it.y) <= it.depth / 2) {
          h = SAIL_HEIGHT;
        }
        if (h > (out[i] as number)) out[i] = h;
      }
    }
  }
  return out;
}

/** numpy.interp: linear, clamped to the end values. xs ascending. */
export function interp(x: number, xs: number[], ys: number[]): number {
  const n = xs.length;
  if (n === 0) return Number.NaN;
  if (x <= (xs[0] as number)) return ys[0] as number;
  if (x >= (xs[n - 1] as number)) return ys[n - 1] as number;
  let lo = 0;
  let hi = n - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if ((xs[mid] as number) <= x) lo = mid;
    else hi = mid;
  }
  const x0 = xs[lo] as number;
  const x1 = xs[hi] as number;
  const t = (x - x0) / (x1 - x0);
  return (ys[lo] as number) + t * ((ys[hi] as number) - (ys[lo] as number));
}

export interface HourModel {
  label: string;
  altitude: number;
  azimuth: number;
  coef: number[];
  lut_tmrt: number[];
  lut_utci: number[];
  mae_changed: number;
}

/**
 * Anchored T0 for one hour: base SOLWEIG field plus the modelled change.
 * features order: sunlit, under_canopy, sunlit_x_svf, near_canopy.
 */
export function predictHour(
  model: HourModel,
  base: { tmrt: Float32Array; utci: Float32Array; cdsm: Float32Array; features: Features },
  edit: { cdsm: Float32Array; features: Features },
  svf: Float32Array,
): { tmrt: Float32Array; utci: Float32Array } {
  const n = svf.length;
  const tmrt = new Float32Array(n);
  const utci = new Float32Array(n);
  const [b0, b1, b2, b3] = model.coef as [number, number, number, number];
  for (let i = 0; i < n; i++) {
    const dLit = (edit.features.lit[i] as number) - (base.features.lit[i] as number);
    const dUnder = ((edit.cdsm[i] as number) > 0 ? 1 : 0) - ((base.cdsm[i] as number) > 0 ? 1 : 0);
    const dNear = (edit.features.near[i] as number) - (base.features.near[i] as number);
    const bt = base.tmrt[i] as number;
    if (dLit === 0 && dUnder === 0 && dNear === 0) {
      tmrt[i] = bt;
      utci[i] = base.utci[i] as number;
      continue;
    }
    const t = bt + b0 * dLit + b1 * dUnder + b2 * dLit * (svf[i] as number) + b3 * dNear;
    tmrt[i] = t;
    utci[i] =
      (base.utci[i] as number) +
      interp(t, model.lut_tmrt, model.lut_utci) -
      interp(bt, model.lut_tmrt, model.lut_utci);
  }
  return { tmrt, utci };
}
