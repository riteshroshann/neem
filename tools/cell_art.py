"""Cell art for the site: neem branches for the top corners and a schoolyard strip for the foot.

Everything on the site is drawn in square cells, like the 1 m grid the physics runs on. Shapes
are built as geometry, rasterised at 4x4 samples per cell, and written as SVG runs masked by a
cell pattern, so the files stay small and the gaps stay crisp at any size.

    uv run python tools/cell_art.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from shapely import contains_xy
from shapely.affinity import rotate, scale, translate
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from neem_core.palette import STOPS

OUT = Path("web/public/art")
SUB = 4  # samples per cell side
GAP = 0.2  # share of a cell left as gap

# neem greens, darkest first; bark; blossom
LEAF = ["#1d4530", "#2c6142", "#3f7d4f", "#68a05c", "#9cc57e"]
BARK = "#5b4030"
BARK_SHADE = "#3d2a1f"  # the underside of a limb
BARK_LIT = "#7d5d44"  # its top edge, lit from above
BLOSSOM = ["#f7f1de", "#ece0b5"]
# the UTCI heat ramp, one colour per band
HEAT = [hex_.lower() for _, hex_ in STOPS]
CITY = ["#ddd5c8", "#d3cabb"]
KID = {"skin": "#8a5a3c", "hair": "#241a14", "shirt": "#fbfaf6", "shorts": "#4b5a78"}


@dataclass
class Art:
    cols: int
    rows: int
    grid: np.ndarray = field(init=False)  # palette index per cell, -1 empty
    palette: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.grid = np.full((self.rows, self.cols), -1, dtype=np.int16)
        s = (np.arange(self.cols * SUB) + 0.5) / SUB
        t = (np.arange(self.rows * SUB) + 0.5) / SUB
        self._x, self._y = np.meshgrid(s, t)

    def colour(self, hex_: str) -> int:
        if hex_ not in self.palette:
            self.palette.append(hex_)
        return self.palette.index(hex_)

    def coverage(self, geom: BaseGeometry) -> np.ndarray:
        inside = contains_xy(geom, self._x, self._y).astype(np.float32)
        return inside.reshape(self.rows, SUB, self.cols, SUB).mean(axis=(1, 3))

    def fill(self, geom: BaseGeometry, hex_: str, threshold: float = 0.34) -> None:
        if geom.is_empty:
            return
        self.grid[self.coverage(geom) >= threshold] = self.colour(hex_)

    def put(self, col: int, row: int, hex_: str) -> None:
        if 0 <= row < self.rows and 0 <= col < self.cols:
            self.grid[row, col] = self.colour(hex_)

    def svg(self, name: str, aspect: str = "xMidYMid meet") -> None:
        paths = []
        for k, hex_ in enumerate(self.palette):
            runs = []
            for r in range(self.rows):
                row = self.grid[r] == k
                c = 0
                while c < self.cols:
                    if row[c]:
                        start = c
                        while c < self.cols and row[c]:
                            c += 1
                        runs.append(f"M{start} {r}h{c - start}v1h-{c - start}z")
                    else:
                        c += 1
            if runs:
                paths.append(f'<path fill="{hex_}" d="{"".join(runs)}"/>')
        side = 1 - GAP
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.cols} {self.rows}" '
            f'preserveAspectRatio="{aspect}">'
            '<defs><pattern id="c" width="1" height="1" patternUnits="userSpaceOnUse">'
            f'<rect width="{side}" height="{side}" fill="#fff"/></pattern>'
            '<mask id="m"><rect width="100%" height="100%" fill="url(#c)"/></mask></defs>'
            f'<g mask="url(#m)">{"".join(paths)}</g></svg>'
        )
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / name).write_text(svg)
        print(f"{name}: {self.cols}x{self.rows} cells, {len(svg) / 1024:.1f} KB")


def curve(points: list[tuple[float, float]], n: int = 48) -> LineString:
    """Quadratic or cubic Bezier through control points, as a polyline."""
    t = np.linspace(0, 1, n)[:, None]
    p = np.array(points, dtype=float)
    if len(p) == 3:
        xy = (1 - t) ** 2 * p[0] + 2 * (1 - t) * t * p[1] + t**2 * p[2]
    else:
        xy = (
            (1 - t) ** 3 * p[0]
            + 3 * (1 - t) ** 2 * t * p[1]
            + 3 * (1 - t) * t**2 * p[2]
            + t**3 * p[3]
        )
    return LineString(xy)


def path(*segments: list[tuple[float, float]], n: int = 48) -> LineString:
    """Bezier segments joined end to end into one polyline."""
    parts = [np.asarray(curve(seg, n).coords) for seg in segments]
    return LineString(np.vstack([parts[0], *(p[1:] for p in parts[1:])]))


def tapered(line: LineString, w0: float, w1: float, steps: int = 24) -> BaseGeometry:
    """A stroke that thins from w0 to w1 along the line."""
    parts = []
    for i in range(steps):
        a = line.interpolate(i / steps, normalized=True)
        b = line.interpolate((i + 1) / steps, normalized=True)
        w = w0 + (w1 - w0) * (i + 0.5) / steps
        parts.append(LineString([a, b]).buffer(w / 2, cap_style="round"))
    return unary_union(parts)


def leaflet(x: float, y: float, angle: float, length: float, width: float, bend: float) -> Polygon:
    """A falcate neem leaflet: pointed both ends, curved toward the leaf tip."""
    n = 14
    t = np.linspace(0, 1, n)
    half = width / 2 * np.sin(np.pi * t) ** 0.8
    spine = bend * length * (t - t**2)
    upper = np.stack([t * length, spine + half], axis=1)
    lower = np.stack([t * length, spine - half], axis=1)[::-1]
    poly = Polygon(np.vstack([upper, lower]))
    return translate(rotate(poly, angle, origin=(0, 0)), x, y)


def compound_leaf(
    base: tuple[float, float], angle: float, length: float, pairs: int, rng: np.random.Generator
) -> tuple[BaseGeometry, list[Polygon], list[Polygon]]:
    """Rachis plus paired leaflets, split into the sunlit side and the shaded side."""
    a = math.radians(angle)
    sag = rng.uniform(-0.1, 0.1) * length
    end = (base[0] + math.cos(a) * length, base[1] + math.sin(a) * length)
    mid = (
        (base[0] + end[0]) / 2 - math.sin(a) * sag,
        (base[1] + end[1]) / 2 + math.cos(a) * sag,
    )
    rachis = curve([base, mid, end])
    lit: list[Polygon] = []
    shade: list[Polygon] = []
    for i in range(pairs):
        t = 0.22 + 0.7 * i / max(1, pairs - 1)
        p = rachis.interpolate(t, normalized=True)
        q = rachis.interpolate(min(1.0, t + 0.02), normalized=True)
        heading = math.degrees(math.atan2(q.y - p.y, q.x - p.x))
        size = 1.05 - 0.3 * abs(t - 0.5)
        for side in (-1, 1):
            leaf = leaflet(
                p.x,
                p.y,
                heading + side * rng.uniform(38, 50),
                length * 0.3 * size,
                length * 0.095 * size,
                -side * 0.22,
            )
            # leaflets on the side facing the sun, up and to the right, catch the light
            (
                lit
                if side * math.copysign(1, math.cos(math.radians(heading)) + 1e-9) < 0
                else shade
            ).append(leaf)
    lit.append(leaflet(end[0], end[1], math.degrees(a), length * 0.26, length * 0.09, 0.1))
    return tapered(rachis, 0.9, 0.5), lit, shade


def blossom(art: Art, x: float, y: float, rng: np.random.Generator) -> None:
    """Neem flowers in April: small loose panicles of cream cells on hair-thin stalks."""
    stalk = curve([(x, y), (x + rng.uniform(-1, 1), y + 2), (x + rng.uniform(-2, 2), y + 4)])
    art.fill(stalk.buffer(0.32), LEAF[2], 0.3)
    for _ in range(7):
        cx = x + rng.uniform(-2.6, 2.6)
        cy = y + rng.uniform(2.0, 6.0)
        art.put(int(cx), int(cy), BLOSSOM[int(rng.random() < 0.35)])


def branch(seed: int, cols: int = 84, rows: int = 52) -> Art:
    """A neem limb coming down from behind the masthead into the corner.

    It leaves the top edge in a curve, so it reads as part of a tree beyond the frame, sags under
    its leaves, and lifts at the tip, where the new growth is. The leaves bunch toward the end, as
    neem's do."""
    rng = np.random.default_rng(seed)
    art = Art(cols, rows)
    twig = path(
        [(1.5, -9), (3.5, -1), (9, 3.5), (20, 5)],
        [(20, 5), (36, 6.6), (54, 10.5), (cols - 16, 8)],
    )
    fork = twig.interpolate(0.42, normalized=True)
    spur = curve([(fork.x, fork.y), (fork.x + 5, fork.y + 4), (fork.x + 8, fork.y + 11)])
    tip = twig.interpolate(1.0, normalized=True)
    back, front = [], []
    # (position on the twig, angle, length, depth layer); none on the stretch hidden by the masthead
    sprays = [
        (0.22, 72, 25, 0),
        (0.33, 104, 29, 1),
        (0.45, 64, 32, 0),
        (0.56, 90, 34, 1),
        (0.66, 116, 27, 0),
        (0.76, 74, 31, 1),
        (0.86, 100, 28, 1),
    ]
    for t, angle, length, layer in sprays:
        p = twig.interpolate(t, normalized=True)
        leaf = compound_leaf((p.x, p.y), angle + rng.uniform(-6, 6), length, 4, rng)
        (front if layer else back).append(leaf)
    end = spur.interpolate(1.0, normalized=True)
    front.append(compound_leaf((end.x, end.y), 84, 22, 3, rng))
    # the flush at the tip: young leaves held up and forward, lighter than the old ones
    young = [
        compound_leaf((tip.x, tip.y), a, n, 3, rng) for a, n in ((-14, 10), (24, 11), (60, 14))
    ]
    for stem, lit, shade in back:
        art.fill(unary_union(shade), LEAF[0])
        art.fill(unary_union(lit), LEAF[1])
        art.fill(stem, LEAF[0], 0.3)
    for stem, lit, shade in front:
        art.fill(unary_union(shade), LEAF[2])
        art.fill(unary_union(lit), LEAF[3])
        art.fill(stem, LEAF[1], 0.3)
    # the brightest leaflets: the tips of the front sprays
    for _, lit, _ in front[1::2]:
        art.fill(unary_union(lit[-3:]), LEAF[4])
    for stem, lit, shade in young:
        art.fill(unary_union(shade), LEAF[3])
        art.fill(unary_union(lit), LEAF[4])
        art.fill(stem, LEAF[2], 0.3)
    # bark thick at the base and thin at the tip, shaded underneath and lit along the top
    bark = unary_union([tapered(twig, 4.2, 1.0, steps=40), tapered(spur, 1.5, 0.8)])
    art.fill(bark, BARK, 0.3)
    art.fill(bark.difference(translate(bark, 0, -0.9)), BARK_SHADE, 0.3)
    top = bark.difference(translate(bark, 0, 0.9)).intersection(box(-2, -10, cols * 0.45, rows))
    art.fill(top, BARK_LIT, 0.3)
    for t in (0.3, 0.52, 0.72, 0.9):
        p = twig.interpolate(t, normalized=True)
        blossom(art, p.x, p.y + 1, rng)
    return art


