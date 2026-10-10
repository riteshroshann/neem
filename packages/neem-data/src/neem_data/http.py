"""HTTP with retries; public endpoints here flake under load."""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from neem_data.sources import USER_AGENT


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, max=30), reraise=True)
def get_json(url: str, *, params: dict[str, Any] | None = None, timeout: float = 120) -> Any:
    r = httpx.get(url, params=params, timeout=timeout, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    return r.json()


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, max=30), reraise=True)
def post_json(url: str, *, data: dict[str, str], timeout: float = 180) -> Any:
    r = httpx.post(
        url, data=data, timeout=timeout, headers={"User-Agent": USER_AGENT, "Accept": "*/*"}
    )
    r.raise_for_status()
    return r.json()
