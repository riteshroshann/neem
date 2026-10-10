"""python -m neem_recon.cli <video> <school_id>: video to measured heights for one school."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from neem_recon.frames import extract
from neem_recon.heights import SceneArrays, measure
from neem_recon.reconstruct import reconstruct, write_ply
from neem_recon.register import excess_green, level, register


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("video", type=Path)
    ap.add_argument("school_id")
    ap.add_argument("--lake", type=Path, default=Path("../data/lake"))
    ap.add_argument("--frames", type=int, default=24, help="fewer if the GPU runs out of memory")
    args = ap.parse_args()

    started = time.perf_counter()
    work = Path("work") / args.school_id
    frames = extract(args.video, work / "frames", count=args.frames)
    print(f"frames: {len(frames)} sharp frames")

    cloud = reconstruct(frames)
    write_ply(work / "cloud_raw.ply", cloud["xyz"], cloud["rgb"])
    lv = level(cloud["xyz"])
    xyz, rgb = lv.xyz, cloud["rgb"]
    print(f"vggt: {len(xyz):,} points, ground plane holds {lv.ground_inliers:.0%}")

    scene = SceneArrays.load(args.lake / "scenes" / args.school_id)
    target = ((scene.dsm - scene.dem) > 0).astype(np.float32)
    exg = excess_green(rgb)
    span = float(np.ptp(xyz[:, 2]))
    built = xyz[(xyz[:, 2] > span * 0.15) & (exg <= 0.06)]
    # first guess at scale: the yard's mapped extent over the cloud's extent
    extent_map = np.sqrt(target.sum()) * scene.pixel
    extent_cloud = float(np.sqrt(np.prod(np.ptp(built[:, :2], axis=0)))) or 1.0
    s0 = extent_map / extent_cloud
    sim = register(
        built[:, :2],
        target,
        scene.pixel,
        np.array([scene.x0, scene.y0]),
        scales=s0 * np.geomspace(0.5, 2.0, 25),
        thetas=np.deg2rad(np.arange(0, 360, 2.0)),
    )
    xy = sim.apply(xyz[:, :2])
    heights = xyz[:, 2] * sim.scale
    print(
        f"register: scale {sim.scale:.3f} m/unit, rotation {np.rad2deg(sim.theta):.1f} deg, "
        f"footprint IoU {sim.iou:.2f}"
    )

    result = measure(scene, xy, heights, exg)
    np.savez_compressed(
        args.lake / "scenes" / args.school_id / "scene_recon.npz",
        dsm=result["dsm"],
        dem=scene.dem,
        cdsm=result["cdsm"],
        zones=scene.zones,
    )
    keep = np.random.default_rng(0).choice(len(xy), min(len(xy), 150_000), replace=False)
    local = np.c_[xy[keep, 0] - scene.x0, scene.y0 - xy[keep, 1], heights[keep]].astype(np.float32)
    np.savez_compressed(work / "cloud_local.npz", xyz=local, rgb=rgb[keep])
    report = {
        "school_id": args.school_id,
        "frames": len(frames),
        "points": len(xyz),
        "ground_inliers": round(lv.ground_inliers, 3),
        "scale_m_per_unit": round(sim.scale, 4),
        "rotation_deg": round(float(np.rad2deg(sim.theta)), 2),
        "footprint_iou": round(sim.iou, 3),
        "buildings_measured": result["buildings_measured"],
        "tree_cells_added": result["tree_cells_added"],
        "seconds": round(time.perf_counter() - started, 1),
    }
    (work / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    if sim.iou < 0.4:
        print("warning: weak footprint match; check the video covers the school building")


if __name__ == "__main__":
    main()