def neem_tree(art: Art, x: float, ground: float, height: float, spread: float, seed: int) -> None:
    """A full neem: short forked trunk, broad dome, lit from the upper right."""
    rng = np.random.default_rng(seed)
    top = ground - height * 0.45
    trunk = Polygon(
        [
            (x - spread * 0.06, ground),
            (x + spread * 0.06, ground),
            (x + spread * 0.035, top),
            (x - spread * 0.035, top),
        ]
    )
    limbs = [
        tapered(
            curve(
                [
                    (x, top + 2),
                    (x + k * spread * 0.1, top - 2),
                    (x + k * spread * 0.22, top - height * 0.18),
                ]
            ),
            spread * 0.05,
            spread * 0.025,
        )
        for k in (-1, 1)
    ]
    cy = ground - height * 0.7
    circles = [(x, cy, spread * 0.3)]
    for _ in range(40):
        a = rng.uniform(math.pi * 0.95, math.pi * 2.05)
        r = rng.uniform(0.3, 1.0)
        circles.append(
            (
                x + math.cos(a) * spread * 0.48 * r,
                cy + math.sin(a) * height * 0.3 * r + height * 0.06,
                spread * rng.uniform(0.09, 0.17),
            )
        )
    crown = unary_union([Point(cx, cy_).buffer(r, 16) for cx, cy_, r in circles])
    lit = unary_union(
        [
            Point(cx + spread * 0.07, cy_ - height * 0.05).buffer(r * 0.8, 16)
            for cx, cy_, r in circles[1:26]
        ]
    ).intersection(crown)
    top_light = unary_union(
        [
            Point(cx + spread * 0.12, cy_ - height * 0.1).buffer(r * 0.5, 16)
            for cx, cy_, r in circles[1:18]
        ]
    ).intersection(crown)
    art.fill(unary_union([trunk, *limbs]), BARK, 0.3)
    art.fill(crown, LEAF[1])
    art.fill(lit, LEAF[2])
    art.fill(top_light, LEAF[3])
    # a few dark gaps in the crown read as depth
    for _ in range(int(spread * 0.6)):
        gx, gy = x + rng.uniform(-0.4, 0.3) * spread, cy + rng.uniform(-0.1, 0.25) * height
        if crown.contains(Point(gx, gy)):
            art.put(int(gx), int(gy), LEAF[0])


