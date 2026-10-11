"""One school's heat twin in 3D, rendered frame by frame for the night bands on the home page.

    uv run --no-project --with playwright,imageio-ffmpeg,pillow python tools/three-d/render.py

Drives tools/three-d/render.html in headless Chromium, on the GPU through ANGLE or on SwiftShader
when there is none, and saves every frame at twice the size. By default it makes the yard film, a
12 s loop of the planting: web/public/media/kv-3d.webm, kv-3d.mp4 and the kv-3d.jpg poster.

--future grows the same planting through the ages in web/src/data/future.json: one still per age,
future-y{age}.jpg, and a 16 s one-way ride from seed to thirty years, future-ride.webm and .mp4,
its last frame as future-ride.jpg, and future-ride.json with the age shown on every frame.

Pass --encode-only to re-encode frames already rendered. On a cp1252 console, run python -I -X utf8.
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import subprocess
import tempfile
from bisect import bisect_right
from itertools import pairwise
from pathlib import Path
from typing import Any

import imageio_ffmpeg
from PIL import Image
from playwright.sync_api import Error, Page, Playwright, sync_playwright

REPO = Path(__file__).resolve().parents[2]
TWIN = REPO / "web" / "public" / "twins" / "osm-w1321574340"  # KV Sector 25, Rohini
MEDIA = REPO / "web" / "public" / "media"
PUBLIC = REPO / "web" / "public"
FUTURE = REPO / "web" / "src" / "data" / "future.json"  # neem-data publish: the plan at each age
FPS = 30
FRAMES = 12 * FPS
SIZE = (1280, 800)
SCALE = 2  # render at twice the size and average down: clean edges on a 1 m grid
POSTER_T = 6.2  # early in the hold: the plan at full size, the grove in front of the school
# the page embeds these as a 16:10 film; past this they start to weigh on the home page
BUDGET = {"kv-3d.webm": 3_000_000, "kv-3d.mp4": 3_500_000, "kv-3d.jpg": 180_000}
GL_PATHS = {
    "gpu": ["--enable-gpu", "--use-angle=d3d11"],
    "swiftshader": ["--use-gl=swiftshader"],
}

# The ride is scrubbed by scroll, so it runs one way and keys often. Every modelled age lands on
# a whole frame, the last at RISE_S; a hold on it fills the rest.
RIDE_FRAMES = 16 * FPS
RISE_S = 14.5
FADE = 15  # frames over which the ground fades into a stage's own map, ending on that stage
KEYINT = 10  # a keyframe every ten frames: a scrub never decodes more than nine
# libvpx's constant quality spends freely on keyframes and the ride has 48, so its VP9 caps the
# average rate as well (about 3.7 MB); crf 34 stays the ceiling
RIDE_VP9_RATE = "1850k"
STILL_BUDGET = 140_000
RIDE_BUDGET = 4_000_000

Stage = dict[str, Any]


def page_data(stages: list[Stage] | None = None) -> str:
    summary = json.loads((TWIN / "twin.json").read_text(encoding="utf-8"))
    design = json.loads((TWIN / "plan.json").read_text(encoding="utf-8"))["design"]
    hours = json.loads((TWIN / "calibration.json").read_text(encoding="utf-8"))["hours"]
    # the page grows neem crowns only; anything else in the plan would go missing silently
    if design["sails"] or any(t["species"] != "neem" for t in design["trees"]):
        raise SystemExit("render.html draws neem trees only; this plan has more")
    sun = next(h for h in hours if h["label"] == "13:00")

    def b64(path: Path) -> str:
        return base64.b64encode(path.read_bytes()).decode()

    def png(path: Path) -> str:
        return "data:image/png;base64," + b64(path)

    data: dict[str, Any] = {
        "summary": summary,
        "trees": design["trees"],
        "sun": {"altitude": sun["altitude"], "azimuth": sun["azimuth"]},
        "layers": b64(TWIN / "layers.bin.gz"),
    }
    if stages is None:
        data["maps"] = {"today": png(TWIN / "map-1pm.png"), "plan": png(TWIN / "map-1pm-plan.png")}
    else:
        maps = [png(PUBLIC / s["map"].lstrip("/")) for s in stages]
        data["future"] = {"stages": [s | {"map": m} for s, m in zip(stages, maps, strict=True)]}
    data["frame"] = {"width": SIZE[0], "height": SIZE[1], "scale": SCALE}
    return json.dumps(data)


def open_page(p: Playwright, data: str) -> tuple[Page, str, dict]:
    """The page on the GPU when Chromium gets one, else on SwiftShader."""
    for name, args in GL_PATHS.items():
        browser = p.chromium.launch(
            channel="chromium",
            args=["--allow-file-access-from-files", "--ignore-gpu-blocklist", *args],
        )
        page = browser.new_page(viewport={"width": SIZE[0], "height": SIZE[1]})
        page.add_init_script(f"window.KV = {data};")
        page.goto((Path(__file__).parent / "render.html").as_uri())
        page.wait_for_function("() => window.ready !== undefined")
        try:
            info = page.evaluate("window.ready")
        except Error as e:  # no WebGL on this path
            print(f"{name}: {e.message.splitlines()[0]}")
            browser.close()
            continue
        if name == "gpu" and "SwiftShader" in info["gl"]:
            browser.close()
            continue
        return page, name, info
    raise SystemExit("headless Chromium has no WebGL here")


def save_png(url: str, path: Path) -> None:
    path.write_bytes(base64.b64decode(url.split(",", 1)[1]))


def render(frames: Path) -> None:
    grab = "t => { renderAt(t); return document.querySelector('canvas').toDataURL('image/png'); }"
    with sync_playwright() as p:
        page, name, info = open_page(p, page_data())
        print(f"{name}: {info['gl']}, orbit {info['distance']:.0f} m, {info['trees']} trees")
        for i in range(FRAMES):
            save_png(page.evaluate(grab, i / FPS), frames / f"f{i:04d}.png")


def ffmpeg(*args: str) -> None:
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", *args], check=True)


def jpeg(frame: Path, out: Path) -> None:
    """A 2x frame averaged down to a progressive JPEG."""
    image = Image.open(frame).convert("RGB").reduce(SCALE)
    image.save(out, quality=82, optimize=True, progressive=True)


def encode(frames: Path, stem: str, poster: int, *, keyint: int = 0, vp9_rate: str = "0") -> None:
    """WebM, MP4 and a poster from the 2x frames. vp9_rate 0 is constant quality."""
    w, h = SIZE
    src = ["-framerate", str(FPS), "-i", str(frames / "f%04d.png"), "-an"]
    # Average the 2x frames down to bt709 limited range. The tags go on the frames: ffmpeg 7
    # writes those and drops -color_primaries and -color_trc given as encoder options.
    yuv = f"scale={w}:{h}:flags=area:out_color_matrix=bt709:out_range=tv,format=yuv420p"
    tags = "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv"
    vf = ["-vf", f"{yuv},{tags}"]
    gop = ["-g", str(keyint), "-keyint_min", str(keyint)] if keyint else []
    vp9 = ["-c:v", "libvpx-vp9", "-b:v", vp9_rate, "-crf", "34", "-row-mt", "1", *gop]
    vp9 += ["-deadline", "good", "-cpu-used", "1", "-passlogfile", str(frames / "vp9")]
    ffmpeg(*src, *vf, *vp9, "-pass", "1", "-f", "null", "-")
    ffmpeg(*src, *vf, *vp9, "-pass", "2", str(MEDIA / f"{stem}.webm"))
    x264 = ["-c:v", "libx264", "-preset", "veryslow", "-crf", "26", "-profile:v", "high"]
    x264 += [*gop, "-sc_threshold", "0"] if keyint else []
    ffmpeg(*src, *vf, *x264, "-movflags", "+faststart", str(MEDIA / f"{stem}.mp4"))
    jpeg(frames / f"f{poster:04d}.png", MEDIA / f"{stem}.jpg")


def film(frames: Path, encode_only: bool) -> dict[str, int]:
    if not encode_only:
        render(frames)
    encode(frames, "kv-3d", round(POSTER_T * FPS))
    return BUDGET


def read_stages() -> list[Stage]:
    """The planting at each modelled age: tree height, crown radius and that run's 1 pm map."""
    future = json.loads(FUTURE.read_text(encoding="utf-8"))
    planted = json.loads((TWIN / "plan.json").read_text(encoding="utf-8"))["design"]["trees"]
    if future["school_id"] != TWIN.name or future["trees"] != len(planted):
        raise SystemExit(f"{FUTURE.name} grows another planting than {TWIN.name}'s plan")
    today, *grown = future["stages"]
    if today["years"] != 0 or "height_m" in today:
        raise SystemExit(f"{FUTURE.name} must start from the yard as it is, with no new trees")
    stages = [{"years": 0, "height": 0.0, "radius": 0.0, "map": today["map"]}]
    for s in grown:
        stages.append(
            {
                "years": s["years"],
                "height": s["height_m"],
                "radius": s["crown_m"] / 2,
                "map": s["map"],
            }
        )
    ages = [s["years"] for s in stages]
    if any(b <= a for a, b in pairwise(ages)):
        raise SystemExit(f"{FUTURE.name} ages must rise: {ages}")
    return stages


