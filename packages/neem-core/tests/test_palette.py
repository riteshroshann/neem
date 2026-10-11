import pytest

from neem_core.palette import NO_HEAT_STRESS, band, to_json


@pytest.mark.parametrize(
    ("utci", "name"),
    [
        (20.0, NO_HEAT_STRESS),
        (26.0, "Moderate"),
        (31.9, "Moderate"),
        (32.0, "Strong"),
        (40.0, "Very strong"),
        (45.9, "Very strong"),
        (47.3, "Extreme"),
    ],
)
def test_bands_follow_the_utci_assessment_scale(utci: float, name: str) -> None:
    assert band(utci) == name


def test_json_bands_carry_names_bounds_and_colours() -> None:
    bands = to_json()["bands"]
    assert isinstance(bands, list)
    assert [b["name"] for b in bands] == [
        NO_HEAT_STRESS,
        "Moderate",
        "Strong",
        "Very strong",
        "Extreme",
    ]
    assert [b["min"] for b in bands] == [None, 26.0, 32.0, 38.0, 46.0]
    assert all(b["hex"].startswith("#") and len(b["hex"]) == 7 for b in bands)
