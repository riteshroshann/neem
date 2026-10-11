// The hero Earth: an orthographic globe drawn in square cells, the way the yard maps are drawn,
// lit by the sun SOLWEIG used for the 1 pm hour: where it stood at 12:30 in Delhi, mid-hour,
// on the showcase day.
import { LAND } from "../art/land";
import { STOPS } from "./palette";

type LatLon = readonly [number, number];

const RAD = Math.PI / 180;
const ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-_";
// 4x4 ordered dither, thresholds centred on zero: band edges break up like pixel art
const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5].map(
  (v) => (v + 0.5) / 16 - 0.5,
);
// Band edges fray by about ±1.5° of sun height. Dithering in degrees keeps that spread the
// same at 70° as at 30°, so a cell never shows a band its sun is more than 1.5° from.
const DITHER_DEG = 3.2;
// CSS px a press must travel before it turns the globe, so taps leave it settled
const SLOP = 4;

// Land is coloured by the sun's height: below 30, 30 to 50, 50 to 70 and above 70 degrees,
// in the heat ramp's moderate to extreme colours.
export const SUN_BANDS = [30, 50, 70] as const;
export const BAND_COLOURS = STOPS.slice(1, 5).map((s) => s.hex);
// sea in daylight, sea at night, land at night: from CSS, so the globe matches day or night bands
function surfaceColours(el: Element): string[] {
  const css = getComputedStyle(el);
  const read = (name: string, fallback: string) => css.getPropertyValue(name).trim() || fallback;
  return [
    read("--globe-sea", "#e5e9ec"),
    read("--globe-sea-night", "#ebe5db"),
    read("--globe-land-night", "#cbc3b6"),
    ...BAND_COLOURS,
    read("--globe-air", "#c9d8e3"),
  ];
}

// The disc fills 90% of the canvas; the ring beyond it is the atmosphere, drawn in cells that
// thin out with height, the way the air looks from orbit.
const RADIUS = 0.9;
const AIR = 0.08;
const SEA = 0;
const SEA_NIGHT = 1;
const LAND_NIGHT = 2;
const LAND_DAY = 3;

function decodeLand(): Uint8Array {
  const { cols, rows, rle } = LAND;
  const index = new Map([...ALPHABET].map((ch, i) => [ch, i]));
  const out = new Uint8Array(cols * rows);
  rle.split(".").forEach((line, r) => {
    let c = 0;
    let land = false;
    for (let i = 0; i < line.length; i += 2) {
      const n = (index.get(line[i] ?? "0") ?? 0) * 64 + (index.get(line[i + 1] ?? "0") ?? 0);
      if (land) out.fill(1, r * cols + c, r * cols + c + n);
      c += n;
      land = !land;
    }
  });
  return out;
}

function unit([lat, lon]: LatLon): [number, number, number] {
  const p = lat * RAD;
  const l = lon * RAD;
  return [Math.cos(p) * Math.cos(l), Math.cos(p) * Math.sin(l), Math.sin(p)];
}

const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);

export interface Globe {
  /** Screen position of a point in CSS px from the canvas's top left, or null on the far side. */
  project(at: LatLon): { x: number; y: number } | null;
  destroy(): void;
}

export interface GlobeOptions {
  sun: LatLon;
  focus: LatLon;
  from?: LatLon;
  intro: boolean;
  draggable: boolean;
  /** Degrees a second the Earth turns under a fixed sun once it has flown in; 0 holds still. */
  spin?: number;
  onSettle?: (settled: boolean) => void;
}

