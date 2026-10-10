"""Put a VGGT cloud on the map.

VGGT's frame has no scale, no north and no ground. We level it with a RANSAC ground plane,
split points into built and green by height and an excess-green index, then find the
similarity transform (scale, rotation, offset) that best overlays the built points on the
school's mapped building footprint. The search is brute force over rotation and scale, with
the offset for each candidate found by FFT cross-correlation.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Levelled:
    xyz: np.ndarray  # ground at z = 0, z up, still in VGGT units
    ground_inliers: float


@dataclass(frozen=True)
class Similarity:
    scale: float  # metres per VGGT unit
    theta: float  # radians, counter-clockwise from the cloud's x axis to east
    tx: float  # metres, map easting of the cloud origin
    ty: float  # metres, map northing of the cloud origin
    iou: float

    def apply(self, xy: np.ndarray) -> np.ndarray:
        c, s = np.cos(self.theta), np.sin(self.theta)
        rot = np.array([[c, -s], [s, c]])
        return (xy * self.scale) @ rot.T + np.array([self.tx, self.ty])


def level(xyz: np.ndarray, iters: int = 400, tol: float | None = None, seed: int = 0) -> Levelled:
    """Fit the dominant plane (the yard) and rotate it to z = 0 with the camera side up."""
    rng = np.random.default_rng(seed)
    span = float(np.linalg.norm(np.ptp(xyz, axis=0)))
    tol = tol or span * 0.005
    best_n, best_d, best_count = np.array([0.0, 0.0, 1.0]), 0.0, -1
    sample = xyz[rng.choice(len(xyz), min(len(xyz), 200_000), replace=False)]
    for _ in range(iters):
        a, b, c = sample[rng.choice(len(sample), 3, replace=False)]
        n = np.cross(b - a, c - a)
        norm = np.linalg.norm(n)
        if norm < 1e-9:
            continue
        n /= norm
        d = -float(n @ a)
        count = int((np.abs(sample @ n + d) < tol).sum())
        if count > best_count:
            best_n, best_d, best_count = n, d, count
    # Cameras look down at the yard from above it: orient the normal toward the origin side.
    if best_d < 0:
        best_n, best_d = -best_n, -best_d
    z = np.array([0.0, 0.0, 1.0])
    v = np.cross(best_n, z)
    s, c = np.linalg.norm(v), float(best_n @ z)
    if s < 1e-9:
        rot = np.eye(3) if c > 0 else np.diag([1.0, -1.0, -1.0])
    else:
        vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
        rot = np.eye(3) + vx + vx @ vx * ((1 - c) / s**2)
    out = xyz @ rot.T
    out[:, 2] += best_d
    return Levelled(out, best_count / len(sample))


def excess_green(rgb: np.ndarray) -> np.ndarray:
    f = rgb.astype(np.float32) + 1.0
    total = f.sum(axis=1)
    r, g, b = (f[:, k] / total for k in range(3))
    return 2 * g - r - b


def occupancy(
    xy: np.ndarray, cell: float, origin: np.ndarray, shape: tuple[int, int]
) -> np.ndarray:
    grid = np.zeros(shape, dtype=np.float32)
    cols = np.floor((xy[:, 0] - origin[0]) / cell).astype(int)
    rows = np.floor((origin[1] - xy[:, 1]) / cell).astype(int)
    ok = (rows >= 0) & (rows < shape[0]) & (cols >= 0) & (cols < shape[1])
    np.add.at(grid, (rows[ok], cols[ok]), 1.0)
    return (grid > 0).astype(np.float32)


def _best_shift(target: np.ndarray, source: np.ndarray) -> tuple[int, int, float]:
    """Integer (drow, dcol) maximising overlap of source shifted onto target, and the IoU."""
    f = np.fft.rfft2(target) * np.conj(np.fft.rfft2(source))
    corr = np.fft.irfft2(f, s=target.shape)
    r, c = np.unravel_index(int(np.argmax(corr)), corr.shape)
    dr = r if r <= target.shape[0] // 2 else r - target.shape[0]
    dc = c if c <= target.shape[1] // 2 else c - target.shape[1]
    inter = float(corr[r, c])
    union = float(target.sum() + source.sum() - inter)
    return int(dr), int(dc), inter / union if union > 0 else 0.0


def register(
    built_xy: np.ndarray,
    target: np.ndarray,
    cell: float,
    target_origin: np.ndarray,
    scales: np.ndarray,
    thetas: np.ndarray,
) -> Similarity:
    """Search rotation and scale; translation by cross-correlation on a grid shaped like target."""
    rows, cols = target.shape
    centre_map = target_origin + np.array([cols * cell / 2, -rows * cell / 2])
    centroid = built_xy.mean(axis=0)
    best = Similarity(1.0, 0.0, 0.0, 0.0, -1.0)
    for theta in thetas:
        c, s = np.cos(theta), np.sin(theta)
        rot = np.array([[c, -s], [s, c]])
        for scale in scales:
            placed = ((built_xy - centroid) * scale) @ rot.T + centre_map
            src = occupancy(placed, cell, target_origin, target.shape)
            if src.sum() == 0:
                continue
            dr, dc, iou = _best_shift(target, src)
            if iou > best.iou:
                shift = np.array([dc * cell, -dr * cell])
                origin = centre_map - (centroid * scale) @ rot.T + shift
                best = Similarity(
                    float(scale), float(theta), float(origin[0]), float(origin[1]), iou
                )
    return best
