"""neem-data: ingest open data, build school scenes, rank the city."""

from __future__ import annotations

import typer

from neem_data import lake

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.callback()
def main() -> None:
    """Neem data pipeline."""


@app.command()
def ingest(what: str = typer.Argument("all", help="schools | buildings | all")) -> None:
    """Pull open data for Delhi into the local lake."""
    if what in ("schools", "all"):
        from neem_data.schools import fetch_schools

        fetch_schools(lake.path(*lake.SCHOOLS))
    if what in ("buildings", "all"):
        from neem_data.overture import extract_buildings

        extract_buildings(lake.path(*lake.BUILDINGS))


@app.command()
def weather(
    start: str = typer.Option("2026-04-01", help="first day to consider"),
    end: str = typer.Option("2026-05-10", help="last school day before summer vacation"),
) -> None:
    """Find the hottest school day (Mon to Sat) in a range and save its hourly forcing."""
    from datetime import date

    from neem_data.weather import fetch_day, fetch_range_daily_max

    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    daily = fetch_range_daily_max(d0, d1)
    school_days = {d: t for d, t in daily.items() if d.weekday() < 6}
    ranked = sorted(school_days.items(), key=lambda kv: kv[1], reverse=True)
    for d, t in ranked[:5]:
        print(f"  {d} {d:%a} max {t:.1f} C")
    hottest = ranked[0][0]
    fetch_day(hottest, lake.path("raw", "met", f"{hottest}.json"))
    lake.path("raw", "met", "showcase.txt").write_text(hottest.isoformat())


@app.command()
def scene(school_id: str, pixel: float = typer.Option(1.0, help="cell size, metres")) -> None:
    """Build and save the surface model for one school."""
    from neem_data.scene_builder import build_scene

    s, q = build_scene(school_id, pixel)
    s.save(lake.scene_dir(school_id))
    print(
        f"{s.name}: {s.grid.rows}x{s.grid.cols} at {pixel} m, {q.buildings} buildings "
        f"({q.height_coverage:.0%} with height), canopy over {q.canopy_cover:.0%} of open ground"
    )


@app.command()
def twin(school_id: str, day: str = typer.Option("", help="defaults to the showcase day")) -> None:
    """Run the full 1 m twin: SOLWEIG day, calibration, exposure and the child's day."""
    from neem_data.forcing import showcase_day
    from neem_data.twin import run_twin

    out = run_twin(school_id, day or showcase_day())
    print(f"twin -> {out}")


@app.command()
def rank(
    day: str = typer.Option("", help="defaults to the showcase day"),
    workers: int = typer.Option(4, help="local processes"),
    limit: int = typer.Option(0, help="stop after this many schools (0 for all)"),
    government: bool = typer.Option(False, help="government schools only"),
) -> None:
    """Rank every school with mapped grounds by heat exposure (resumable)."""
    from neem_data.batch import LocalPoolExecutor, rank_city
    from neem_data.forcing import showcase_day

    out = rank_city(day or showcase_day(), LocalPoolExecutor(workers), limit or None, government)
    print(f"rank -> {out}")


@app.command("verify-plan")
def verify_plan(
    school_id: str = typer.Argument("", help="one school, or every stored plan"),
    day: str = typer.Option("", help="defaults to the showcase day"),
) -> None:
    """Re-run stored planner designs through SOLWEIG and keep the fields for the site."""
    from neem_data import lake
    from neem_data.designs import verify_plan as run_plan
    from neem_data.forcing import showcase_day

    ids = [school_id] if school_id else sorted(p.stem for p in (lake.ROOT / "plans").glob("*.json"))
    for sid in ids:
        out = run_plan(sid, day or showcase_day())
        print(f"verify-plan {sid} -> {out}")


@app.command()
def publish(
    day: str = typer.Option("", help="defaults to the showcase day"),
    web: str = typer.Option("web", help="site root"),
) -> None:
    """Export ranking, twins, palette and thumbnails for the static site."""
    from pathlib import Path

    from neem_data.forcing import showcase_day
    from neem_data.publish import publish as run_publish

    run_publish(day or showcase_day(), Path(web))


if __name__ == "__main__":
    app()
