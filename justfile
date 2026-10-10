set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]
set dotenv-load := true

# solweig logs non-ascii marks; the windows console default codec chokes on them
export PYTHONUTF8 := "1"

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

# Web: lint, types and the cross-language differential tests
check-web:
    cd web; bun x biome check .; bun x astro check; bun test

# Export ranking, thumbnails and twin files for the site
publish:
    uv run neem-data publish

web:
    cd web; bun run dev

# Planner agent (Strands Agents on a local Ollama model)
plan school_id budget="300000":
    uv run neem-agent plan {{school_id}} --budget {{budget}}

# LocalStack (last open-source release) for sam local and ad-hoc runs
localstack:
    docker run -d --rm --name neem-localstack -p 4566:4566 -e SERVICES=s3,sqs,dynamodb,stepfunctions,lambda,iam,sts,logs localstack/localstack:4.14

# Create table, queue and lake bucket on LocalStack, seed the lake, queue a demo job
seed:
    $env:NEEM_AWS_ENDPOINT_URL='http://localhost:4566'; $env:NEEM_AWS_REGION='us-east-1'; $env:AWS_ACCESS_KEY_ID='test'; $env:AWS_SECRET_ACCESS_KEY='test'; $env:NEEM_LAKE_BUCKET='neem-lake'; $env:NEEM_LAKE_SRC='data/lake'; uv run python -m neem_worker.bootstrap --demo-job

sam-validate:
    sam validate -t infra/template.yaml --lint --region us-east-1

sam-build:
    sam build -t infra/template.yaml

# Run the worker Lambda locally on a queued design, against LocalStack
sam-worker:
    sam local invoke WorkerFunction -t .aws-sam/build/template.yaml -e infra/events/sqs-job.json --env-vars infra/sam-env.json --docker-network neem

# Run one city-ranking item Lambda locally
sam-rank:
    sam local invoke RankFunction -t .aws-sam/build/template.yaml -e infra/events/rank-one.json --env-vars infra/sam-env.json --docker-network neem

# The API through API Gateway emulation
sam-api:
    sam local start-api -t .aws-sam/build/template.yaml --env-vars infra/sam-env.json --docker-network neem --port 3000
