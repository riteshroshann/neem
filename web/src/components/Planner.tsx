import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { delta, lakh, ml, rise, temp } from "../lib/format";
import { BANDS, heatRgb, MAP } from "../lib/palette";
import {
  applyDesign,
  cost,
  type Features,
  features,
  type Intervention,
  predictHour,
  SPECIES,
  type Species,
  ZONE_BUILDING,
  ZONE_GROUND,
} from "../lib/physics";
import { bandShares, type ChildDay, groundMean, hourLabel, loadTwin, type Twin } from "../lib/twin";
import ChildChart from "./ChildChart";
import Twin3D from "./Twin3D";
import "./planner.css";

type Tool = Species | "sail";
type View = "map" | "3d";
type Verify =
  | { state: "idle" }
  | { state: "running"; started: number }
  | { state: "done"; result: VerifyResult; items: number }
  | { state: "error"; message: string };

interface VerifyResult {
  cost_rs: number;
  hours: string[];
  utci_ground_by_hour: number[];
  child: ChildDay;
  seconds: number;
}

interface AgentPlan {
  answer: string;
  baseline: { hours: Record<string, { today: number; plan: number }> };
  model: string;
  budget_rs: number;
  seconds: number;
  steps: string[];
  design: {
    trees: { x: number; y: number; species: Species }[];
    sails: { x: number; y: number; width: number; depth: number }[];
  };
  verified: VerifyResult | null;
}

function planItems(plan: AgentPlan): Intervention[] {
  return [
    ...plan.design.trees.map((t) => ({ kind: "tree" as const, ...t })),
    ...plan.design.sails.map((t) => ({ kind: "sail" as const, ...t })),
  ];
}

/** One step of the agent's trace, "tool -> result", as a line to read: the preview's hourly
    JSON becomes its 1 pm pair. */
function stepLine(step: string): string {
  const [call, result = ""] = step.split(" -> ");
  if (call === "preview") {
    try {
      const pm = (JSON.parse(result) as Record<string, { today: number; plan: number }>)["13:00"];
      if (pm) return `preview: 1 pm ${pm.today.toFixed(1)} → ${pm.plan.toFixed(1)} °C`;
    } catch {
      // not the hourly form: show it as it came
    }
  }
  return result ? `${call} → ${result}` : step;
}

// Dev talks to the local API; a production build without PUBLIC_NEEM_API has no physics server.
const API =
  (import.meta.env.PUBLIC_NEEM_API as string | undefined) ??
  (import.meta.env.DEV ? "http://127.0.0.1:8000" : "");
const TOOLS: { id: Tool; label: string }[] = [
  { id: "neem", label: "Neem" },
  { id: "peepal", label: "Peepal" },
  { id: "jamun", label: "Jamun" },
  { id: "amaltas", label: "Amaltas" },
  { id: "sail", label: "Sail" },
];
const BOUNDS = BANDS.flatMap((b) => (b.min === null ? [] : [b.min]));
const rupees = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

const PLACEHOLDER_HOURS = ["7 am", "8 am", "9 am", "10 am", "11 am", "12 pm", "1 pm"];

/** Run `fn` once the page's largest paint is on screen, or on the next frame after load. */
function afterFirstPaint(fn: () => void): () => void {
  if (PerformanceObserver.supportedEntryTypes?.includes("largest-contentful-paint")) {
    const po = new PerformanceObserver(() => {
      po.disconnect();
      fn();
    });
    po.observe({ type: "largest-contentful-paint", buffered: true });
    return () => po.disconnect();
  }
  let frame = 0;
  const onLoad = () => {
    frame = requestAnimationFrame(fn);
  };
  if (document.readyState === "complete") onLoad();
  else window.addEventListener("load", onLoad, { once: true });
  return () => {
    window.removeEventListener("load", onLoad);
    cancelAnimationFrame(frame);
  };
}

interface MapSize {
  rows: number;
  cols: number;
}

/** The map's shape, read by the CSS that sizes its column and its frame. */
function aspect(size: MapSize): React.CSSProperties {
  return { ["--aspect" as string]: String(size.cols / size.rows) };
}

