# syntax=docker/dockerfile:1

# =============================================================================
# GEOSIX frontend image (W41)
# =============================================================================
# Two stages:
#
#   build    Node toolchain compiles the Vite bundle.
#   runtime  nginx-unprivileged serves the static output. No Node, npm, or any
#            other build tooling is present in the shipped image.
#
# Deployment shape: the browser talks only to this nginx, on the frontend origin.
# api-client.ts uses a relative base (VITE_API_BASE_URL unset), so requests go to
# https://<frontend-host>/api/v1/... and this nginx proxies /api/ to the backend
# service. That is why the image is environment independent: it never needs to
# know the backend's hostname, and the browser never needs a Docker-internal
# address such as `backend:8000`, which is not resolvable outside the Compose
# network.
#
# Build from the repository root:
#     docker build -f frontend/Dockerfile frontend
# =============================================================================

ARG NODE_VERSION=22

# -----------------------------------------------------------------------------
# Build stage: compile the Vite bundle
# -----------------------------------------------------------------------------
FROM node:${NODE_VERSION}-alpine AS build

WORKDIR /app

# package.json + lockfile first: `npm ci` is only re-run when dependencies change.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .

# No ARG/ENV for the API base URL on purpose. `VITE_API_BASE_URL` is a *build*
# variable that gets inlined into the JavaScript bundle, so baking in a hostname
# would tie this image to one environment. Leaving it unset keeps
# `import.meta.env.VITE_API_BASE_URL` falsy in api-client.ts, which selects the
# relative "" base. See docs/deployment.md.
RUN npm run build

# -----------------------------------------------------------------------------
# Runtime stage: static files behind nginx, running as non-root
# -----------------------------------------------------------------------------
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

# nginx-unprivileged already runs as UID/GID 101 (`nginx`) and listens on 8080,
# so no privilege drop or capability juggling is needed here. See
# docs/deployment.md for the `docker inspect` command that proves it.
USER nginx:nginx

# Replace the stock single-page sample with our SPA + API-proxy configuration.
# Owned by nginx, matching the image's own /etc/nginx layout, so the base image's
# entrypoint script can still read it and its IPv6 adjustment does not print a
# "can not modify" warning on every start.
COPY --chown=nginx:nginx nginx/default.conf /etc/nginx/conf.d/default.conf

COPY --from=build --chown=nginx:nginx /app/dist /usr/share/nginx/html

EXPOSE 8080

# stdlib-free but dependency-free: busybox wget ships in the alpine base, so no
# extra package is installed just for the health probe.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["wget", "--quiet", "--tries=1", "--spider", "http://127.0.0.1:8080/healthz"]

# nginx-unprivileged's default entrypoint starts the master process; nothing to
# override, because the base image already drops privileges before exec'ing it.
CMD ["nginx", "-g", "daemon off;"]