set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]
set dotenv-load := true

default: check

# Format check, lint, types and the fast test suite (must pass before any commit)
check:
    uv run ruff format --check .
    uv run ruff check .
    uv run basedpyright
    uv run pytest -q -m "not slow and not integration and not network"

# Everything, including the full SOLWEIG engine tests
test-all:
    uv run pytest -q -m "not integration and not network"

# Fix formatting and autofixable lint
fmt:
    uv run ruff format .
    uv run ruff check --fix .

test *args:
    uv run pytest -q {{args}}

# Pull open data for Delhi into the local lake
ingest *args:
    uv run neem-data ingest {{args}}

# Build the 1 m twin for one school
scene school_id:
    uv run neem-data scene {{school_id}}

# City-scale ranking of every school
rank *args:
    uv run neem-data rank {{args}}

# Local stack: emulated AWS, API, worker
up:
    docker compose -f infra/compose.yaml up -d --build

down:
    docker compose -f infra/compose.yaml down

# API with reload, against the local stack
api:
    uv run neem-api
