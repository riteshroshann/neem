import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { heatRgb, STOPS } from "../lib/palette";
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
import "./planner.css";

type Tool = Species | "sail";
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

const API = (import.meta.env.PUBLIC_NEEM_API as string | undefined) ?? "http://127.0.0.1:8000";
const TOOLS: { id: Tool; label: string }[] = [
  { id: "neem", label: "Neem" },
  { id: "peepal", label: "Peepal" },
  { id: "jamun", label: "Jamun" },
  { id: "amaltas", label: "Amaltas" },
  { id: "sail", label: "Shade sail" },
];
const BOUNDS = STOPS.map((s) => s.utci);
const rupees = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

export default function Planner({ schoolId }: { schoolId: string }) {
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
  const canvas = useRef<HTMLCanvasElement>(null);
  const baseFeatures = useRef(new Map<number, Features>());

  useEffect(() => {
    loadTwin(schoolId)
      .then((t) => {
        setTwin(t);
        setHour(t.hours.length - 1);
      })
      .catch((e: unknown) => setLoadError(String(e)));
  }, [schoolId]);

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

  // Paint the heat field and the design overlay.
  useEffect(() => {
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
      let rgb: [number, number, number];
      if (z === ZONE_BUILDING) rgb = [208, 208, 208];
      else if ((twin.dsm[i] as number) - (twin.dem[i] as number) > 2.5) rgb = [232, 232, 232];
      else {
        rgb = heatRgb(preview.utci[i] as number);
        if (z !== ZONE_GROUND) rgb = rgb.map((v) => Math.round(v + (255 - v) * 0.55)) as typeof rgb;
      }
      img.data[i * 4] = rgb[0];
      img.data[i * 4 + 1] = rgb[1];
      img.data[i * 4 + 2] = rgb[2];
      img.data[i * 4 + 3] = 255;
    }
    octx.putImageData(img, 0, 0);

    const dpr = window.devicePixelRatio || 1;
    const width = el.clientWidth;
    const height = (width * rows) / cols;
    el.width = Math.round(width * dpr);
    el.height = Math.round(height * dpr);
    el.style.height = `${height}px`;
    const ctx = el.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(off, 0, 0, width, height);

    const s = width / (cols * px); // screen px per metre
    const toScreen = (x: number, y: number) => [(x - x0) * s, (y0 - y) * s] as const;
    ctx.lineWidth = 1.25;
    ctx.strokeStyle = "#0a0a0a";
    for (const it of items) {
      if (it.kind === "tree") {
        const [cx, cy] = toScreen(it.x, it.y);
        ctx.beginPath();
        ctx.arc(cx, cy, SPECIES[it.species].radius * s, 0, Math.PI * 2);
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(cx, cy, 2, 0, Math.PI * 2);
        ctx.fillStyle = "#0a0a0a";
        ctx.fill();
      } else {
        const [l, t] = toScreen(it.x - it.width / 2, it.y + it.depth / 2);
        ctx.strokeRect(l, t, it.width * s, it.depth * s);
      }
    }
    if (drag) {
      ctx.setLineDash([4, 3]);
      const [a, b] = toScreen(Math.min(drag.x0, drag.x1), Math.max(drag.y0, drag.y1));
      ctx.strokeRect(a, b, Math.abs(drag.x1 - drag.x0) * s, Math.abs(drag.y1 - drag.y0) * s);
      ctx.setLineDash([]);
    }
  }, [twin, preview, editCdsm, items, drag]);

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
    if (twin.zones[p.cell] === ZONE_BUILDING) return;
    setItems((xs) => [...xs, { kind: "tree", x: p.x, y: p.y, species: tool }]);
    setVerify({ state: "idle" });
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
    if (width >= 2 && depth >= 2) {
      setItems((xs) => [
        ...xs,
        {
          kind: "sail",
          x: (drag.x0 + drag.x1) / 2,
          y: (drag.y0 + drag.y1) / 2,
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
        setItems((xs) => xs.slice(0, -1));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const runVerify = async () => {
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
  if (!twin || !preview) return <p className="planner-msg">Loading the 1 m heat twin…</p>;

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

  return (
    <div className="planner">
      <div className="planner-map">
        <fieldset className="hours">
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
        <canvas
          ref={canvas}
          className={tool === "sail" ? "drag" : ""}
          aria-label={`Heat map of ${twin.summary.name} at ${h ? hourLabel(h.time) : ""}. Click to plant, drag to place a shade sail.`}
          onPointerDown={onDown}
          onPointerMove={onMove}
          onPointerUp={onUp}
          onPointerLeave={() => setHover(null)}
        />
        <p className="xs muted readout num">
          {hoverValue !== undefined
            ? `Under the cursor: ${hoverValue.toFixed(1)} °C feels-like (UTCI). `
            : "Hover the yard to read the heat at any square metre. "}
          Preview recomputed in {previewMs.toFixed(0)} ms.
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
            ? `Air ${h?.ta.toFixed(1)} °C. Mean over open ground, from the SOLWEIG run.`
            : `${(previewMean - todayMean).toFixed(1)} °C against today (${todayMean.toFixed(1)} °C), preview.`}
        </p>

        <div
          className="bands"
          role="img"
          aria-label="Share of the grounds in each heat-stress band"
        >
          {shares.map((s, i) => (
            <span
              key={STOPS[i]?.band}
              style={{ flexGrow: s, background: STOPS[i]?.hex }}
              title={`${STOPS[i]?.band}: ${(s * 100).toFixed(0)}%`}
            />
          ))}
        </div>
        <ul className="legend xs num">
          {shares.map((s, i) =>
            s > 0.005 ? (
              <li key={STOPS[i]?.band}>
                <i style={{ background: STOPS[i]?.hex }} /> {STOPS[i]?.band} {(s * 100).toFixed(0)}%
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
              onClick={() => setItems((xs) => xs.slice(0, -1))}
            >
              Undo
            </button>
            <button
              type="button"
              className="button quiet"
              disabled={!items.length}
              onClick={() => {
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
            This is a preview. Cells you didn't touch keep the SOLWEIG value; where you planted, it
            can be off by about {model.mae_changed.toFixed(1)} °C until verified.
          </p>
        )}

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
            `Verified by SOLWEIG in ${verified.seconds.toFixed(1)} s: ${verifiedMean.toFixed(1)} °C at ${h ? hourLabel(h.time) : ""} (preview ${previewMean.toFixed(1)} °C).`}
          {verify.state === "error" && verify.message}
        </p>

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
      </aside>

      <section className="planner-child rule">
        <div className="child-numbers">
          <div>
            <p className="label">A nine-year-old's core temperature rise by 12:45</p>
            <p className="figure num">+{twin.child.morning.peak_rise.toFixed(2)}°</p>
            {verified && (
              <p className="small num">With this plan: +{verified.child.peak_rise.toFixed(2)}°</p>
            )}
          </div>
          <div>
            <p className="label">Water lost to sweat and breath</p>
            <p className="figure num">{Math.round(twin.child.morning.total_water_ml)} ml</p>
            {verified && (
              <p className="small num">
                With this plan: {Math.round(verified.child.total_water_ml)} ml
              </p>
            )}
          </div>
        </div>
        <ChildChart today={twin.child.morning} plan={verified ? verified.child : null} />
      </section>
    </div>
  );
}
