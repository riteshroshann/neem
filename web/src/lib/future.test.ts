import { expect, test } from "bun:test";
import { GROWN, STAGES, TODAY } from "./future";

test("stages run from today to the grown grove, in order", () => {
  expect(TODAY.years).toBe(0);
  expect(STAGES.map((s) => s.years)).toEqual([...STAGES.map((s) => s.years)].sort((a, b) => a - b));
  expect(GROWN.years).toBeGreaterThan(TODAY.years);
});

test("grown trees cool the yard", () => {
  expect(GROWN.yard_1pm).toBeLessThan(TODAY.yard_1pm);
});