def shade_pool(
    art: Art, x: float, ground: float, width: float, depth: float, rng: np.random.Generator
) -> None:
    """Shade on hot ground: cooler bands, dithered at the edge."""
    for r in range(art.rows):
        for c in range(art.cols):
            dx = (c + 0.5 - x) / (width / 2)
            dy = (r + 0.5 - ground - depth / 2) / (depth / 2)
            d = dx * dx + dy * dy
            if d < 1 and art.grid[r, c] >= 0:
                art.grid[r, c] = art.colour(
                    HEAT[1] if d + rng.uniform(-0.15, 0.15) < 0.55 else HEAT[2]
                )


# a child in school uniform, five cells wide: hair, face, white shirt, blue shorts, legs
KID_SPRITE = [
    ".HHH.",
    "HHHHH",
    ".SSS.",
    ".SSS.",
    "WWWWW",
    "SWWWS",
    "SWWWS",
    ".BBB.",
    ".B.B.",
    ".S.S.",
    ".S.S.",
]
KID_COLOURS = {"H": "hair", "S": "skin", "W": "shirt", "B": "shorts"}


def kid(art: Art, x: int, feet: int) -> None:
    top = feet - len(KID_SPRITE)
    for r, line in enumerate(KID_SPRITE):
        for c, ch in enumerate(line):
            if ch in KID_COLOURS:
                art.put(x - 2 + c, top + r, KID[KID_COLOURS[ch]])


