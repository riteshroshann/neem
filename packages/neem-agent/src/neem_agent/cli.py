"""neem-agent: let the planner design a school's yard."""

from __future__ import annotations

import typer

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.callback()
def main() -> None:
    """Neem planner agent (Strands Agents on a local model)."""


@app.command()
def plan(
    school_id: str,
    budget: int = typer.Option(300_000, help="rupees"),
    model: str = typer.Option("qwen3:4b", help="Ollama model id"),
    day: str = typer.Option("", help="defaults to the showcase day"),
) -> None:
    """Design, preview and verify a cooler yard for one school."""
    from neem_agent.planner import plan as run_plan
    from neem_data.forcing import showcase_day

    out = run_plan(school_id, day or showcase_day(), budget, model)
    print(out["answer"])
    print()
    for step in out["steps"]:
        print("  ", step)
    v = out["verified"] or {}
    print(f"\nverified in {v.get('seconds')} s; total {out['seconds']} s")


if __name__ == "__main__":
    app()
