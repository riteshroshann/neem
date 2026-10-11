from pathlib import Path

import numpy as np
import pytest
from fixtures import yard
from hypothesis import given, settings
from hypothesis import strategies as st

from neem_core.interventions import ShadeSail, Tree, apply, total_cost
from neem_core.scene import ZONE_BUILDING, Scene


def test_scene_round_trips_through_disk(tmp_path: Path) -> None:
    scene = yard()
    scene.save(tmp_path)
    loaded = Scene.load(tmp_path)
    assert loaded.grid == scene.grid
    assert np.array_equal(loaded.dsm, scene.dsm)
    assert np.array_equal(loaded.zones, scene.zones)


def test_scene_rejects_relative_dsm() -> None:
    scene = yard()
    with pytest.raises(ValueError, match="absolute"):
        Scene(
            scene.school_id,
            scene.name,
            scene.grid,
            scene.dsm - 210,
            scene.dem,
            scene.cdsm,
            scene.zones,
        )


def test_tree_adds_canopy_at_its_trunk_and_nowhere_beyond_its_crown() -> None:
    scene = yard()
    x, y = scene.grid.to_map(100.5, 100.5)
    out = apply(scene, [Tree(x, y, "neem")])
    assert out.cdsm[100, 100] == pytest.approx(7.0, abs=0.2)
    assert out.cdsm[100, 106] == 0.0  # 5.5 m from the trunk, crown radius is 3.5 m
    assert scene.cdsm[100, 100] == 0.0  # input untouched


def test_nothing_is_planted_on_a_roof() -> None:
    scene = yard()
    x, y = scene.grid.to_map(20.5, 50.5)  # inside the main block
    out = apply(scene, [ShadeSail(x, y, 10, 10)])
    assert out.cdsm[scene.zones == ZONE_BUILDING].max() == 0.0


def test_cost_adds_up() -> None:
    assert total_cost([Tree(0, 0, "neem"), ShadeSail(0, 0, 5, 4)]) == 3_500 + 20 * 1_800


coords = st.tuples(st.floats(0, 119), st.floats(0, 119))


@settings(max_examples=40, deadline=None)
@given(st.lists(coords, max_size=6))
def test_interventions_only_ever_add_canopy_and_order_does_not_matter(points) -> None:
    scene = yard()
    trees = [Tree(*scene.grid.to_map(r, c)) for r, c in points]
    forward = apply(scene, trees)
    backward = apply(scene, list(reversed(trees)))
    assert np.all(forward.cdsm >= scene.cdsm)
    assert np.allclose(forward.cdsm, backward.cdsm)


def test_an_older_tree_casts_a_wider_canopy() -> None:
    from neem_core.interventions import NEEM_BY_AGE

    scene = yard()
    rows, cols = np.nonzero(scene.zones == 1)  # open ground: trees are never planted on roofs
    mid = len(rows) // 2
    x, y = scene.grid.to_map(rows[mid] + 0.5, cols[mid] + 0.5)
    young = apply(scene, [Tree(x, y, "neem")])
    old = apply(scene, [Tree(x, y, "neem", NEEM_BY_AGE[30])])
    assert (old.cdsm > 0).sum() > (young.cdsm > 0).sum()
    assert old.cdsm.max() > young.cdsm.max()