/** Map or 3D, floating in the corner of the map like the tags on the site's other maps. */
function Views({ view, onChange }: { view: View; onChange?: (v: View) => void }) {
  return (
    <fieldset className="views" disabled={!onChange}>
      <legend className="visually-hidden">View</legend>
      {(["map", "3d"] as const).map((v) => (
        <button
          key={v}
          type="button"
          className={view === v ? "on" : ""}
          aria-pressed={view === v}
          onClick={() => onChange?.(v)}
        >
          {v === "map" ? "Map" : "3D"}
        </button>
      ))}
    </fieldset>
  );
}

/** Same layout as the planner, with the 1 pm heat map as a plain image, while the twin loads. */
export function PlannerPlaceholder({ schoolId, size }: { schoolId: string; size: MapSize }) {
  return (
    <div className="planner-top" style={aspect(size)} aria-busy="true">
      <div className="planner-map">
        <fieldset className="hours" disabled>
          <legend className="visually-hidden">Hour of the day</legend>
          {PLACEHOLDER_HOURS.map((label) => (
            <button key={label} type="button" className={label === "1 pm" ? "on" : ""}>
              {label}
            </button>
          ))}
        </fieldset>
        <div className="stage">
          <img
            src={`/twins/${schoolId}/map-1pm.png`}
            alt="Heat map of the school grounds at 1 pm"
            width={size.cols}
            height={size.rows}
          />
          <Views view="map" />
        </div>
        <p className="xs readout" />
      </div>
      <aside className="planner-side">
        <p className="label">Loading the 1 m heat twin…</p>
      </aside>
    </div>
  );
}

