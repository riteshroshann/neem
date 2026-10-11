"""The yard film: a 12 s loop of one school's heat twin in 3D, for the night band on the home page.

    uv run --no-project --with playwright,imageio-ffmpeg,pillow python tools/three-d/render.py

Drives tools/three-d/render.html in headless Chromium, on the GPU through ANGLE or on SwiftShader
when there is none, saves every frame, and encodes web/public/media/kv-3d.webm, kv-3d.mp4 and the
kv-3d.jpg poster. Pass --encode-only to re-encode frames already rendered.
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg
from PIL import Image
from playwright.sync_api import Error, Page, Playwright, sync_playwright

REPO = Path(__file__).resolve().parents[2]
TWIN = REPO / "web" / "public" / "twins" / "osm-w1321574340"  # KV Sector 25, Rohini
MEDIA = REPO / "web" / "public" / "media"
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


def page_data() -> str:
    summary = json.loads((TWIN / "twin.json").read_text(encoding="utf-8"))
    design = json.loads((TWIN / "plan.json").read_text(encoding="utf-8"))["design"]
    hours = json.loads((TWIN / "calibration.json").read_text(encoding="utf-8"))["hours"]
    # the page grows neem crowns only; anything else in the plan would go missing silently
    if design["sails"] or any(t["species"] != "neem" for t in design["trees"]):
        raise SystemExit("render.html draws neem trees only; this plan has more")
    sun = next(h for h in hours if h["label"] == "13:00")

    def b64(name: str) -> str:
        return base64.b64encode((TWIN / name).read_bytes()).decode()

    return json.dumps(
        {
            "summary": summary,
            "trees": design["trees"],
            "sun": {"altitude": sun["altitude"], "azimuth": sun["azimuth"]},
            "layers": b64("layers.bin.gz"),
            "maps": {
                "today": "data:image/png;base64," + b64("map-1pm.png"),
                "plan": "data:image/png;base64," + b64("map-1pm-plan.png"),
            },
            "frame": {"width": SIZE[0], "height": SIZE[1], "scale": SCALE},
        }
    )


def open_page(p: Playwright) -> tuple[Page, str, dict]:
    """The page on the GPU when Chromium gets one, else on SwiftShader."""
    data = page_data()
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


def render(frames: Path) -> None:
    grab = "t => { renderAt(t); return document.querySelector('canvas').toDataURL('image/png'); }"
    with sync_playwright() as p:
        page, name, info = open_page(p)
        print(f"{name}: {info['gl']}, orbit {info['distance']:.0f} m, {info['trees']} trees")
        for i in range(FRAMES):
            url = page.evaluate(grab, i / FPS)
            (frames / f"f{i:04d}.png").write_bytes(base64.b64decode(url.split(",", 1)[1]))


def ffmpeg(*args: str) -> None:
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", *args], check=True)


def encode(frames: Path) -> None:
    w, h = SIZE
    src = ["-framerate", str(FPS), "-i", str(frames / "f%04d.png"), "-an"]
    # Average the 2x frames down to bt709 limited range. The tags go on the frames: ffmpeg 7
    # writes those and drops -color_primaries and -color_trc given as encoder options.
    yuv = f"scale={w}:{h}:flags=area:out_color_matrix=bt709:out_range=tv,format=yuv420p"
    tags = "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv"
    vf = ["-vf", f"{yuv},{tags}"]
    vp9 = ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "34", "-row-mt", "1"]
    vp9 += ["-deadline", "good", "-cpu-used", "1", "-passlogfile", str(frames / "vp9")]
    ffmpeg(*src, *vf, *vp9, "-pass", "1", "-f", "null", "-")
    ffmpeg(*src, *vf, *vp9, "-pass", "2", str(MEDIA / "kv-3d.webm"))
    x264 = ["-c:v", "libx264", "-preset", "veryslow", "-crf", "26", "-profile:v", "high"]
    ffmpeg(*src, *vf, *x264, "-movflags", "+faststart", str(MEDIA / "kv-3d.mp4"))
    poster = Image.open(frames / f"f{round(POSTER_T * FPS):04d}.png").convert("RGB")
    poster.reduce(SCALE).save(MEDIA / "kv-3d.jpg", quality=82, optimize=True, progressive=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--frames", type=Path, default=Path(tempfile.gettempdir()) / "neem-kv-3d")
    parser.add_argument("--encode-only", action="store_true")
    args = parser.parse_args()
    args.frames.mkdir(parents=True, exist_ok=True)
    MEDIA.mkdir(parents=True, exist_ok=True)
    if not args.encode_only:
        render(args.frames)
    encode(args.frames)
    for name, limit in BUDGET.items():
        size = (MEDIA / name).stat().st_size
        print(f"{name:11} {size:>9,} bytes")
        if size > limit:
            raise SystemExit(f"{name} is over its {limit:,} byte budget")


if __name__ == "__main__":
    main()
