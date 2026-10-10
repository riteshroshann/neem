import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from neem_core.shadow import CANOPY_TRANSMISSIVITY, sunlit_fraction

FLAT = 100.0


def _flat(n: int = 60) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    dem = np.full((n, n), FLAT, dtype=np.float32)
    return dem.copy(), dem, np.zeros((n, n), dtype=np.float32)


@pytest.mark.parametrize("altitude", [20.0, 35.0, 60.0])
def test_wall_casts_shadow_of_length_h_over_tan_alt(altitude: float) -> None:
    dsm, dem, cdsm = _flat()
    height = 10.0
    dsm[:, 40:45] = FLAT + height  # north-south wall
    lit = sunlit_fraction(dsm, dem, cdsm, 1.0, altitude, azimuth=90.0)  # sun due east
    shaded_west = int((lit[30, :40] < 0.5).sum())
    expected = height / math.tan(math.radians(altitude))
    assert abs(shaded_west - expected) <= 1.5
    assert lit[30, 45:].min() == 1.0  # nothing shaded on the sunny side


def test_flat_ground_is_fully_lit() -> None:
    dsm, dem, cdsm = _flat()
    assert sunlit_fraction(dsm, dem, cdsm, 1.0, 30.0, 135.0).min() == 1.0


def test_night_is_dark() -> None:
    dsm, dem, cdsm = _flat()
    assert sunlit_fraction(dsm, dem, cdsm, 1.0, -5.0, 135.0).max() == 0.0


def test_crown_lets_a_little_light_through_and_trunk_zone_lets_low_sun_under() -> None:
    dsm, dem, cdsm = _flat()
    cdsm[28:33, 28:33] = 8.0
    high = sunlit_fraction(dsm, dem, cdsm, 1.0, 80.0, 180.0)
    assert high[30, 30] == pytest.approx(CANOPY_TRANSMISSIVITY)
    # A low sun slips under the crown (trunk zone is the bottom quarter) for cells far enough
    # away that the ray is still below 2 m when it reaches the tree.
    low = sunlit_fraction(dsm, dem, cdsm, 1.0, 5.0, 90.0)
    assert low[30, 27] == 1.0


boxes = st.lists(
    st.tuples(
        st.integers(0, 29),
        st.integers(0, 29),
        st.integers(1, 8),
        st.integers(1, 8),
        st.floats(1.0, 20.0),
    ),
    max_size=5,
)


def _with_boxes(spec: list[tuple[int, int, int, int, float]]) -> np.ndarray:
    dsm = np.full((30, 30), FLAT, dtype=np.float32)
    for r, c, h, w, z in spec:
        dsm[r : r + h, c : c + w] = np.maximum(dsm[r : r + h, c : c + w], FLAT + z)
    return dsm


@settings(max_examples=60, deadline=None)
@given(boxes, boxes, st.floats(5.0, 85.0), st.floats(0.0, 359.9))
def test_adding_buildings_never_lights_unchanged_cells(base, extra, alt, az) -> None:
    dsm = _with_boxes(base)
    taller = np.maximum(dsm, _with_boxes(extra))
    dem = np.full_like(dsm, FLAT)
    cdsm = np.zeros_like(dsm)
    before = sunlit_fraction(dsm, dem, cdsm, 1.0, alt, az)
    after = sunlit_fraction(taller, dem, cdsm, 1.0, alt, az)
    unchanged = taller == dsm
    assert np.all(after[unchanged] <= before[unchanged] + 1e-6)


@settings(max_examples=60, deadline=None)
@given(boxes, st.floats(5.0, 85.0), st.floats(0.0, 359.9))
def test_adding_canopy_never_lights_any_cell(spec, alt, az) -> None:
    dsm = np.full((30, 30), FLAT, dtype=np.float32)
    dem = dsm.copy()
    cdsm = np.zeros_like(dsm)
    grown = _with_boxes(spec) - FLAT
    before = sunlit_fraction(dsm, dem, cdsm, 1.0, alt, az)
    after = sunlit_fraction(dsm, dem, grown, 1.0, alt, az)
    assert np.all(after <= before + 1e-6)
