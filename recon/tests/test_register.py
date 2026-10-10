"""Registration must recover a known scale, rotation and offset from footprint geometry alone."""

import numpy as np
from neem_recon.register import excess_green, level, occupancy, register


def _l_shaped_building(rng: np.random.Generator) -> np.ndarray:
    """Points sampled over an L-shaped footprint in metres, local frame."""
    a = rng.uniform([0, 0], [40, 12], size=(4000, 2))
    b = rng.uniform([0, 12], [12, 36], size=(3000, 2))
    return np.vstack([a, b])


def test_recovers_a_known_similarity() -> None:
    rng = np.random.default_rng(3)
    local = _l_shaped_building(rng)
    true_scale, true_theta, true_t = 2.5, np.deg2rad(37.0), np.array([700_120.0, 3_180_050.0])
    c, s = np.cos(true_theta), np.sin(true_theta)
    world = local @ np.array([[c, -s], [s, c]]).T + true_t
    cloud = local / true_scale  # what VGGT would give: right shape, unknown units

    cell = 1.0
    origin = np.array([700_080.0, 3_180_120.0])
    target = occupancy(world, cell, origin, (140, 140))
    sim = register(
        cloud,
        target,
        cell,
        origin,
        scales=np.linspace(2.0, 3.0, 11),
        thetas=np.deg2rad(np.arange(0, 360, 1.0)),
    )
    assert sim.iou > 0.85
    assert abs(sim.scale - true_scale) < 0.06
    assert abs(np.rad2deg(sim.theta) - 37.0) < 1.5
    err = np.abs(sim.apply(cloud) - world).mean()
    assert err < 1.0, f"mean placement error {err:.2f} m"


def test_level_puts_the_dominant_plane_at_zero() -> None:
    rng = np.random.default_rng(1)
    ground = np.c_[rng.uniform(-10, 10, (5000, 2)), np.zeros(5000)]
    roof = np.c_[rng.uniform(-3, 3, (800, 2)), np.full(800, 6.0)]
    pts = np.vstack([ground, roof])
    tilt = np.deg2rad(20)
    rot = np.array([[1, 0, 0], [0, np.cos(tilt), -np.sin(tilt)], [0, np.sin(tilt), np.cos(tilt)]])
    out = level(pts @ rot.T + np.array([0.0, 0.0, -4.0])).xyz
    assert abs(np.median(out[:5000, 2])) < 0.05
    assert abs(abs(np.median(out[5000:, 2])) - 6.0) < 0.2


def test_excess_green_separates_leaves_from_concrete() -> None:
    rgb = np.array([[60, 140, 50], [150, 150, 150], [180, 160, 130]], dtype=np.uint8)
    exg = excess_green(rgb)
    assert exg[0] > 0.1 > exg[1] and exg[0] > exg[2]
