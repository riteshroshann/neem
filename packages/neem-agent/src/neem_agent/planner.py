"""The planner: a Strands agent that designs a cooler yard by calling the physics as tools.

The model decides how many trees, which species and whether a sail is worth it; the tools
decide where (the hottest open ground) and what it does (T0 preview, SOLWEIG verification).
The model never invents a number: every figure in its answer comes back from a tool.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import Any

from strands import Agent, tool
from strands.models.ollama import OllamaModel

from neem_agent.session import Session, load
from neem_core.interventions import SAIL_COST_PER_M2, SPECIES
from neem_data import lake
from neem_data.designs import baseline

SYSTEM = """You are Neem's schoolyard planner for a Delhi government school.
Goal: lower the feels-like heat (UTCI) children face outdoors on the morning shift (8 am
assembly, 11 am recess, 1 pm dismissal) as much as the budget allows.

Facts: shade is what cools a yard at midday. A neem gives about 38 m2 of shade for 3,500
rupees (about 92 rupees per m2). A shade sail costs 1,800 rupees per m2, about 20 times
more, but works from day one while trees take about five years. Prefer trees; add a small
sail only for an assembly spot if budget is left.

How to work:
1. Call school_brief once.
2. Call plant_trees with max_trees_in_budget from the brief, then preview.
3. If budget remains, you may add_shade_sail (keep it small) and preview again. If over
   budget, call plant_trees again with fewer trees.
4. Call verify exactly once on your final design.
5. Answer in four short plain sentences: what to plant, the cost, the yard heat at 1 pm today
   and with the plan, and the child's core temperature rise today and with the plan. Copy
   numbers exactly from the verify result. /no_think"""


def build(session: Session, budget: int) -> list[Any]:
    """Tools bound to one school's session."""

    @tool
    def school_brief() -> dict[str, Any]:
        """Today's heat at this school: grounds area, tree cover, feels-like temperature at the
        hours children are outside, and the budget."""
        t = session.twin
        ground = t.scene.mask(1)
        p = session.preview()
        return {
            "school": t.scene.name,
            "ground_m2": int(ground.sum() * t.scene.grid.pixel_size**2),
            "tree_cover": round(float((t.scene.cdsm[ground] > 0).mean()), 3),
            "utci_today": {h: v["today"] for h, v in p["hours"].items()},
            "budget_rs": budget,
            "tree_cost_rs": 3500,
            "max_trees_in_budget": budget // 3500,
            "sail_cost_rs_per_m2": 1800,
        }

    @tool
    def plant_trees(count: int, species: str = "neem") -> dict[str, Any]:
        """Replace the current trees with `count` new trees on the hottest open ground, at least
        one crown apart. species: neem, peepal, jamun or amaltas. Sails are kept."""
        # The budget is a hard limit enforced here; a model can ignore a flag but not this.
        sp = species if species in SPECIES else "neem"
        sails = session.cost - sum(t.cost for t in session.trees())
        affordable = max(0, (budget - sails) // SPECIES[sp][2])
        asked = max(0, min(int(count), 200))
        trees = session.place_trees(min(asked, affordable), sp)
        session.log.append(f"plant_trees({asked}, {sp}) -> {len(trees)}")
        return {
            "planted": len(trees),
            "asked": asked,
            "capped_by_budget": asked > affordable,
            "cost_rs": session.cost,
            "budget_left_rs": budget - session.cost,
        }

    @tool
    def add_shade_sail(width_m: float, depth_m: float) -> dict[str, Any]:
        """Add one horizontal shade sail (4 m high) over the hottest open ground without a tree.
        Width and depth in metres, each between 3 and 20."""
        w = min(max(float(width_m), 3.0), 20.0)
        d = min(max(float(depth_m), 3.0), 20.0)
        if session.cost + round(w * d * SAIL_COST_PER_M2) > budget:
            session.log.append(f"add_shade_sail({w}, {d}) -> refused, over budget")
            return {
                "added": False,
                "reason": "over budget",
                "budget_left_rs": budget - session.cost,
            }
        sail = session.add_sail(w, d)
        session.log.append(f"add_shade_sail({w}, {d}) -> {'ok' if sail else 'no room'}")
        return {
            "added": sail is not None,
            "cost_rs": session.cost,
            "budget_left_rs": budget - session.cost,
        }

    @tool
    def preview() -> dict[str, Any]:
        """Instant estimate of the current design: grounds feels-like temperature today and with
        the plan at 8:00, 11:00 and 13:00, and the cost."""
        p = session.preview()
        session.log.append(f"preview -> {json.dumps(p['hours'])}")
        return p

    @tool
    def verify() -> dict[str, Any]:
        """Run the full SOLWEIG physics on the current design (about ten seconds) and the
        child twin. Call once, at the end."""
        r = session.verify()
        session.log.append(f"verify -> {r['seconds']} s")
        today = baseline(session.twin.school_id, session.twin.day)
        k = session.twin.hour_index("13:00")
        idx = r["hours"].index("13:00")
        return {
            "yard_utci_1pm_today": round(float(session.twin.base_ground_utci(k)), 2),
            "yard_utci_1pm_with_plan": r["utci_ground_by_hour"][idx],
            "child_core_rise_today": today["child"]["peak_rise"],
            "child_core_rise_with_plan": r["child"]["peak_rise"],
            "child_water_ml_today": today["child"]["total_water_ml"],
            "child_water_ml_with_plan": r["child"]["total_water_ml"],
            "cost_rs": r["cost_rs"],
            "trees": r["trees"],
            "sails": r["sails"],
            "seconds": r["seconds"],
        }

    return [school_brief, plant_trees, add_shade_sail, preview, verify]


def plan(school_id: str, day: str, budget: int, model_id: str = "qwen3:4b") -> dict[str, Any]:
    started = time.perf_counter()
    session = Session(load(school_id, day))
    before = session.preview()
    agent = Agent(
        model=OllamaModel(host="http://127.0.0.1:11434", model_id=model_id, temperature=0.2),
        tools=build(session, budget),
        system_prompt=SYSTEM,
        callback_handler=None,
    )
    # qwen3 reads /no_think from the user turn; without it, it sometimes skips the tools and
    # answers from imagination. One firm retry if that happens.
    answer = agent(f"Design a plan for this school. Budget: {budget} rupees. /no_think")
    if not session.log:
        answer = agent(
            "You did not use the tools. Start with school_brief, then follow the steps. /no_think"
        )
    if session.verified is None and session.design:
        session.verify()  # the model skipped the final step; physics still gets the last word
    out = {
        "school_id": school_id,
        "day": day,
        "budget_rs": budget,
        "model": model_id,
        "answer": str(answer).strip(),
        "design": session.design_json(),
        "baseline": before,
        "preview": session.preview(),
        "verified": session.verified,
        "steps": session.log,
        "seconds": round(time.perf_counter() - started, 1),
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    lake.path("plans", f"{school_id}.json").write_text(json.dumps(out, indent=2))
    return out
