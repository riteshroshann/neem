"""Policy tests: the rules a judge, a principal or an attacker would try first."""

from __future__ import annotations

import cedarpy
import pytest

from neem_api.authz import (
    ANONYMOUS,
    Identity,
    RecentJobs,
    check,
    identity_from_token,
    policies,
    schema,
)

KV = "osm-w1321574340"
OTHER = "osm-w78786253"
PRINCIPAL = Identity("principal@kv25", "planner", (KV,))
ADMIN = Identity("ops@neem", "admin")


def test_policies_validate_against_the_schema() -> None:
    result = cedarpy.validate_policies(policies(), schema())
    assert result.validation_passed, result.errors


@pytest.mark.parametrize("action", ["ViewTwin", "PreviewDesign"])
def test_anyone_can_explore(action: str) -> None:
    assert check(ANONYMOUS, action, KV).allowed  # type: ignore[arg-type]


def test_anyone_can_verify_a_reasonable_design() -> None:
    assert check(ANONYMOUS, "VerifyDesign", KV, {"trees": 12, "sails": 1, "recent_jobs": 0}).allowed


@pytest.mark.parametrize(
    "ctx",
    [
        {"trees": 201, "sails": 0, "recent_jobs": 0},
        {"trees": 5, "sails": 41, "recent_jobs": 0},
        {"trees": 5, "sails": 0, "recent_jobs": 20},
    ],
)
def test_verification_has_a_budget(ctx: dict[str, int]) -> None:
    assert not check(ANONYMOUS, "VerifyDesign", KV, ctx).allowed


def test_a_planner_approves_only_their_own_verified_school() -> None:
    assert check(PRINCIPAL, "ApproveDesign", KV, {"verified": True}).allowed
    assert not check(PRINCIPAL, "ApproveDesign", OTHER, {"verified": True}).allowed
    assert not check(PRINCIPAL, "ApproveDesign", KV, {"verified": False}).allowed


def test_visitors_cannot_approve() -> None:
    assert not check(ANONYMOUS, "ApproveDesign", KV, {"verified": True}).allowed


def test_even_an_admin_cannot_approve_unverified_plans() -> None:
    assert check(ADMIN, "ApproveDesign", OTHER, {"verified": True}).allowed
    assert not check(ADMIN, "ApproveDesign", OTHER, {"verified": False}).allowed


def test_only_admins_rerun_the_city_batch() -> None:
    assert check(ADMIN, "RunCityBatch", "delhi", resource_kind="City").allowed
    assert not check(PRINCIPAL, "RunCityBatch", "delhi", resource_kind="City").allowed


def test_roles_come_from_the_server_table_not_the_caller() -> None:
    table = {"t-kv25": {"user": "principal@kv25", "role": "planner", "schools": [KV]}}
    assert identity_from_token("t-kv25", table) == PRINCIPAL
    assert identity_from_token("made-up", table) == ANONYMOUS
    assert identity_from_token(None, table) == ANONYMOUS


def test_recent_jobs_window_counts_per_user() -> None:
    jobs = RecentJobs(window_s=60)
    for _ in range(3):
        jobs.record("a")
    jobs.record("b")
    assert jobs.count("a") == 3 and jobs.count("b") == 1 and jobs.count("c") == 0
