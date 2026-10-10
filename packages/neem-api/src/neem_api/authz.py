"""Authorization with Cedar: identities in, allow or deny out, with the policy that decided.

Identity comes from the deployment's auth layer. Locally that is a bearer token looked up in a
server-side table (NEEM_DEV_TOKENS); a caller can never claim a role by sending one. Without a
token you are an anonymous visitor.
"""

from __future__ import annotations

import json
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any, Literal

import cedarpy

Action = Literal["ViewTwin", "PreviewDesign", "VerifyDesign", "ApproveDesign", "RunCityBatch"]
Role = Literal["visitor", "planner", "admin"]

_HERE = Path(__file__).parent / "policies"


@cache
def policies() -> str:
    return (_HERE / "neem.cedar").read_text()


@cache
def schema() -> dict[str, Any]:
    return json.loads((_HERE / "neem.cedarschema.json").read_text())


@dataclass(frozen=True, slots=True)
class Identity:
    user_id: str = "anonymous"
    role: Role = "visitor"
    schools: tuple[str, ...] = ()


ANONYMOUS = Identity()


@dataclass(frozen=True, slots=True)
class Decision:
    allowed: bool
    reasons: list[str] = field(default_factory=list)  # ids of the policies that decided
    errors: list[str] = field(default_factory=list)


def _uid(kind: str, id_: str) -> dict[str, str]:
    return {"type": f"Neem::{kind}", "id": id_}


def _entities(who: Identity, resource_kind: str, resource_id: str) -> list[dict[str, Any]]:
    schools = sorted({*who.schools, resource_id} if resource_kind == "School" else set(who.schools))
    out: list[dict[str, Any]] = [
        {"uid": _uid("Role", who.role), "attrs": {}, "parents": []},
        {
            "uid": _uid("User", who.user_id),
            "attrs": {"schools": [_uid("School", s) for s in who.schools]},
            "parents": [_uid("Role", who.role)],
        },
    ]
    out += [
        {"uid": _uid("School", s), "attrs": {"government": False}, "parents": []} for s in schools
    ]
    if resource_kind == "City":
        out.append({"uid": _uid("City", resource_id), "attrs": {}, "parents": []})
    return out


def check(
    who: Identity,
    action: Action,
    resource_id: str,
    context: dict[str, Any] | None = None,
    resource_kind: str = "School",
) -> Decision:
    request = {
        "principal": f'Neem::User::"{who.user_id}"',
        "action": f'Neem::Action::"{action}"',
        "resource": f'Neem::{resource_kind}::"{resource_id}"',
        "context": context or {},
    }
    result = cedarpy.is_authorized(
        request, policies(), _entities(who, resource_kind, resource_id), schema=schema()
    )
    diag = result.diagnostics
    return Decision(
        allowed=bool(result.allowed),
        reasons=list(getattr(diag, "reasons", []) or []),
        errors=[str(e) for e in (getattr(diag, "errors", []) or [])],
    )


class RecentJobs:
    """Per-identity count of verification jobs in the last hour (one API process)."""

    def __init__(self, window_s: float = 3600) -> None:
        self.window = window_s
        self._seen: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def count(self, user_id: str) -> int:
        with self._lock:
            q = self._seen[user_id]
            cutoff = time.monotonic() - self.window
            while q and q[0] < cutoff:
                q.popleft()
            return len(q)

    def record(self, user_id: str) -> None:
        with self._lock:
            self._seen[user_id].append(time.monotonic())


def identity_from_token(token: str | None, table: dict[str, dict[str, Any]]) -> Identity:
    if not token or token not in table:
        return ANONYMOUS
    t = table[token]
    return Identity(user_id=t["user"], role=t["role"], schools=tuple(t.get("schools", [])))
