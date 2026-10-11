import { expect, test } from "bun:test";
import { delta, fullDate, lakh, longDate, rise, rupees, schoolName, temp } from "./format";

const NB = " ";

test("units stay attached and minus signs are real", () => {
  expect(temp(42.1)).toBe(`42.1${NB}°C`);
  expect(temp(-1.84)).toBe(`−1.8${NB}°C`);
  expect(rise(0.93)).toBe(`+0.93${NB}°C`);
  expect(delta(-1.81)).toBe(`−1.8${NB}°C`);
  expect(delta(-0.02)).toBe("No change");
});

test("rupees read the Indian way", () => {
  expect(rupees(297500)).toBe("₹2,97,500");
  expect(lakh(300000)).toBe(`₹3${NB}lakh`);
  expect(lakh(250000)).toBe("₹2,50,000");
});

test("dates", () => {
  expect(longDate("2026-04-27")).toBe("27 April 2026");
  expect(fullDate("2026-04-27")).toBe("Monday 27 April 2026");
});

test("school names", () => {
  expect(schoolName("skv school ground")).toBe("Skv School Ground");
  expect(schoolName("School Of Specialized Excellence")).toBe("School of Specialized Excellence");
  expect(schoolName("Unnamed school")).toBe("Unnamed school");
  expect(schoolName("Of Mice School")).toBe("Of Mice School");
});
