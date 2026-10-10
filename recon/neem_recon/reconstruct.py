"""VGGT: frames in, a dense coloured point cloud out, in the first camera's frame."""

from __future__ import annotations

from pathlib import Path

import numpy as np


def reconstruct(frames: list[Path], keep: float = 0.5) -> dict[str, np.ndarray]:
    """Run VGGT and keep the most confident `keep` share of pixels.

    Points come from depth unprojected with the predicted cameras, which VGGT's authors find
    more accurate than the direct point-map head.
    """
    import torch
    from vggt.models.vggt import VGGT
    from vggt.utils.geometry import unproject_depth_map_to_point_map
    from vggt.utils.load_fn import load_and_preprocess_images
    from vggt.utils.pose_enc import pose_encoding_to_extri_intri

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if device == "cuda" else torch.float32
    model = VGGT.from_pretrained("facebook/VGGT-1B").to(device).eval()
    images = load_and_preprocess_images([str(f) for f in frames]).to(device)
    with torch.no_grad(), torch.autocast(device_type=device, dtype=dtype, enabled=device == "cuda"):
        pred = model(images)
    extri, intri = pose_encoding_to_extri_intri(pred["pose_enc"], images.shape[-2:])
    depth = pred["depth"].float().cpu().numpy().squeeze(0)
    conf = pred["depth_conf"].float().cpu().numpy().squeeze(0)
    points = unproject_depth_map_to_point_map(
        depth, extri.float().cpu().numpy().squeeze(0), intri.float().cpu().numpy().squeeze(0)
    )
    rgb = (images.permute(0, 2, 3, 1).float().cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
    flat_conf = conf.reshape(-1)
    threshold = np.quantile(flat_conf, 1 - keep)
    mask = flat_conf >= threshold
    return {
        "xyz": points.reshape(-1, 3)[mask].astype(np.float32),
        "rgb": rgb.reshape(-1, 3)[mask],
        "conf": flat_conf[mask].astype(np.float32),
    }


def write_ply(path: Path, xyz: np.ndarray, rgb: np.ndarray) -> None:
    header = (
        "ply\nformat binary_little_endian 1.0\n"
        f"element vertex {len(xyz)}\n"
        "property float x\nproperty float y\nproperty float z\n"
        "property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n"
    )
    rec = np.empty(len(xyz), dtype=[("p", "<f4", 3), ("c", "u1", 3)])
    rec["p"], rec["c"] = xyz, rgb
    with path.open("wb") as f:
        f.write(header.encode())
        f.write(rec.tobytes())
