import { expect, test } from "bun:test";
import { coolerBy, GROWN, STAGES, stageAt, TODAY } from "./future";

test("stages run from today to the grown grove, in order", () => {
  expect(TODAY.years).toBe(0);
  expect(STAGES.map((s) => s.years)).toEqual([...STAGES.map((s) => s.years)].sort((a, b) => a - b));
  expect(GROWN.years).toBeGreaterThan(TODAY.years);
});

test("a year between runs shows the last run before it", () => {
  expect(stageAt(0)).toBe(TODAY);
  expect(stageAt(7).years).toBe(5);
  expect(stageAt(99)).toBe(GROWN);
});

test("grown trees cool the yard; today is the baseline", () => {
  expect(coolerBy(TODAY)).toBe(0);
  expect(coolerBy(GROWN)).toBeGreaterThan(0);
});