def tree_guard(art: Art, x: int, ground: int) -> None:
    """The brick tree guard that rings every new sapling on a Delhi road."""
    for r in range(ground - 4, ground):
        for c in (x - 2, x + 2):
            art.put(c, r, "#a4553a")
    for c in range(x - 2, x + 3):
        art.put(c, ground - 4, "#b9694b")


def ground(seed: int = 3) -> Art:
    cols, rows, horizon = 320, 44, 33
    rng = np.random.default_rng(seed)
    art = Art(cols, rows)

    # the city behind the wall: blocks with water tanks, Qutub Minar, India Gate, the Lotus Temple
    blocks = []
    x = -4.0
    while x < cols + 4:
        w = rng.uniform(6, 16)
        h = rng.uniform(4, 11)
        blocks.append(box(x, horizon - h, x + w, horizon))
        if rng.random() < 0.3:
            blocks.append(box(x + w * 0.25, horizon - h - 1.6, x + w * 0.25 + 2.2, horizon - h))
        x += w + rng.uniform(1, 7)
    minar = unary_union(
        [
            Polygon(
                [
                    (64 - 2.6 + t * 0.35, horizon - t * 5.2),
                    (64 + 2.6 - t * 0.35, horizon - t * 5.2),
                    (64 + 2.6 - (t + 1) * 0.35, horizon - (t + 1) * 5.2),
                    (64 - 2.6 + (t + 1) * 0.35, horizon - (t + 1) * 5.2),
                ]
            )
            for t in range(5)
        ]
        + [
            box(
                64 - 2.9 + t * 0.35,
                horizon - (t + 1) * 5.2,
                64 + 2.9 - t * 0.35,
                horizon - (t + 1) * 5.2 + 0.8,
            )
            for t in range(5)
        ]
        + [box(63.6, horizon - 29, 64.4, horizon - 26)]
    )
    gate = unary_union(
        [
            box(196, horizon - 15, 212, horizon),
            box(195, horizon - 17, 213, horizon - 15),
            box(200, horizon - 19.5, 208, horizon - 17),
        ]
    ).difference(
        unary_union(
            [box(201.5, horizon - 9, 206.5, horizon), Point(204, horizon - 9).buffer(2.5, 16)]
        )
    )
    lotus = unary_union(
        [
            translate(
                rotate(scale(Point(0, 0).buffer(1, 16), 1.6, 5.2), a, origin=(0, 4.6)),
                268,
                horizon - 4.6,
            )
            for a in (-60, -36, -12, 12, 36, 60)
        ]
    ).intersection(box(255, horizon - 12, 281, horizon))
    art.fill(unary_union(blocks), CITY[0])
    art.fill(unary_union([minar, gate, lotus]), CITY[1])

    # hot ground: very strong near the eye, strong toward the wall, dithered between
    bayer = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16
    for r in range(horizon, rows):
        depth = (r - horizon) / (rows - horizon)
        for c in range(cols):
            hot = depth * 1.1 + 0.15 * math.sin(c / 23) + bayer[r % 4, c % 4] * 0.6 > 0.7
            art.put(c, r, HEAT[3] if hot else HEAT[2])

    trees = [(26, 30, 34, 1), (118, 22, 26, 2), (232, 27, 32, 4), (300, 20, 24, 5)]
    for x0, _, s, _ in trees:
        shade_pool(art, x0 - 4, horizon, s * 1.35, 9.0, rng)
    for x0, h, s, sd in trees:
        neem_tree(art, x0, horizon + 0.6, h, s, sd)
    # a sapling in its guard, planted this year
    sap = curve([(160, horizon), (160.3, horizon - 4), (160, horizon - 7)])
    art.fill(sap.buffer(0.4), BARK, 0.3)
    art.fill(
        unary_union(
            [
                Point(160, horizon - 8).buffer(2.4, 12),
                Point(158, horizon - 6.5).buffer(1.7, 12),
                Point(162, horizon - 6.8).buffer(1.8, 12),
            ]
        ),
        LEAF[2],
    )
    art.fill(Point(161, horizon - 8.6).buffer(1.2, 12), LEAF[3])
    tree_guard(art, 160, horizon + 1)
    # children in the shade pools, clear of the trunks
    for x0 in (12, 34, 41, 107, 128, 219, 243):
        kid(art, x0, horizon + 8)
    return art


def stars(seed: int = 7, width: int = 480, height: int = 320, count: int = 70) -> None:
    """A tile of faint square stars for the night bands; a few brighter ones in two sizes."""
    rng = np.random.default_rng(seed)
    cells = []
    for _ in range(count):
        x, y = rng.uniform(0, width - 3), rng.uniform(0, height - 3)
        size = 3 if rng.random() < 0.15 else 2
        alpha = rng.choice([0.14, 0.22, 0.32, 0.5], p=[0.4, 0.3, 0.2, 0.1])
        cells.append(
            f'<rect x="{x:.0f}" y="{y:.0f}" width="{size}" height="{size}" fill-opacity="{alpha}"/>'
        )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">'
        f'<g fill="#f4eee4">{"".join(cells)}</g></svg>'
    )
    (OUT / "stars.svg").write_text(svg)
    print(f"stars.svg: {count} cells, {len(svg) / 1024:.1f} KB")


if __name__ == "__main__":
    stars()
    branch(seed=11).svg("neem-left.svg", "xMinYMin meet")
    right = branch(seed=23)
    right.grid = right.grid[:, ::-1].copy()
    right.svg("neem-right.svg", "xMaxYMin meet")
    ground().svg("ground.svg", "xMidYMax slice")
