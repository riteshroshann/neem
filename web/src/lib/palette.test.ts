import { expect, test } from "bun:test";
import { BANDS, band } from "./palette";

test("bands follow the UTCI assessment scale", () => {
  expect(band(20)).toBe("No heat stress");
  expect(band(26)).toBe("Moderate");
  expect(band(31.9)).toBe("Moderate");
  expect(band(32)).toBe("Strong");
  expect(band(40)).toBe("Very strong");
  expect(band(47.3)).toBe("Extreme");
});

test("every band has a ramp colour", () => {
  expect(BANDS).toHaveLength(5);
  for (const b of BANDS) expect(b.hex).toMatch(/^#[0-9a-f]{6}$/);
});
