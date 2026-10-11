import { expect, test } from "bun:test";
import { frameAt } from "./scrub";

test("frames stay in range", () => {
  expect(frameAt(0, 480)).toBe(0);
  expect(frameAt(1, 480)).toBe(479);
  expect(frameAt(0.5, 481)).toBe(240);
  expect(frameAt(-0.2, 480)).toBe(0);
  expect(frameAt(1.3, 480)).toBe(479);
});
