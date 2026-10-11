import ranking from "../data/ranking.json";
import { heatHex } from "./palette";

const { utci_min: lo, utci_max: hi } = ranking.stats;

/**
 * Colour for a yard's mean feels-like temperature. Yard means span only a few degrees, so the
 * coolest and hottest yards are stretched over the ramp from 32 °C (moderate) to 46 °C (extreme)
 * to make the differences show. Anything drawn with it needs YARD_LEGEND beside it.
 */
export function yardHex(utci: number): string {
  return heatHex(32 + ((utci - lo) / (hi - lo)) * 14);
}

/** The coolest yard, two even steps and the hottest: what the stretched colours mean. */
export const YARD_LEGEND = [lo, lo + (hi - lo) / 3, lo + (2 * (hi - lo)) / 3, hi];

/** Every ranked school, coolest first, so the hottest yards are drawn last and stay on top. */
export const YARDS_BY_HEAT = [...ranking.schools].sort((a, b) => a.utci_mean - b.utci_mean);

export const COOLEST = YARDS_BY_HEAT[0];
export const HOTTEST = YARDS_BY_HEAT[YARDS_BY_HEAT.length - 1];

type Yard = (typeof ranking.schools)[number];
const meanOf = (xs: Yard[], key: "canopy_cover" | "utci_mean") =>
  xs.reduce((sum, x) => sum + x[key], 0) / xs.length;
const summarise = (xs: Yard[]) => ({
  cover: meanOf(xs, "canopy_cover"),
  heat: meanOf(xs, "utci_mean"),
});
const byCanopy = [...ranking.schools].sort((a, b) => a.canopy_cover - b.canopy_cover);
const quarter = Math.floor(byCanopy.length / 4);

/** The barest and the leafiest quarter of yards by tree cover: the shade argument in two rows. */
export const CANOPY_QUARTERS = {
  bare: summarise(byCanopy.slice(0, quarter)),
  leafy: summarise(byCanopy.slice(-quarter)),
};
