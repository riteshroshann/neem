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


if __name__ == "__main__":
    app()