export function createGlobe(canvas: HTMLCanvasElement, opts: GlobeOptions): Globe {
  const land = decodeLand();
  let sun = unit(opts.sun);
  const ctx = canvas.getContext("2d");
  // how far the Earth has turned under the sun, in degrees; the camera turns with the sun, so
  // the lit side stays put on screen while the land slides west to east beneath it
  let turned = 0;
  let camera: [number, number] = [...(opts.intro ? (opts.from ?? [8, -18]) : opts.focus)];
  let dpr = 1; // pixel ratio of the last layout; offset, cellPx and n are in its device px
  let n = 0; // cells across
  let cellPx = 0;
  let gap = 0;
  let offset = 0;
  let cells = new Float32Array(0); // sx, sy, z per visible cell
  let dither = new Float32Array(0);
  let slots = new Uint16Array(0); // grid column and row per visible cell
  let air: number[] = []; // column, row, closeness to the limb (1 at the limb, 0 at the top)
  let frame = 0;
  let settled = !opts.intro;

  const colours = surfaceColours(canvas);

  function layout() {
    dpr = window.devicePixelRatio || 1;
    const size = canvas.clientWidth;
    cellPx = Math.max(3, Math.round(Math.min(6, Math.max(3.6, size / 96)) * dpr));
    const px = Math.round(size * dpr);
    n = Math.floor(px / cellPx);
    gap = Math.max(1, Math.round(cellPx * 0.2));
    offset = Math.floor((px - n * cellPx) / 2);
    canvas.width = px;
    canvas.height = px;
    const xs: number[] = [];
    const ds: number[] = [];
    const ss: number[] = [];
    air = [];
    for (let j = 0; j < n; j++) {
      for (let i = 0; i < n; i++) {
        const sx = (((i + 0.5) / n) * 2 - 1) / RADIUS;
        const sy = (((j + 0.5) / n) * 2 - 1) / RADIUS;
        const r = Math.hypot(sx, sy);
        const threshold = BAYER[(i & 3) + ((j & 3) << 2)] ?? 0;
        if (r > 1) {
          const t = 1 - (r - 1) / (AIR / RADIUS);
          if (t > 0 && t + threshold * 0.9 > 0.62) air.push(i, j, t);
          continue;
        }
        xs.push(sx, sy, Math.sqrt(1 - r * r));
        ds.push(threshold);
        ss.push(i, j);
      }
    }
    cells = new Float32Array(xs);
    dither = new Float32Array(ds);
    slots = new Uint16Array(ss);
  }

  function basis() {
    const lat = camera[0];
    const lon = camera[1] - turned;
    const p = lat * RAD;
    const l = lon * RAD;
    const c = [Math.cos(p) * Math.cos(l), Math.cos(p) * Math.sin(l), Math.sin(p)];
    const e = [-Math.sin(l), Math.cos(l), 0];
    const u = [-Math.sin(p) * Math.cos(l), -Math.sin(p) * Math.sin(l), Math.cos(p)];
    return { c, e, u };
  }

  function draw() {
    cancelAnimationFrame(frame);
    frame = 0;
    if (!ctx) return;
    const { c, e, u } = basis();
    sun = unit([opts.sun[0], opts.sun[1] - turned]);
    const buckets: number[][] = colours.map(() => []);
    const { cols, rows } = LAND;
    for (let k = 0, m = cells.length / 3; k < m; k++) {
      const sx = cells[k * 3] as number;
      const sy = -(cells[k * 3 + 1] as number);
      const z = cells[k * 3 + 2] as number;
      const x = (c[0] as number) * z + (e[0] as number) * sx + (u[0] as number) * sy;
      const y = (c[1] as number) * z + (e[1] as number) * sx + (u[1] as number) * sy;
      const w = (c[2] as number) * z + (u[2] as number) * sy;
      const lat = Math.asin(Math.max(-1, Math.min(1, w))) / RAD;
      const lon = Math.atan2(y, x) / RAD;
      const r = Math.min(rows - 1, Math.floor((90 - lat) / 0.5));
      const q = Math.min(cols - 1, Math.floor((lon + 180) / 0.5));
      const light = x * sun[0] + y * sun[1] + w * sun[2]; // sine of the sun's height here
      const d = dither[k] as number;
      const day = light + d * 0.07 > 0;
      let colour: number;
      if (!land[r * cols + q]) colour = day ? SEA : SEA_NIGHT;
      else if (!day) colour = LAND_NIGHT;
      else {
        const height = Math.asin(Math.min(1, light)) / RAD + d * DITHER_DEG;
        colour = LAND_DAY + SUN_BANDS.filter((edge) => height > edge).length;
      }
      buckets[colour]?.push(k);
    }
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const side = cellPx - gap;
    buckets.forEach((ks, colour) => {
      ctx.fillStyle = colours[colour] as string;
      for (const k of ks) {
        // cells shrink toward the rim, like a halftone: the disc reads as a sphere, no gradient
        const s = Math.max(1, Math.round(side * (0.55 + 0.45 * (cells[k * 3 + 2] as number))));
        const pad = Math.floor((side - s) / 2);
        ctx.fillRect(
          offset + (slots[k * 2] as number) * cellPx + pad,
          offset + (slots[k * 2 + 1] as number) * cellPx + pad,
          s,
          s,
        );
      }
    });
    ctx.fillStyle = colours[colours.length - 1] as string;
    for (let k = 0; k < air.length; k += 3) {
      const s = Math.max(1, Math.round(side * (0.3 + 0.45 * (air[k + 2] as number))));
      const pad = Math.floor((side - s) / 2);
      ctx.fillRect(
        offset + (air[k] as number) * cellPx + pad,
        offset + (air[k + 1] as number) * cellPx + pad,
        s,
        s,
      );
    }
  }

  const request = () => {
    if (!frame) frame = requestAnimationFrame(draw);
  };

  function setSettled(next: boolean) {
    if (next === settled) return;
    settled = next;
    opts.onSettle?.(next);
  }

  // Resizing the canvas clears it, so redraw at once rather than leave a blank frame.
  function refit() {
    layout();
    draw();
    if (settled) opts.onSettle?.(true);
  }

  // Browser zoom changes the pixel ratio without resizing the canvas in CSS px, which
  // ResizeObserver never reports, so watch the ratio itself and re-arm on every change.
  let ratio: MediaQueryList | undefined;
  function watchRatio() {
    ratio?.removeEventListener("change", onRatio);
    ratio = window.matchMedia(`(resolution: ${dpr}dppx)`);
    ratio.addEventListener("change", onRatio);
  }
  function onRatio() {
    refit();
    watchRatio();
  }

  // Ease the camera to a target, the short way round in longitude.
  let tween = 0;
  function flyTo(target: LatLon, ms: number) {
    cancelAnimationFrame(tween);
    const from: [number, number] = [...camera];
    const dLon = ((((target[1] - from[1]) % 360) + 540) % 360) - 180; // the short way round
    const t0 = performance.now();
    const step = (now: number) => {
      const t = Math.min(1, (now - t0) / ms);
      const k = ease(t);
      camera = [from[0] + (target[0] - from[0]) * k, from[1] + dLon * k];
      draw();
      if (t < 1) tween = requestAnimationFrame(step);
      else setSettled(true);
    };
    tween = requestAnimationFrame(step);
  }

  // Back to the focus after a drag; reduced motion snaps there instead of flying.
  function home() {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      camera = [...opts.focus];
      request();
      setSettled(true);
    } else flyTo(opts.focus, 1400);
  }

  layout();
  draw();
  const resize = new ResizeObserver(refit);
  resize.observe(canvas);
  watchRatio();
  if (opts.intro) flyTo(opts.focus, 3200);

  // The turn: frame-rate independent, easing up to speed after the fly-in, paused while
  // dragged, off screen or in a hidden tab, and never for people who ask for less motion.
  const spin = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : (opts.spin ?? 0);
  let held = false;
  let seen = true;
  let last = 0;
  let spun = 0;
  let turning = 0;
  const turn = (now: number) => {
    turning = 0;
    if (!seen || document.hidden) return;
    const dt = last ? Math.min(0.1, (now - last) / 1000) : 0;
    last = now;
    if (settled && !held) {
      spun = Math.min(1, spun + dt / 1.5);
      turned += spin * dt * spun * spun * (3 - 2 * spun);
      draw();
    }
    turning = requestAnimationFrame(turn);
  };
  const play = () => {
    if (spin && !turning) {
      last = 0;
      turning = requestAnimationFrame(turn);
    }
  };
  const watch = new IntersectionObserver(([entry]) => {
    seen = entry?.isIntersecting ?? true;
    if (seen) play();
  });
  if (spin) {
    watch.observe(canvas);
    document.addEventListener("visibilitychange", play);
    play();
  }

  // Drag to turn the Earth; it drifts home after a pause. Only the primary pointer counts, and
  // a press becomes a drag past SLOP, so a tap or a page scroll leaves the labels alone.
  let press: { id: number; x: number; y: number; cam?: [number, number] } | null = null;
  let back = 0;
  const onDown = (ev: PointerEvent) => {
    if (!ev.isPrimary || ev.button !== 0) return;
    canvas.setPointerCapture(ev.pointerId);
    press = { id: ev.pointerId, x: ev.clientX, y: ev.clientY };
  };
  const onMove = (ev: PointerEvent) => {
    if (!press || ev.pointerId !== press.id) return;
    const dx = ev.clientX - press.x;
    const dy = ev.clientY - press.y;
    if (!press.cam) {
      // under touch-action: pan-y a mostly vertical touch is the page scrolling, not a turn
      const scroll = ev.pointerType !== "mouse" && Math.abs(dy) >= Math.abs(dx);
      if (scroll || Math.hypot(dx, dy) <= SLOP) return;
      cancelAnimationFrame(tween);
      clearTimeout(back);
      press.cam = [...camera];
      held = true;
      if (!spin) setSettled(false);
    }
    const k = 180 / Math.PI / ((canvas.clientWidth / 2) * RADIUS);
    camera = [Math.max(-70, Math.min(70, press.cam[0] + dy * k)), press.cam[1] - dx * k];
    request();
  };
  const onUp = (ev: PointerEvent) => {
    if (!press || ev.pointerId !== press.id) return;
    const dragged = press.cam !== undefined;
    press = null;
    held = false;
    if (dragged && !spin) back = window.setTimeout(home, 1600);
  };
  if (opts.draggable) {
    canvas.addEventListener("pointerdown", onDown);
    canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("pointerup", onUp);
    canvas.addEventListener("pointercancel", onUp);
  }

  return {
    project(at) {
      const { c, e, u } = basis();
      const p = unit(at);
      const z = p[0] * (c[0] as number) + p[1] * (c[1] as number) + p[2] * (c[2] as number);
      if (z <= 0) return null;
      const sx = p[0] * (e[0] as number) + p[1] * (e[1] as number);
      const sy = p[0] * (u[0] as number) + p[1] * (u[1] as number) + p[2] * (u[2] as number);
      const half = (n * cellPx) / 2;
      return {
        x: (offset + half + sx * half * RADIUS) / dpr,
        y: (offset + half - sy * half * RADIUS) / dpr,
      };
    },
    destroy() {
      resize.disconnect();
      watch.disconnect();
      document.removeEventListener("visibilitychange", play);
      cancelAnimationFrame(turning);
      ratio?.removeEventListener("change", onRatio);
      cancelAnimationFrame(tween);
      cancelAnimationFrame(frame);
      clearTimeout(back);
    },
  };
}
