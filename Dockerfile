# Phase 41 -- NONROOT selects the final stage below (default 1 = non-root).
# Phase 47 -- PYTHON_BASE_IMAGE lets the release workflow pin this by digest
# (python:3.12-slim@sha256:...) for a reproducible tagged build. Everyday
# `make build` leaves it at the floating tag below -- unchanged behavior.
# Both ARGs must be declared before the first FROM to be usable in one.
ARG NONROOT=1
ARG PYTHON_BASE_IMAGE=python:3.12-slim

FROM ${PYTHON_BASE_IMAGE} AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    VIRTUAL_ENV="/app/.venv"

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libpq-dev postgresql-client procps && \
    rm -rf /var/lib/apt/lists/*

# Fixed uid/gid so bind/named volumes chowned by `make fix-perms` stay stable
# across rebuilds.
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -m -d /home/appuser -s /usr/sbin/nologin appuser

# Pinned to the version live at :latest as of 2026-09-27 (Phase 40) -- checked via
# ghcr.io/v2/astral-sh/uv/manifests, org.opencontainers.image.version label. Bump
# deliberately, not by drifting back to :latest.
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /bin/uv

COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-dev

COPY backend_django /app/backend_django
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && mkdir -p /app/staticfiles /app/media

# ── Non-root variant (default) ────────────────────────────────────────────────
FROM base AS nonroot-1
RUN chown -R appuser:appuser /app /home/appuser
USER appuser

# ── Root variant (escape hatch: --build-arg NONROOT=0) ────────────────────────
FROM base AS nonroot-0

# ── Final: picks one of the two variants above ────────────────────────────────
FROM nonroot-${NONROOT} AS final

WORKDIR /app/backend_django
CMD ["/entrypoint.sh"]
