// The showcase plan as it grows (neem-data grow): one full SOLWEIG run per age, same heatwave
// day every year, so the trees are the only thing that changes. Written by neem-data publish.
import future from "../data/future.json";

export interface Stage {
  years: number;
  /** open-ground mean feels-like at 1 pm, °C */
  yard_1pm: number;
  /** share of yard-hours in shade over the school morning */
  shade: number;
  child_rise: number;
  water_ml: number;
  map: string;
  height_m?: number;
  /** crown diameter, m */
  crown_m?: number;
  /** feels-like at 1 pm under the new crowns, and on the same cells today */
  under_crowns_1pm?: number;
  under_crowns_today?: number;
  crown_cover_m2?: number;
}

export const STAGES: Stage[] = future.stages;
export const TREES: number = future.trees;

const first = STAGES[0];
const last = STAGES[STAGES.length - 1];
if (!first || !last || first.years !== 0) throw new Error("future.json needs a year-0 stage");
export const TODAY: Stage = first;
export const GROWN: Stage = last;