def shown(age: float) -> float:
    """An age as the page shows it: floored, so no frame shows an age before the frame that
    reaches it."""
    return math.floor(age * 100) / 100


def smoother(u: float) -> float:
    x = min(1.0, max(0.0, u))
    return x * x * x * (x * (6 * x - 15) + 10)


def size_at(stages: list[Stage], age: float) -> tuple[float, float]:
    """Tree height and crown radius at an age: linear between the modelled stages."""
    for a, b in pairwise(stages):
        if age <= b["years"]:
            u = (age - a["years"]) / (b["years"] - a["years"])
            return (
                a["height"] + u * (b["height"] - a["height"]),
                a["radius"] + u * (b["radius"] - a["radius"]),
            )
    return stages[-1]["height"], stages[-1]["radius"]


def timeline(stages: list[Stage]) -> tuple[list[int], list[float]]:
    """The frame each modelled age is reached on, and the age on every frame of the ride.

    Age a is reached at RISE_S * sqrt(a / last age), so the early years get the time and still
    read. In between, the age follows a monotone cubic through those frames with flat ends
    (Fritsch-Carlson): growth eases in and out, never runs backwards, and each stage is exact.
    """
    ages = [s["years"] for s in stages]
    knots = [round(RISE_S * FPS * (a / ages[-1]) ** 0.5) for a in ages]
    if any(b - a <= FADE for a, b in pairwise(knots)):
        raise SystemExit(f"stages too close for a {FADE}-frame fade: frames {knots}")
    slope = [(ages[k + 1] - ages[k]) / (knots[k + 1] - knots[k]) for k in range(len(ages) - 1)]
    tangent = [0.0]
    for k in range(1, len(ages) - 1):
        h0, h1 = knots[k] - knots[k - 1], knots[k + 1] - knots[k]
        w0, w1 = 2 * h1 + h0, h1 + 2 * h0
        tangent.append((w0 + w1) / (w0 / slope[k - 1] + w1 / slope[k]))
    tangent.append(0.0)
    years = []
    for f in range(RIDE_FRAMES):
        if f >= knots[-1]:
            years.append(float(ages[-1]))
            continue
        k = bisect_right(knots, f) - 1
        h = knots[k + 1] - knots[k]
        s = (f - knots[k]) / h
        years.append(
            (2 * s**3 - 3 * s**2 + 1) * ages[k]
            + (s**3 - 2 * s**2 + s) * h * tangent[k]
            + (-2 * s**3 + 3 * s**2) * ages[k + 1]
            + (s**3 - s**2) * h * tangent[k + 1]
        )
    return knots, years


