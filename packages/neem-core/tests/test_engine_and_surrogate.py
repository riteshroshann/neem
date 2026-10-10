"""Slow tests: SOLWEIG itself, and the differential checks that keep T0 honest against it."""

from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
from fixtures import yard

from neem_core.engine import SolweigEngine
from neem_core.interventions import Tree, apply
from neem_core.met import MetHour, Site
from neem_core.scene import ZONE_BUILDING
from neem_core.shadow import sunlit_fraction
from neem_core.surrogate import fit, predict

pytestmark = pytest.mark.slow

SITE = Site(latitude=28.75, longitude=77.12, altitude=212.0, utc_offset=5.5)

# Delhi, Monday 27 April 2026 (ERA5 via Open-Meteo)
HOURS = [
    MetHour(datetime(2026, 4, 27, 9), 36.6, 19, 541, 536.2, 185, 1.64, 979.9),
    MetHour(datetime(2026, 4, 27, 11), 39.9, 15, 830, 659.1, 227, 2.51, 979.1),
    MetHour(datetime(2026, 4, 27, 13), 42.1, 14, 870, 669.7, 233, 3.58, 977.5),
]


@pytest.fixture(scope="module")
def engine(tmp_path_factory: pytest.TempPathFactory) -> SolweigEngine:
    return SolweigEngine(Path(tmp_path_factory.mktemp("solweig")))


def _trees(scene, seed: int, n: int = 8) -> list[Tree]:
    rng = np.random.default_rng(seed)
    rows, cols = np.nonzero(scene.zones != ZONE_BUILDING)
    pick = rng.choice(len(rows), n, replace=False)
    return [Tree(*scene.grid.to_map(rows[i] + 0.5, cols[i] + 0.5)) for i in pick]


def test_shade_is_cooler_than_sun(engine: SolweigEngine) -> None:
    scene = yard()
    field = engine.run(scene, HOURS, SITE)
    assert field.tmrt.shape == (3, *scene.grid.shape)
    noon = HOURS.index(HOURS[2])
    open_ground = field.tmrt[noon][100, 20]
    under_tree = field.tmrt[noon][85, 60]
    assert 55 < open_ground < 80
    assert open_ground - under_tree > 10


def test_engine_leaves_the_scene_untouched(engine: SolweigEngine) -> None:
    scene = yard()
    before = [a.copy() for a in (scene.dsm, scene.dem, scene.cdsm)]
    engine.run(scene, HOURS[:1], SITE)
    for b, a in zip(before, (scene.dsm, scene.dem, scene.cdsm), strict=True):
        assert np.array_equal(a, b)


def test_fast_shadows_agree_with_solweig(engine: SolweigEngine) -> None:
    scene = yard()
    field = engine.run(scene, HOURS, SITE)
    ground = scene.zones != ZONE_BUILDING
    for k, hour in enumerate(HOURS):
        sun = hour.sun(SITE)
        ours = sunlit_fraction(scene.dsm, scene.dem, scene.cdsm, 1.0, sun.altitude, sun.azimuth)
        lit_ours = ours[ground] > 0.5
        lit_ref = field.sunlit[k][ground] > 0.5
        agreement = float(np.mean(lit_ours == lit_ref))
        assert agreement > 0.97, f"{hour.label}: {agreement:.3f}"


def test_t0_tracks_t1_on_an_unseen_design(engine: SolweigEngine) -> None:
    base = yard()
    planted = apply(base, _trees(base, seed=1))
    unseen = apply(base, _trees(base, seed=2))
    base_field = engine.run(base, HOURS, SITE)
    probe = engine.run(planted, HOURS, SITE)
    cal = fit(base, base_field, [planted], [probe], SITE)
    truth = engine.run(unseen, HOURS, SITE)
    tmrt, _ = predict(cal, unseen, base, base_field)
    ground = unseen.zones != ZONE_BUILDING
    err = np.abs(tmrt - truth.tmrt)[:, ground]
    changed = np.abs(truth.tmrt - base_field.tmrt)[:, ground] > 0.5
    assert float(err.mean()) < 1.0, f"T0 MAE over the yard {err.mean():.2f} C"
    assert float(err[changed].mean()) < 3.0, (
        f"T0 MAE where the design acts {err[changed].mean():.2f} C"
    )
