from neem_core.child import PAR_PLAY, PAR_SEATED, Activity, simulate


def _day(recess_tr: float) -> list[Activity]:
    return [
        Activity("class", 30, ta=33, tr=33, rh=20, v=0.4, par=PAR_SEATED),
        Activity("recess", 30, ta=40, tr=recess_tr, rh=15, v=1.0, par=PAR_PLAY),
        Activity("class", 30, ta=34, tr=34, rh=20, v=0.4, par=PAR_SEATED),
    ]


def test_recess_in_the_sun_heats_a_child_more_than_recess_in_shade() -> None:
    sun = simulate(_day(recess_tr=68))
    shade = simulate(_day(recess_tr=45))
    assert sun.peak_core > shade.peak_core
    assert sun.total_water_ml > shade.total_water_ml
    assert len(sun.labels) == 90 and sun.labels[45] == "recess"


def test_outputs_are_physiological() -> None:
    day = simulate(_day(recess_tr=60))
    assert day.core.min() > 36.0 and day.core.max() < 41.0
    assert 0 < day.total_water_ml < 1500
    assert all(b >= a for a, b in zip(day.water_ml, day.water_ml[1:], strict=False))