def ride_states(stages: list[Stage], knots: list[int], years: list[float]) -> list[dict]:
    """What the page draws on each frame: tree size, the ground's maps and the camera."""
    states = []
    for f, age in enumerate(years):
        k = bisect_right(knots, f) - 1
        ground = [k, k, 0.0]
        if k + 1 < len(knots) and f > knots[k + 1] - FADE:
            ground = [k, k + 1, smoother((f - (knots[k + 1] - FADE)) / FADE)]
        height, radius = size_at(stages, age)
        view = smoother(f / (RIDE_FRAMES - 1))
        states.append({"height": height, "radius": radius, "ground": ground, "view": view})
    return states


def render_future(frames: Path, stages: list[Stage], states: list[dict]) -> None:
    grab = "s => { drawFuture(s); return document.querySelector('canvas').toDataURL('image/png'); }"
    (frames / "ride").mkdir(exist_ok=True)
    with sync_playwright() as p:
        page, name, info = open_page(p, page_data(stages))
        views = ", ".join(f"{k} {v['distance']:.0f} m" for k, v in info["views"].items())
        print(f"{name}: {info['gl']}, {info['trees']} trees, cameras {views}")
        for k, s in enumerate(stages):
            still = {
                "height": s["height"],
                "radius": s["radius"],
                "ground": [k, k, 0],
                "view": "still",
            }
            save_png(page.evaluate(grab, still), frames / f"still-y{s['years']}.png")
        for i, state in enumerate(states):
            save_png(page.evaluate(grab, state), frames / "ride" / f"f{i:04d}.png")


