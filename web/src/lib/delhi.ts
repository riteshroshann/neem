import delhi from "../data/delhi.json";

// Delhi's boundary, equirectangular with longitude scaled by cos(latitude): true shape at city scale.
type Ring = number[][];
const boundary = delhi as { type: string; coordinates: unknown };
const rings: Ring[] =
  boundary.type === "Polygon"
    ? [(boundary.coordinates as Ring[])[0] ?? []]
    : (boundary.coordinates as Ring[][]).map((poly) => poly[0] ?? []);
const outline = rings.flat();
const lats = outline.map((p) => p[1] ?? 0);
const lons = outline.map((p) => p[0] ?? 0);
const [minLat, maxLat] = [Math.min(...lats), Math.max(...lats)];
const [minLon, maxLon] = [Math.min(...lons), Math.max(...lons)];
const K = Math.cos((28.6 * Math.PI) / 180);

export interface DelhiMap {
  width: number;
  height: number;
  x(lon: number): number;
  y(lat: number): number;
  outline: string;
}

export function delhiMap(width: number, pad = 20): DelhiMap {
  const height = Math.round((width * (maxLat - minLat)) / ((maxLon - minLon) * K));
  const x = (lon: number) => ((lon - minLon) / (maxLon - minLon)) * (width - 2 * pad) + pad;
  const y = (lat: number) => ((maxLat - lat) / (maxLat - minLat)) * (height - 2 * pad) + pad;
  const path = rings
    .map(
      (r) => `M${r.map((p) => `${x(p[0] ?? 0).toFixed(1)},${y(p[1] ?? 0).toFixed(1)}`).join("L")}Z`,
    )
    .join("");
  return { width, height, x, y, outline: path };
}
