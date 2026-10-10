import numpy as np
from fixtures import yard

from neem_agent.sites import hottest_sites, plantable
from neem_core.scene import ZONE_BUILDING


def test_sites_are_hottest_first_spaced_and_never_on_roofs_or_canopy() -> None:
    scene = yard()
    heat = np.zeros(scene.grid.shape, dtype=np.float32)
    heat[100:110, 90:100] = 50.0  # one hot patch in the south-east
    heat[60:70, 60:70] = 45.0
    sites = hottest_sites(scene, heat, count=6, spacing_m=7.0)
    assert len(sites) == 6
    r0, c0 = scene.grid.to_pixel(*sites[0])
    assert heat[int(r0), int(c0)] == 50.0
    for i, (x, y) in enumerate(sites):
        r, c = (int(v) for v in scene.grid.to_pixel(x, y))
        assert scene.zones[r, c] != ZONE_BUILDING
        assert scene.cdsm[r, c] == 0
        for x2, y2 in sites[i + 1 :]:
            assert (x - x2) ** 2 + (y - y2) ** 2 >= 7.0**2


def test_taken_circles_are_respected() -> None:
    scene = yard()
    x, y = scene.grid.to_map(100.5, 100.5)
    ok = plantable(scene, taken=[(x, y, 5.0)])
    assert not ok[100, 100] and not ok[103, 100]
    assert ok[108, 100] or scene.zones[108, 100] == ZONE_BUILDING


def test_asking_for_zero_trees_plants_nothing() -> None:
    scene = yard()
    assert hottest_sites(scene, np.ones(scene.grid.shape), 0, 7.0) == []
