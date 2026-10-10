// Cross-language differential test, TypeScript half: the browser T0 must reproduce the Python.
import { describe, expect, test } from "bun:test";
import fixture from "./fixtures/physics.json";
import {
  applyDesign,
  cost,
  type Intervention,
  interp,
  nearCanopy,
  SPECIES,
  sunlitFraction,
} from "./physics";

const { rows, cols, pixel_size } = fixture.grid;
const dsm = Float32Array.from(fixture.dsm);
const dem = Float32Array.from(fixture.dem);
const cdsm = Float32Array.from(fixture.cdsm);
const zones = Uint8Array.from(fixture.zones);
const design = fixture.design as Intervention[];

describe("shadow caster", () => {
  fixture.suns.forEach(([alt, az], k) => {
    test(`agrees with numba at altitude ${alt}, azimuth ${az}`, () => {
      const ours = sunlitFraction(dsm, dem, cdsm, rows, cols, pixel_size, alt ?? 0, az ?? 0);
      const ref = fixture.sunlit[k] as number[];
      let same = 0;
      for (let i = 0; i < ref.length; i++) {
        if (Math.abs((ours[i] as number) - (ref[i] as number)) < 1e-3) same++;
      }
      // float32 inputs on the Python side can flip a ray that grazes an edge; nothing more.
      expect(same / ref.length).toBeGreaterThan(0.998);
    });
  });

  test("is dark at night", () => {
    const night = sunlitFraction(dsm, dem, cdsm, rows, cols, pixel_size, -3, 120);
    expect(Math.max(...night)).toBe(0);
  });
});

describe("design application", () => {
  const edited = applyDesign(cdsm, zones, fixture.grid, design);

  test("reproduces the Python canopy", () => {
    let worst = 0;
    edited.forEach((v, i) => {
      worst = Math.max(worst, Math.abs(v - (fixture.edited_cdsm[i] as number)));
    });
    expect(worst).toBeLessThan(1e-3);
  });

  test("near-canopy window matches scipy's maximum_filter", () => {
    const near = nearCanopy(edited, rows, cols);
    expect(Array.from(near)).toEqual(fixture.edited_near);
  });

  test("never plants on a roof and never lowers canopy", () => {
    edited.forEach((v, i) => {
      if (zones[i] === 2) expect(v).toBe(cdsm[i] as number);
      expect(v).toBeGreaterThanOrEqual(cdsm[i] as number);
    });
  });

  test("costs add up", () => {
    const sail = design.find((d) => d.kind === "sail");
    const sailCost = sail && sail.kind === "sail" ? Math.round(sail.width * sail.depth * 1800) : 0;
    expect(cost(design)).toBe(SPECIES.neem.cost + SPECIES.peepal.cost + sailCost);
  });
});

test("interp matches numpy at and beyond the ends", () => {
  const xs = [10, 20, 30];
  const ys = [1, 3, 7];
  expect(interp(5, xs, ys)).toBe(1);
  expect(interp(25, xs, ys)).toBeCloseTo(5);
  expect(interp(99, xs, ys)).toBe(7);
});
