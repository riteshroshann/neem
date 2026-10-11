"""Social card and icons for the site, drawn in cells like everything else on it.

    uv run --no-project --with playwright --with pillow python tools/og/render.py

Renders tools/og/card.html with the hero globe's land mask and sun, and writes web/public/og.png,
favicon.svg, favicon-32.png and apple-touch-icon.png.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[2]
PUBLIC = REPO / "web" / "public"
SRC = REPO / "web" / "src"
PAPER = "#faf7f1"
MAX_BYTES = 300_000

# The mark: a 3x3 patch of yard, one neem cell and heat rising with distance from it.
RAMP = ["#3f7d4f", "#f1d9a7", "#e9a15a", "#d65a2e", "#8c1c30"]
MARK = [(i, j, RAMP[i + j]) for j in range(3) for i in range(3)]


def land_mask() -> dict:
    """The run-length land mask from web/src/art/land.ts, as the globe decodes it."""
    src = (SRC / "art" / "land.ts").read_text(encoding="utf-8")
    cols, rows, rle = (
        re.search(rf'{key}:\s*"?([^",\s]+)', src).group(1) for key in ("cols", "rows", "rle")
    )
    return {"cols": int(cols), "rows": int(rows), "rle": rle}


def branch() -> dict:
    """The site's right-hand neem branch as horizontal cell runs, one layer per colour."""
    svg = (PUBLIC / "art" / "neem-right.svg").read_text(encoding="utf-8")
    cols, rows = map(int, re.search(r'viewBox="0 0 (\d+) (\d+)"', svg).groups())
    layers = [
        [fill, [[int(x), int(y), int(w)] for x, y, w in re.findall(r"M(\d+) (\d+)h(\d+)", d)]]
        for fill, d in re.findall(r'<path fill="(#[0-9a-f]{6})" d="([^"]+)"', svg)
    ]
    return {"cols": cols, "rows": rows, "layers": layers}


def page_data() -> str:
    showcase = json.loads((SRC / "data" / "showcase.json").read_text(encoding="utf-8"))
    sun = showcase["sun"]  # subsolar point and the Delhi site, as the hero globe reads them
    return json.dumps({"land": land_mask(), "sun": sun, "branch": branch()})


def card() -> Image.Image:
    data = page_data()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=1)
        page.add_init_script(f"window.OG = {data};")
        page.goto((Path(__file__).parent / "card.html").as_uri())
        page.evaluate("document.fonts.ready")
        for family in ("Instrument Serif", "Geist"):
            if not page.evaluate(f"document.fonts.check('16px \"{family}\"')"):
                raise SystemExit(
                    f"{family} did not load; the card would fall back to a system font"
                )
        png = page.screenshot(clip={"x": 0, "y": 0, "width": 1200, "height": 630})
        browser.close()
    return Image.open(io.BytesIO(png)).convert("RGB")


def save_card(img: Image.Image, path: Path) -> None:
    img.save(path, optimize=True)
    # some link unfurlers drop preview images over a few hundred KB
    if path.stat().st_size > MAX_BYTES:
        raise SystemExit(f"{path.name} is {path.stat().st_size} bytes, over {MAX_BYTES}")


def mark_png(size: int, origin: int, pitch: int, cell: int, background: str | None) -> Image.Image:
    img = Image.new("RGBA", (size, size), background or (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for i, j, colour in MARK:
        x, y = origin + i * pitch, origin + j * pitch
        draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=colour)
    return img


def mark_svg() -> str:
    # 16 units with 5-unit cells and 1-unit gaps: whole pixels at 16 and 32 px
    head = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" shape-rendering="crispEdges">'
    )
    rects = "".join(
        f'<rect x="{1 + i * 5}" y="{1 + j * 5}" width="4" height="4" fill="{colour}"/>'
        for i, j, colour in MARK
    )
    return f"{head}{rects}</svg>\n"


def main() -> None:
    save_card(card(), PUBLIC / "og.png")
    (PUBLIC / "favicon.svg").write_text(mark_svg(), encoding="utf-8")
    mark_png(32, 2, 10, 8, None).save(PUBLIC / "favicon-32.png", optimize=True)
    # iOS rounds the corners itself and wants no transparency
    mark_png(180, 34, 40, 32, PAPER).convert("RGB").save(
        PUBLIC / "apple-touch-icon.png", optimize=True
    )
    for name in ("og.png", "favicon.svg", "favicon-32.png", "apple-touch-icon.png"):
        print(f"{name:22} {(PUBLIC / name).stat().st_size:>7} bytes")


if __name__ == "__main__":
    main()