def future(frames: Path, encode_only: bool) -> dict[str, int]:
    stages = read_stages()
    knots, years = timeline(stages)
    if not encode_only:
        render_future(frames, stages, ride_states(stages, knots, years))
    stills = [f"future-y{s['years']}.jpg" for s in stages]
    for s, name in zip(stages, stills, strict=True):
        jpeg(frames / f"still-y{s['years']}.png", MEDIA / name)
    encode(frames / "ride", "future-ride", RIDE_FRAMES - 1, keyint=KEYINT, vp9_rate=RIDE_VP9_RATE)
    track = {
        "fps": FPS,
        "frames": RIDE_FRAMES,
        "duration": RIDE_FRAMES / FPS,
        "years": [shown(y) for y in years],
        "stages": [{"years": s["years"], "frame": f} for s, f in zip(stages, knots, strict=True)],
    }
    path = MEDIA / "future-ride.json"
    path.write_text(json.dumps(track) + "\n", encoding="utf-8", newline="\n")
    budget = dict.fromkeys(stills, STILL_BUDGET)
    budget |= {"future-ride.webm": RIDE_BUDGET, "future-ride.mp4": RIDE_BUDGET}
    return budget | {"future-ride.jpg": STILL_BUDGET}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--future", action="store_true", help="grow the planting to 30 years")
    parser.add_argument(
        "--frames", type=Path, help="where the 2x frames go; a temp folder if unset"
    )
    parser.add_argument("--encode-only", action="store_true")
    args = parser.parse_args()
    temp = Path(tempfile.gettempdir()) / ("neem-future" if args.future else "neem-kv-3d")
    frames = args.frames or temp
    frames.mkdir(parents=True, exist_ok=True)
    MEDIA.mkdir(parents=True, exist_ok=True)
    budget = future(frames, args.encode_only) if args.future else film(frames, args.encode_only)
    for name, limit in budget.items():
        size = (MEDIA / name).stat().st_size
        print(f"{name:17} {size:>9,} bytes")
        if size > limit:
            raise SystemExit(f"{name} is over its {limit:,} byte budget")


if __name__ == "__main__":
    main()
