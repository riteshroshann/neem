"""Runtime configuration, from environment variables prefixed NEEM_."""

from __future__ import annotations

from functools import cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NEEM_", env_file=".env", extra="ignore")

    day: str = "2026-04-27"
    jobs: Literal["local", "aws"] = "local"  # local: files + threads; aws: DynamoDB + SQS
    aws_endpoint_url: str | None = None  # moto locally, unset on AWS
    aws_region: str = "ap-south-1"
    jobs_table: str = "neem-jobs"
    jobs_queue_url: str | None = None
    cors_origins: list[str] = ["http://localhost:4321", "http://127.0.0.1:4321"]
    host: str = "127.0.0.1"
    port: int = 8000


@cache
def settings() -> Settings:
    return Settings()
