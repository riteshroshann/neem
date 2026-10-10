"""Pick sharp, evenly spread frames from a phone video."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def sharpness(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def extract(video: Path, out: Path, count: int = 24, long_side: int = 1024) -> list[Path]:
    """Split the video into `count` equal windows and keep the sharpest frame of each."""
    cap = cv2.VideoCapture(str(video))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        raise ValueError(f"cannot read frames from {video}")
    out.mkdir(parents=True, exist_ok=True)
    bounds = np.linspace(0, total, count + 1).astype(int)
    saved: list[Path] = []
    for k in range(count):
        best, best_score = None, -1.0
        # sample up to 8 candidates per window; motion blur is the enemy of reconstruction
        for idx in np.linspace(bounds[k], max(bounds[k], bounds[k + 1] - 1), 8).astype(int):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ok, frame = cap.read()
            if not ok:
                continue
            score = sharpness(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
            if score > best_score:
                best, best_score = frame, score
        if best is None:
            continue
        h, w = best.shape[:2]
        scale = long_side / max(h, w)
        if scale < 1:
            best = cv2.resize(
                best, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA
            )
        path = out / f"frame_{k:03d}.jpg"
        cv2.imwrite(str(path), best, [cv2.IMWRITE_JPEG_QUALITY, 92])
        saved.append(path)
    cap.release()
    return saved
