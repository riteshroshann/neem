import type { ChildDay } from "../lib/twin";

interface Props {
  today: ChildDay;
  plan?: ChildDay | null;
  start?: string; // clock time of minute 0
}

const W = 760;
const H = 240;
const PAD = { top: 36, right: 16, bottom: 32, left: 44 };

function clock(start: string, minute: number): string {
  const [h, m] = start.split(":").map(Number) as [number, number];
  const t = h * 60 + m + minute;
  const hh = Math.floor(t / 60);
  const mm = t % 60;
  return `${hh > 12 ? hh - 12 : hh}:${mm.toString().padStart(2, "0")}`;
}

function segments(labels: string[]): { label: string; from: number; to: number }[] {
  const out: { label: string; from: number; to: number }[] = [];
  labels.forEach((label, i) => {
    const last = out[out.length - 1];
    if (last && last.label === label) last.to = i + 1;
    else out.push({ label, from: i, to: i + 1 });
  });
  return out;
}

/** Decide which segment labels fit: skip any that would collide with the previous one. */
function labelled(
  segs: { label: string; from: number; to: number }[],
  x: (i: number) => number,
  right: number,
): { label: string; from: number; to: number; show: boolean; anchor: "start" | "end" }[] {
  let lastEnd = -Infinity;
  return segs.map((s) => {
    const width = s.label.length * 6.4;
    const anchor: "start" | "end" = x(s.from) + 4 + width > right ? "end" : "start";
    const start = anchor === "end" ? x(s.to) - 4 - width : x(s.from) + 4;
    const show = start >= lastEnd + 8;
    if (show) lastEnd = start + width;
    return { ...s, show, anchor };
  });
}

export default function ChildChart({ today, plan, start = "7:30" }: Props) {
  const n = today.rise.length;
  const peak = Math.max(1.2, today.peak_rise + 0.15, plan ? plan.peak_rise + 0.15 : 0);
  const x = (i: number) => PAD.left + (i / n) * (W - PAD.left - PAD.right);
  const y = (v: number) => PAD.top + (1 - v / peak) * (H - PAD.top - PAD.bottom);
  const path = (d: ChildDay) =>
    d.rise.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
  const ticks = [0, 0.5, 1].filter((t) => t <= peak);
  const outdoors = new Set(["Assembly", "Recess", "Walk home"]);

  return (
    <figure className="child-chart">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Core temperature rise through the school day: peak ${today.peak_rise.toFixed(
          2,
        )} degrees today${plan ? `, ${plan.peak_rise.toFixed(2)} with the plan` : ""}.`}
      >
        {labelled(segments(today.labels), x, W - PAD.right).map((s) => (
          <g key={`${s.label}-${s.from}`}>
            {outdoors.has(s.label) && (
              <rect
                x={x(s.from)}
                y={PAD.top}
                width={x(s.to) - x(s.from)}
                height={H - PAD.top - PAD.bottom}
                fill="var(--wash)"
              />
            )}
            {s.show && (
              <text
                x={s.anchor === "end" ? x(s.to) - 4 : x(s.from) + 4}
                y={PAD.top - 12}
                textAnchor={s.anchor}
                className="seg"
              >
                {s.label}
              </text>
            )}
          </g>
        ))}
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} stroke="var(--line)" />
            <text x={PAD.left - 8} y={y(t) + 4} textAnchor="end" className="tick">
              {t === 0 ? "rest" : `+${t}°`}
            </text>
          </g>
        ))}
        <line
          x1={PAD.left}
          x2={W - PAD.right}
          y1={y(1)}
          y2={y(1)}
          stroke="var(--ink)"
          strokeDasharray="2 4"
        />
        <path d={path(today)} fill="none" stroke="var(--ink)" strokeWidth={2} />
        {plan && (
          <path
            d={path(plan)}
            fill="none"
            stroke="var(--heat-very-strong)"
            strokeWidth={2}
            strokeDasharray="6 4"
          />
        )}
        {[0, 60, 120, 180, 240, 300]
          .filter((m) => m < n)
          .map((m) => (
            <text key={m} x={x(m)} y={H - 10} className="tick" textAnchor="middle">
              {clock(start, m)}
            </text>
          ))}
      </svg>
      <figcaption className="xs muted">
        Core temperature above the child's own resting state, minute by minute (JOS-3, scaled to a
        nine-year-old). Grey bands are time outdoors. The dotted line is a 1 °C rise, the usual
        heat-strain line. {plan ? "Dashed: with your verified plan." : ""}
      </figcaption>
    </figure>
  );
}