export default function Planner({ schoolId, size }: { schoolId: string; size: MapSize }) {
  const [twin, setTwin] = useState<Twin | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [hour, setHour] = useState(0);
  const [tool, setTool] = useState<Tool>("neem");
  const [items, setItems] = useState<Intervention[]>([]);
  const [drag, setDrag] = useState<{ x0: number; y0: number; x1: number; y1: number } | null>(null);
  const [hover, setHover] = useState<number | null>(null);
  const [verify, setVerify] = useState<Verify>({ state: "idle" });
  const [mail, setMail] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [previewMs, setPreviewMs] = useState(0);
  const [hint, setHint] = useState("");
  const [plan, setPlan] = useState<AgentPlan | null>(null);
  const [view, setView] = useState<View>("map");
  const [stageWidth, setStageWidth] = useState(0);
  const stage = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const baseFeatures = useRef(new Map<number, Features>());
  const hourRow = useRef<HTMLFieldSetElement>(null);

  // On narrow screens the hour row scrolls; keep the selected hour in view without moving the page.
  // Measured against the row itself: offsetLeft counts from the nearest positioned ancestor.
  // biome-ignore lint/correctness/useExhaustiveDependencies: re-centre when the hour or twin changes
  useEffect(() => {
    const row = hourRow.current;
    const on = row?.querySelector<HTMLButtonElement>("button.on");
    if (!row || !on) return;
    const r = row.getBoundingClientRect();
    const b = on.getBoundingClientRect();
    row.scrollLeft += b.left - r.left - (row.clientWidth - b.width) / 2;
  }, [hour, twin]);

  useEffect(() => {
    let live = true;
    const start = () => {
      loadTwin(schoolId)
        .then((t) => {
          if (!live) return;
          setTwin(t);
          setHour(t.hours.length - 1);
        })
        .catch((e: unknown) => live && setLoadError(String(e)));
      fetch(`/twins/${schoolId}/plan.json`)
        .then((r) => (r.ok ? (r.json() as Promise<AgentPlan>) : null))
        .then((p) => live && setPlan(p))
        .catch(() => live && setPlan(null));
    };
    // the 0.8 MB heat field waits until the page has painted; the 1 pm map is already showing
    const stop = afterFirstPaint(start);
    return () => {
      live = false;
      stop();
    };
  }, [schoolId]);

  const loadPlan = () => {
    if (!plan) return;
    const next = planItems(plan);
    setHint("");
    setItems(next);
    setVerify(
      plan.verified
        ? { state: "done", result: plan.verified, items: next.length }
        : { state: "idle" },
    );
  };

  const editCdsm = useMemo(
    () => (twin ? applyDesign(twin.cdsm, twin.zones, twin.summary.grid, items) : null),
    [twin, items],
  );

  const preview = useMemo(() => {
    if (!twin || !editCdsm) return null;
    const model = twin.hours[hour];
    if (!model) return null;
    const t0 = performance.now();
    const grid = twin.summary.grid;
    let base = baseFeatures.current.get(hour);
    if (!base) {
      base = features(twin.dsm, twin.dem, twin.cdsm, grid, model.altitude, model.azimuth);
      baseFeatures.current.set(hour, base);
    }
    const baseTmrt = twin.tmrt[hour] as Float32Array;
    const baseUtci = twin.utci[hour] as Float32Array;
    if (items.length === 0) {
      return { utci: baseUtci, ms: performance.now() - t0 };
    }
    const edit = features(twin.dsm, twin.dem, editCdsm, grid, model.altitude, model.azimuth);
    const out = predictHour(
      model,
      { tmrt: baseTmrt, utci: baseUtci, cdsm: twin.cdsm, features: base },
      { cdsm: editCdsm, features: edit },
      twin.svf,
    );
    return { utci: out.utci, ms: performance.now() - t0 };
  }, [twin, editCdsm, hour, items.length]);

  useEffect(() => {
    if (preview) setPreviewMs(preview.ms);
  }, [preview]);

  // The stage appears with the twin; a new width means a new bitmap, so the cells stay crisp.
  useEffect(() => {
    const el = stage.current;
    if (!el || !twin) return;
    const ro = new ResizeObserver(([entry]) => {
      if (entry) setStageWidth(Math.round(entry.contentRect.width));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [twin]);

  // Paint the heat field and the design overlay before the frame shows, so swapping in the
  // canvas never flashes. `view` and `stageWidth` are dependencies on purpose: the canvas
  // remounts when the 3D view closes, and resizes with the window.
  // biome-ignore lint/correctness/useExhaustiveDependencies: repaint the remounted or resized canvas
  useLayoutEffect(() => {
    const el = canvas.current;
    if (!el || !twin || !preview || !editCdsm) return;
    const { rows, cols, pixel_size: px, x0, y0 } = twin.summary.grid;
    const off = document.createElement("canvas");
    off.width = cols;
    off.height = rows;
    const octx = off.getContext("2d");
    if (!octx) return;
    const img = octx.createImageData(cols, rows);
    for (let i = 0; i < rows * cols; i++) {
      const z = twin.zones[i];
      // drawn like publish.heat_png, from the same palette: warm roofs, faint heat beyond the wall
      let rgb: [number, number, number];
      let alpha = 255;
      if (z === ZONE_BUILDING) rgb = MAP.schoolRoof;
      else if ((twin.dsm[i] as number) - (twin.dem[i] as number) > MAP.tallM) rgb = MAP.nearbyRoof;
      else {
        rgb = heatRgb(preview.utci[i] as number);
        if (z !== ZONE_GROUND) alpha = MAP.outsideAlpha;
      }
      img.data[i * 4] = rgb[0];
      img.data[i * 4 + 1] = rgb[1];
      img.data[i * 4 + 2] = rgb[2];
      img.data[i * 4 + 3] = alpha;
    }
    octx.putImageData(img, 0, 0);

    // the stage's CSS box sets the size; the bitmap matches it pixel for pixel
    const dpr = window.devicePixelRatio || 1;
    const width = el.clientWidth;
    const height = el.clientHeight;
    el.width = Math.round(width * dpr);
    el.height = Math.round(height * dpr);
    const ctx = el.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.imageSmoothingEnabled = false; // crisp 1 m cells, the same grid the physics runs on
    ctx.drawImage(off, 0, 0, width, height);

    const s = width / (cols * px); // screen px per metre
    const toScreen = (x: number, y: number) => [(x - x0) * s, (y0 - y) * s] as const;
    const crowns = new Path2D();
    const trunks = new Path2D();
    const sails = new Path2D();
    const pending = new Path2D();
    for (const it of items) {
      if (it.kind === "tree") {
        const [cx, cy] = toScreen(it.x, it.y);
        const r = SPECIES[it.species].radius * s;
        crowns.moveTo(cx + r, cy);
        crowns.arc(cx, cy, r, 0, Math.PI * 2);
        // on a small map a trunk dot would cover the cooler ground the crown makes
        if (r >= 7) {
          trunks.moveTo(cx + 2, cy);
          trunks.arc(cx, cy, 2, 0, Math.PI * 2);
        }
      } else {
        const [l, t] = toScreen(it.x - it.width / 2, it.y + it.depth / 2);
        sails.rect(l, t, it.width * s, it.depth * s);
      }
    }
    if (drag) {
      const [a, b] = toScreen(Math.min(drag.x0, drag.x1), Math.max(drag.y0, drag.y1));
      pending.rect(a, b, Math.abs(drag.x1 - drag.x0) * s, Math.abs(drag.y1 - drag.y0) * s);
    }

    // theme colours, not fixed ones: your trees in the accent green, sails in ink, each over
    // a dark halo so it reads on the hottest ground and the palest roof alike
    const css = getComputedStyle(el);
    const ink = css.getPropertyValue("--ink").trim();
    const leaf = css.getPropertyValue("--leaf").trim();
    const halo = css.getPropertyValue("--paper").trim();
    ctx.strokeStyle = halo;
    ctx.globalAlpha = 0.7;
    ctx.lineWidth = Math.min(4, 1.5 + s); // thinner on small maps, so it never fills a crown
    for (const path of [crowns, trunks, sails, pending]) ctx.stroke(path);
    ctx.globalAlpha = 1;
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = leaf;
    ctx.stroke(crowns);
    ctx.fillStyle = leaf;
    ctx.fill(trunks);
    ctx.strokeStyle = ink;
    ctx.stroke(sails);
    ctx.setLineDash([4, 3]);
    ctx.stroke(pending);
    ctx.setLineDash([]);
  }, [twin, preview, editCdsm, items, drag, view, stageWidth]);

  const toMap = useCallback(
    (e: React.PointerEvent<HTMLCanvasElement>) => {
      if (!twin) return null;
      const r = e.currentTarget.getBoundingClientRect();
      const { cols, rows, pixel_size: px, x0, y0 } = twin.summary.grid;
      const fc = ((e.clientX - r.left) / r.width) * cols;
      const fr = ((e.clientY - r.top) / r.height) * rows;
      return { x: x0 + fc * px, y: y0 - fr * px, cell: Math.floor(fr) * cols + Math.floor(fc) };
    },
    [twin],
  );

  const onDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const p = toMap(e);
    if (!p || !twin) return;
    if (tool === "sail") {
      e.currentTarget.setPointerCapture(e.pointerId);
      setDrag({ x0: p.x, y0: p.y, x1: p.x, y1: p.y });
      return;
    }
    // trees go on the school's own open ground; a click next door would cost money and do nothing
    if (twin.zones[p.cell] !== ZONE_GROUND) {
      setHint("Plant on the school's open ground, the bright area inside the wall.");
      return;
    }
    setHint("");
    setItems((xs) => [...xs, { kind: "tree", x: p.x, y: p.y, species: tool }]);
    setVerify({ state: "idle" });
  };

  const groundAt = (x: number, y: number) => {
    if (!twin) return false;
    const { cols, rows, pixel_size: px, x0, y0 } = twin.summary.grid;
    const c = Math.floor((x - x0) / px);
    const r = Math.floor((y0 - y) / px);
    return r >= 0 && r < rows && c >= 0 && c < cols && twin.zones[r * cols + c] === ZONE_GROUND;
  };

  const onMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const p = toMap(e);
    if (!p) return;
    setHover(p.cell);
    if (drag) setDrag({ ...drag, x1: p.x, y1: p.y });
  };

  const onUp = () => {
    if (!drag) return;
    const width = Math.min(40, Math.abs(drag.x1 - drag.x0));
    const depth = Math.min(40, Math.abs(drag.y1 - drag.y0));
    const cx = (drag.x0 + drag.x1) / 2;
    const cy = (drag.y0 + drag.y1) / 2;
    if (width >= 2 && depth >= 2 && !groundAt(cx, cy)) {
      setHint("Centre the sail over the school's open ground.");
    } else if (width >= 2 && depth >= 2) {
      setHint("");
      setItems((xs) => [
        ...xs,
        {
          kind: "sail",
          x: cx,
          y: cy,
          width,
          depth,
        },
      ]);
      setVerify({ state: "idle" });
    }
    setDrag(null);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
        e.preventDefault();
        setHint("");
        setItems((xs) => xs.slice(0, -1));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const runVerify = async () => {
    if (!API) {
      // The public site has no physics server; the planner's suggested plans carry verified results.
      setVerify({
        state: "error",
        message:
          "Physics verification runs on the local stack (SOLWEIG on a GPU). Load Neem's plan to see a design already verified, or run the stack from the repository.",
      });
      return;
    }
    setVerify({ state: "running", started: performance.now() });
    try {
      const body = {
        trees: items.flatMap((i) =>
          i.kind === "tree" ? [{ x: i.x, y: i.y, species: i.species }] : [],
        ),
        sails: items.flatMap((i) =>
          i.kind === "sail" ? [{ x: i.x, y: i.y, width: i.width, depth: i.depth }] : [],
        ),
      };
      const sub = await fetch(`${API}/schools/${schoolId}/designs`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!sub.ok) throw new Error(`the server said ${sub.status}`);
      const { job_id } = (await sub.json()) as { job_id: string };
      for (let i = 0; i < 180; i++) {
        await new Promise((r) => setTimeout(r, 1000));
        const job = (await fetch(`${API}/jobs/${job_id}`).then((r) => r.json())) as {
          state: string;
          result?: VerifyResult;
          error?: string;
        };
        if (job.state === "done" && job.result) {
          setVerify({ state: "done", result: job.result, items: items.length });
          return;
        }
        if (job.state === "failed") throw new Error(job.error ?? "the physics run failed");
      }
      throw new Error("the physics run took longer than three minutes");
    } catch (e) {
      const offline = e instanceof TypeError;
      setVerify({
        state: "error",
        message: offline
          ? "The physics server isn't reachable from here. Verification runs on the local stack; the method page shows how."
          : `Verification failed: ${(e as Error).message}.`,
      });
    }
  };

  const sendMail = async (result: VerifyResult | null) => {
    if (!twin) return;
    setMail("sending");
    const h = twin.summary.hours[hour];
    try {
      const r = await fetch("/api/email", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          school_id: schoolId,
          school: twin.summary.name,
          hour: h ? hourLabel(h.time) : "",
          today_utci: todayMean,
          plan_utci: result ? (result.utci_ground_by_hour[hour] ?? null) : previewMean,
          verified: Boolean(result),
          trees: items.filter((i) => i.kind === "tree").length,
          sails: items.filter((i) => i.kind === "sail").length,
          cost_rs: cost(items),
          child_today: {
            peak_rise: twin.child.morning.peak_rise,
            water_ml: twin.child.morning.total_water_ml,
          },
          child_plan: result
            ? { peak_rise: result.child.peak_rise, water_ml: result.child.total_water_ml }
            : null,
          url: window.location.href,
        }),
      });
      setMail(r.ok ? "sent" : "error");
    } catch {
      setMail("error");
    }
  };

  if (loadError)
    return <p className="planner-msg">Couldn't load this school's twin: {loadError}</p>;
  if (!twin || !preview) return <PlannerPlaceholder schoolId={schoolId} size={size} />;

  const h = twin.summary.hours[hour];
  const model = twin.hours[hour];
  const todayUtci = twin.utci[hour] as Float32Array;
  const todayMean = groundMean(todayUtci, twin.zones);
  const previewMean = groundMean(preview.utci, twin.zones);
  const shares = bandShares(preview.utci, twin.zones, BOUNDS);
  const trees = items.filter((i) => i.kind === "tree").length;
  const sails = items.length - trees;
  const verified = verify.state === "done" && verify.items === items.length ? verify.result : null;
  const verifiedMean = verified ? verified.utci_ground_by_hour[hour] : undefined;
  const hoverValue = hover !== null ? preview.utci[hover] : undefined;
  // the agent's 1 pm row needs both stored runs; a stand-in from another hour would mislead
  const agentToday1pm = plan?.baseline.hours["13:00"]?.today;
  const agentPlan1pm = plan?.verified
    ? plan.verified.utci_ground_by_hour[plan.verified.hours.indexOf("13:00")]
    : undefined;

  return (
    <div className="planner">
      <div className="planner-top" style={aspect(size)}>
        <div className="planner-map">
          <fieldset className="hours" ref={hourRow}>
            <legend className="visually-hidden">Hour of the day</legend>
            {twin.summary.hours.map((x, i) => (
              <button
                key={x.time}
                type="button"
                aria-pressed={i === hour}
                className={i === hour ? "on" : ""}
                onClick={() => setHour(i)}
              >
                {hourLabel(x.time)}
              </button>
            ))}
          </fieldset>
          <div className="stage" ref={stage}>
            {view === "3d" && editCdsm ? (
              <Twin3D twin={twin} cdsm={editCdsm} utci={preview.utci} />
            ) : (
              <canvas
                ref={canvas}
                className={tool === "sail" ? "drag" : ""}
                aria-label={`Heat map of ${twin.summary.name} at ${h ? hourLabel(h.time) : ""}. Click to plant, drag to place a shade sail.`}
                onPointerDown={onDown}
                onPointerMove={onMove}
                onPointerUp={onUp}
                onPointerLeave={() => setHover(null)}
              />
            )}
            <Views view={view} onChange={setView} />
          </div>
          <p className="xs muted readout num" aria-live="polite">
            {view === "3d"
              ? "Drag to orbit, scroll or pinch to zoom. Ground coloured by feels-like heat; grey roofs, green crowns, your trees included."
              : hint ||
                `${
                  hoverValue !== undefined
                    ? `Under the cursor: ${temp(hoverValue)} feels-like (UTCI).`
                    : "Hover the yard to read the heat at any square metre."
                }${items.length ? ` Preview recomputed in ${previewMs.toFixed(0)} ms.` : ""}`}
          </p>
        </div>

        <aside className="planner-side">
          <p className="label">School grounds at {h ? hourLabel(h.time) : ""}, feels-like</p>
          <p className="figure num">
            {previewMean.toFixed(1)}
            <span className="unit">°C</span>
          </p>
          <p className="small num delta">
            {items.length === 0
              ? `Air ${temp(h?.ta ?? Number.NaN)}. Mean over open ground, from the SOLWEIG run.`
              : `${delta(previewMean - todayMean)} against today (${temp(todayMean)}), preview.`}
          </p>

          <div
            className="bands"
            role="img"
            aria-label="Share of the grounds in each heat-stress band"
          >
            {/* only the bands the legend names: an empty one would still leave its gap and push
                the bar off the edge of the text */}
            {shares.map((s, i) =>
              s > 0.005 ? (
                <span
                  key={BANDS[i]?.name}
                  style={{ flexGrow: s, background: BANDS[i]?.hex }}
                  title={`${BANDS[i]?.name}: ${(s * 100).toFixed(0)}%`}
                />
              ) : null,
            )}
          </div>
          <ul className="legend xs num">
            {shares.map((s, i) =>
              s > 0.005 ? (
                <li key={BANDS[i]?.name}>
                  <i style={{ background: BANDS[i]?.hex }} /> {BANDS[i]?.name}{" "}
                  {(s * 100).toFixed(0)}%
                </li>
              ) : null,
            )}
          </ul>

          <fieldset className="tools">
            <legend className="label">Plant</legend>
            {TOOLS.map((t) => (
              <button
                key={t.id}
                type="button"
                className={tool === t.id ? "on" : ""}
                aria-pressed={tool === t.id}
                onClick={() => setTool(t.id)}
              >
                {t.label}
              </button>
            ))}
          </fieldset>
          <p className="xs muted">
            {tool === "sail"
              ? "Drag across the yard to place a 4 m high shade sail."
              : `Click the yard to plant a ${tool}: ${SPECIES[tool].height} m tall, ${SPECIES[tool].radius * 2} m crown after about five years.`}
          </p>

          <div className="design rule-light">
            <p className="small num">
              {items.length === 0
                ? "No changes yet."
                : `${trees} ${trees === 1 ? "tree" : "trees"}${sails ? `, ${sails} ${sails === 1 ? "sail" : "sails"}` : ""} · ${rupees.format(cost(items))}`}
            </p>
            <div className="row">
              <button
                type="button"
                className="button quiet"
                disabled={!items.length}
                onClick={() => {
                  setHint("");
                  setItems((xs) => xs.slice(0, -1));
                }}
              >
                Undo
              </button>
              <button
                type="button"
                className="button quiet"
                disabled={!items.length}
                onClick={() => {
                  setHint("");
                  setItems([]);
                  setVerify({ state: "idle" });
                }}
              >
                Clear
              </button>
            </div>
          </div>

          {items.length > 0 && model && (
            <p className="xs muted">
              This is a preview. Cells you didn't touch keep the SOLWEIG value; where you planted,
              it can be off by about {model.mae_changed.toFixed(1)} °C until verified.
            </p>
          )}

          {API ? (
            <>
              <button
                type="button"
                className="button"
                disabled={!items.length || verify.state === "running"}
                onClick={runVerify}
              >
                {verify.state === "running" ? "Running SOLWEIG…" : "Verify with physics"}
              </button>
              <p className="small num status" aria-live="polite">
                {verify.state === "running" &&
                  "Full radiation model on the edited school, about 10 seconds."}
                {verified &&
                  verifiedMean !== undefined &&
                  `Verified by SOLWEIG in ${verified.seconds.toFixed(1)} s: ${temp(verifiedMean)} at ${h ? hourLabel(h.time) : ""} (preview ${temp(previewMean)}).`}
                {verify.state === "error" && verify.message}
              </p>
            </>
          ) : (
            // the static site has no physics server: say where verification happens instead
            <p className="xs muted">
              Full SOLWEIG verification runs on the local GPU stack; the{" "}
              <a href="/method">method page</a> shows how. The planner's own plan below is already
              verified.
            </p>
          )}

          <button
            type="button"
            className="button quiet"
            disabled={!items.length || mail === "sending"}
            onClick={() => sendMail(verified)}
          >
            {mail === "sending" ? "Sending…" : "Email this plan"}
          </button>
          <p className="xs muted" aria-live="polite">
            {mail === "sent" && "Sent to the project inbox."}
            {mail === "error" && "The email didn't go through. Try again in a moment."}
          </p>

          {plan?.verified && (
            <div className="agent rule-light">
              <p className="label">Neem's planner suggests, within {lakh(plan.budget_rs)}</p>
              <p className="agent-design small num">
                {plan.design.trees.length} {plan.design.trees[0]?.species ?? "neem"} trees
                {plan.design.sails.length
                  ? `, ${plan.design.sails.length} shade ${plan.design.sails.length === 1 ? "sail" : "sails"}`
                  : ""}{" "}
                · {rupees.format(plan.verified.cost_rs)}
              </p>
              <dl className="agent-facts small num">
                {agentToday1pm !== undefined && agentPlan1pm !== undefined && (
                  <div>
                    <dt className="muted">Grounds at 1 pm</dt>
                    <dd>
                      {agentToday1pm.toFixed(1)} → {temp(agentPlan1pm)}
                    </dd>
                  </div>
                )}
                <div>
                  <dt className="muted">Child's core rise</dt>
                  <dd>
                    {rise(twin.child.morning.peak_rise)} → {rise(plan.verified.child.peak_rise)}
                  </dd>
                </div>
              </dl>
              <p className="xs muted">Verified by SOLWEIG.</p>
              <button type="button" className={API ? "button quiet" : "button"} onClick={loadPlan}>
                Load this plan
              </button>
              <details className="xs muted">
                <summary>How the planner got there</summary>
                <ol>
                  {plan.steps.map((step) => (
                    <li key={step}>{stepLine(step)}</li>
                  ))}
                </ol>
                <p>In its own words: “{plan.answer}”</p>
                <p>
                  Strands Agents with {plan.model} running locally, {plan.seconds.toFixed(0)} s. The
                  model chooses how many trees and which kind; the tools choose where, keep to the
                  budget and compute every number.
                </p>
              </details>
            </div>
          )}
        </aside>
      </div>

      <section className="planner-child rule">
        <div className="child-numbers">
          <div>
            <p className="label">A nine-year-old's core temperature rise by 12:45</p>
            <p className="figure num">{rise(twin.child.morning.peak_rise)}</p>
            {verified && (
              <p className="small num">With this plan: {rise(verified.child.peak_rise)}</p>
            )}
          </div>
          <div>
            <p className="label">Water lost to sweat and breath</p>
            <p className="figure num">{ml(twin.child.morning.total_water_ml)}</p>
            {verified && (
              <p className="small num">With this plan: {ml(verified.child.total_water_ml)}</p>
            )}
          </div>
        </div>
        <ChildChart today={twin.child.morning} plan={verified ? verified.child : null} />
      </section>
    </div>
  );
}
