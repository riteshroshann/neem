# One image for the API and the worker. Same image runs locally (compose) and on AWS Lambda
# (container image with the Lambda Web Adapter for the API, the runtime client for the worker).
FROM python:3.12-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages ./packages
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim-bookworm
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/lambda-adapter
# rasterio wheels bundle GDAL but link the system expat; numba and scipy want libgomp
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
# compose runs as neem; Lambda brings its own user, and sam local needs a root build step
RUN useradd --create-home --uid 10001 neem
COPY --from=build /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 PYTHONUTF8=1 \
    NEEM_LAKE=/lake NEEM_HOST=0.0.0.0 NEEM_PORT=8000 \
    AWS_LWA_PORT=8000 AWS_LWA_READINESS_CHECK_PATH=/health
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1
CMD ["neem-api"]
