# syntax=docker/dockerfile:1

# =============================================================================
# GEOSIX backend image (W41)
# =============================================================================
# Two stages:
#
#   builder  installs the application and its production dependencies into a
#            self-contained virtualenv at /opt/venv. Only that virtualenv and
#            the Alembic script directory cross into the runtime stage, so no
#            compiler, no build backend, and no build cache end up in the shipped
#            image.
#   runtime  copies /opt/venv plus the migration environment, drops to a
#            dedicated non-root user, and serves the ASGI app with Uvicorn.
#
# No secret is baked in: every setting is read from the process environment when
# the container starts. See backend/.env.example and docs/deployment.md.
#
# Build from the repository root so the build context stays small:
#     docker build -f backend/Dockerfile backend
# Compose does this for you via `build: {context: backend, dockerfile: Dockerfile}`.
# =============================================================================

ARG PYTHON_VERSION=3.11

# -----------------------------------------------------------------------------
# Builder: resolve and install production dependencies
# -----------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

# Dependency metadata first: the layer is only invalidated when the declared
# dependency set changes, not on every source edit.
COPY pyproject.toml ./
COPY app ./app

# `pip install .` builds the project with the checked-in setuptools configuration:
# [tool.setuptools.packages.find] include = ["app*"] keeps flat-layout
# auto-discovery from failing on the `alembic` directory. Development extras are
# deliberately NOT installed -- the runtime image never needs pytest or ruff.
#
# pip and the build backend are removed afterwards so the runtime image carries
# no package installer at all. The final import check proves the wheel really
# contains a usable `app` package before the stage is published.
RUN python -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir . \
    && /opt/venv/bin/python -c "import app.core.healthcheck, app.main" \
    && /opt/venv/bin/python -m pip uninstall --yes pip setuptools wheel

# -----------------------------------------------------------------------------
# Runtime: minimal image, no build tooling, non-root
# -----------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

#: Dedicated non-root account. A fixed numeric UID/GID keeps bind-mounted
#: volumes predictable across hosts and rebuilds.
ARG APP_UID=10001
ARG APP_GID=10001

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH"

RUN set -eux; \
    groupadd --system --gid "${APP_GID}" geosix; \
    useradd --system --uid "${APP_UID}" --gid "${APP_GID}" \
            --home-dir /home/geosix --create-home \
            --shell /usr/sbin/nologin geosix

WORKDIR /app

COPY --from=builder --chown=root:root /opt/venv /opt/venv

# Alembic is a script directory, not an importable package, so it is not part of
# the installed wheel. Copying it here is what makes `alembic upgrade head`
# runnable *inside* the image without a bind mount.
COPY --chown=root:root alembic.ini ./alembic.ini
COPY --chown=root:root alembic ./alembic

USER geosix

# Declared so `docker inspect` and image metadata report the listening port.
EXPOSE 8000

# stdlib-only probe: this image installs no curl or wget, and adding one purely
# to serve HEALTHCHECK would grow the attack surface for no benefit.
# start-period covers a cold start plus the lifespan database connectivity check
# in app.main.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-m", "app.core.healthcheck", "--url", "http://127.0.0.1:8000/api/v1/health", "--timeout", "4"]

# Production startup: no --reload, explicit 0.0.0.0 bind so the published port
# is actually reachable, and a small fixed worker count. Override `command:` in
# your own compose override to tune workers or add --proxy-headers behind an
# external TLS terminator.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--log-level", "info"]