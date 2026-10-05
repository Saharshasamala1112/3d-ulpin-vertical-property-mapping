#!/usr/bin/env bash
# =============================================================================
# GEOSIX deployment smoke test (W41)
# =============================================================================
# Brings up the real Compose stack and proves the deployment actually works:
#
#   1. every service reports healthy (Docker + Compose healthchecks)
#   2. the backend answers 200 on its public health route
#   3. the frontend nginx serves the built SPA
#   4. the browser path works: browser -> nginx -> backend /api/...
#   5. SPA history fallback works for a React Router deep link
#   6. the containers run as non-root
#
# It exits non-zero on the first failure and prints diagnostics (container logs)
# for whatever is unhealthy, so a failure is actionable without a second command.
#
# Usage
#   scripts/smoke-test.sh                  # build, test, leave the stack running
#   scripts/smoke-test.sh --no-build       # skip `docker compose build`
#   scripts/smoke-test.sh --teardown       # stop containers when finished
#   scripts/smoke-test.sh --timeout 300    # longer health wait, in seconds
#
# Environment
#   FRONTEND_PORT  host port for the frontend (default 8080)
#   BACKEND_PORT   host port for the backend  (default 8000)
#   SMOKE_NO_MIGRATE=1  skip `alembic upgrade head` (e.g. re-testing a live DB)
#
# Cleanup contract -- read this before running with `--teardown`
#   Containers are removed with `docker compose down`, which does NOT touch the
#   `geosix_postgres_data` named volume. `docker compose down -v` is never run
#   here and is never safe to run against a database you care about.
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

BUILD=1
TEARDOWN=0
TIMEOUT=180
FRONTEND_PORT="${FRONTEND_PORT:-8080}"
BACKEND_PORT="${BACKEND_PORT:-8000}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-build) BUILD=0; shift ;;
        --teardown) TEARDOWN=1; shift ;;
        --timeout)  TIMEOUT="${2:?--timeout needs a value in seconds}"; shift 2 ;;
        -h|--help)  sed -n '2,35p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
done

# -----------------------------------------------------------------------------
# Output helpers
# -----------------------------------------------------------------------------
if [[ -t 1 ]]; then
    GREEN=$'\033[32m'; RED=$'\033[31m'; YELLOW=$'\033[33m'; BOLD=$'\033[1m'; RESET=$'\033[0m'
else
    GREEN=""; RED=""; YELLOW=""; BOLD=""; RESET=""
fi

FAILURES=0
STEP=0

step() {
    STEP=$((STEP + 1))
    printf '\n%s==> [%d] %s%s\n' "$BOLD" "$STEP" "$1" "$RESET"
}

pass() { printf '    %sPASS%s  %s\n' "$GREEN" "$RESET" "$1"; }

fail() {
    printf '    %sFAIL%s  %s\n' "$RED" "$RESET" "$1"
    FAILURES=$((FAILURES + 1))
}

warn() { printf '    %sWARN%s  %s\n' "$YELLOW" "$RESET" "$1"; }

info() { printf '          %s\n' "$1"; }

# Dumps container logs for services that are not healthy or that just failed a
# check. This is the difference between a useful failure and a mystery.
diagnose() {
    printf '\n%s--- diagnostics: docker compose ps ---%s\n' "$BOLD" "$RESET"
    docker compose ps --all 2>&1 | sed 's/^/    /' || true
    for service in "$@"; do
        printf '\n%s--- diagnostics: last 40 log lines from %s ---%s\n' "$BOLD" "$service" "$RESET"
        docker compose logs --no-color --tail 40 "$service" 2>&1 | sed 's/^/    /' || true
    done
}

# -----------------------------------------------------------------------------
# Prerequisite check
# -----------------------------------------------------------------------------
step "Checking prerequisites"
command -v docker >/dev/null 2>&1 || { fail "docker is not installed or not on PATH"; exit 1; }
docker compose version >/dev/null 2>&1 || { fail "'docker compose' (v2 plugin) is not available"; exit 1; }
if ! docker info >/dev/null 2>&1; then
    fail "the Docker daemon is not reachable (try: sudo systemctl start docker)"
    exit 1
fi
docker compose version | sed 's/^/    /'
info "frontend origin: http://localhost:${FRONTEND_PORT}"
info "backend  (loopback only): http://127.0.0.1:${BACKEND_PORT}"
pass "Docker and Compose are available"

# -----------------------------------------------------------------------------
# Build
# -----------------------------------------------------------------------------
if [[ "$BUILD" -eq 1 ]]; then
    step "Building images (docker compose build)"
    if docker compose build; then
        pass "backend and frontend images built"
    else
        fail "image build failed"
        diagnose
        exit 1
    fi
else
    step "Skipping build (--no-build)"
fi

# -----------------------------------------------------------------------------
# Start the stack
# -----------------------------------------------------------------------------
step "Starting the Compose stack (docker compose up -d)"
docker compose up -d
pass "containers created/started"

# -----------------------------------------------------------------------------
# Apply migrations explicitly.
#
# Deliberately NOT part of the container entrypoint: an entrypoint that migrates
# on every boot would run concurrently with other replicas and would make a
# rollback impossible to reason about. See docs/deployment.md.
# -----------------------------------------------------------------------------
if [[ "${SMOKE_NO_MIGRATE:-0}" == "1" ]]; then
    step "Skipping migrations (SMOKE_NO_MIGRATE=1)"
else
    step "Running database migrations (alembic upgrade head)"
    if docker compose exec -T backend alembic upgrade head; then
        pass "schema is at the Alembic head revision"
    else
        fail "alembic upgrade head failed"
        diagnose backend
        [[ "$TEARDOWN" -eq 1 ]] && docker compose down
        exit 1
    fi
fi

# -----------------------------------------------------------------------------
# Wait for health
# -----------------------------------------------------------------------------
step "Waiting for all services to become healthy (timeout ${TIMEOUT}s)"
wait_for_healthy() {
    local deadline=$((SECONDS + TIMEOUT))
    while (( SECONDS < deadline )); do
        local not_healthy
        not_healthy="$(docker compose ps --format '{{.Service}} {{.Health}}' 2>/dev/null \
            | awk '$2 != "healthy" {print $1}' | tr '\n' ' ')"
        if [[ -z "${not_healthy// /}" ]]; then
            return 0
        fi
        sleep 3
    done
    info "still not healthy after ${TIMEOUT}s: ${not_healthy:-unknown}"
    return 1
}

if wait_for_healthy; then
    docker compose ps
    pass "postgres, backend and frontend are all healthy"
else
    fail "services did not become healthy within ${TIMEOUT}s"
    diagnose postgres backend frontend
    [[ "$TEARDOWN" -eq 1 ]] && docker compose down
    exit 1
fi

# -----------------------------------------------------------------------------
# HTTP helpers. curl is a hard requirement for these checks; report it clearly
# rather than failing later with a confusing "connection refused".
# -----------------------------------------------------------------------------
step "Checking the HTTP client"
if command -v curl >/dev/null 2>&1; then
    pass "curl $(curl --version | head -1 | awk '{print $2}')"
else
    fail "curl is required by this smoke test"
    diagnose
    [[ "$TEARDOWN" -eq 1 ]] && docker compose down
    exit 1
fi

# -----------------------------------------------------------------------------
# HTTP assertions
# -----------------------------------------------------------------------------
# assert_status <description> <expected-status> <url> [extra curl args...]
assert_status() {
    local description="$1" expected="$2" url="$3"
    shift 3
    local body_file status
    body_file="$(mktemp)"
    status="$(curl --silent --show-error --max-time 15 --output "$body_file" --write-out '%{http_code}' "$@" "$url" 2>/dev/null || echo "000")"
    if [[ "$status" == "$expected" ]]; then
        pass "$description -> HTTP $status"
        [[ -n "${SMOKE_VERBOSE:-}" ]] && info "$(head -c 400 "$body_file")"
        rm -f "$body_file"
        return 0
    fi
    fail "$description -> expected HTTP $expected, got $status"
    info "url:   $url"
    info "body:  $(head -c 400 "$body_file")"
    rm -f "$body_file"
    return 1
}

# assert_body_contains <description> <needle> <url>
assert_body_contains() {
    local description="$1" needle="$2" url="$3"
    local body status
    body="$(curl --silent --show-error --max-time 15 --write-out $'\n%{http_code}' "$url" 2>/dev/null)" || {
        fail "$description -> request failed"
        return 1
    }
    status="${body##*$'\n'}"
    body="${body%$'\n'*}"
    if [[ "$status" != "200" ]]; then
        fail "$description -> expected HTTP 200, got $status"
        return 1
    fi
    if [[ "$body" == *"$needle"* ]]; then
        pass "$description (body contains '$needle')"
        return 0
    fi
    fail "$description -> body did not contain '$needle'"
    info "body: $(printf '%s' "$body" | head -c 400)"
    return 1
}

step "Verifying backend health (direct, loopback port)"
assert_status "backend /api/v1/health (published port)" 200 "http://127.0.0.1:${BACKEND_PORT}/api/v1/health"
assert_status "backend /api/health (published port)"   200 "http://127.0.0.1:${BACKEND_PORT}/api/health"
assert_body_contains "backend reports status ok" "ok" "http://127.0.0.1:${BACKEND_PORT}/api/v1/health"
assert_status "backend /api/v1 root metadata"          200 "http://127.0.0.1:${BACKEND_PORT}/api/v1"

# The health endpoint must NOT hardcode a CORS origin. With a disallowed Origin
# the app's CORSMiddleware is the only thing allowed to add an allow-origin
# header, so its absence is the expected, correct outcome.
step "Verifying health endpoint CORS is driven by configuration, not hardcoded"
CORS_HEADERS="$(curl --silent --show-error --max-time 15 --dump-header - --output /dev/null \
    --header 'Origin: http://evil.example.com' \
    "http://127.0.0.1:${BACKEND_PORT}/api/v1/health" 2>/dev/null || true)"
if grep -qi 'access-control-allow-origin' <<<"$CORS_HEADERS"; then
    fail "a disallowed Origin received Access-Control-Allow-Origin (hardcoded CORS in health.py?)"
    info "$(grep -i 'access-control-allow-origin' <<<"$CORS_HEADERS" | head -2)"
else
    pass "no Access-Control-Allow-Origin echoed for a disallowed Origin"
fi
if grep -q 'http://localhost:5173' <<<"$CORS_HEADERS"; then
    fail "health response still advertises the development origin http://localhost:5173"
else
    pass "health response does not advertise http://localhost:5173"
fi

step "Verifying frontend static serving"
assert_status "frontend / returns 200"        200 "http://localhost:${FRONTEND_PORT}/"
assert_body_contains "frontend serves the Vite-built index.html" '<div id="root">' \
    "http://localhost:${FRONTEND_PORT}/"

# React Router v7 history fallback: a hard navigation to a deep link must be
# answered with index.html, not a 404.
step "Verifying React Router SPA history fallback"
assert_status "frontend /login deep link"      200 "http://localhost:${FRONTEND_PORT}/login"
assert_body_contains "frontend /login returns the SPA shell" '<div id="root">' \
    "http://localhost:${FRONTEND_PORT}/login"
assert_status "frontend /app/deep/link route"  200 "http://localhost:${FRONTEND_PORT}/app/buildings/some-parcel-id"

step "Verifying the browser path: frontend nginx -> backend /api/ (this is the critical one)"
assert_status "proxied /api/v1/health"        200 "http://localhost:${FRONTEND_PORT}/api/v1/health"
assert_status "proxied /api/health"            200 "http://localhost:${FRONTEND_PORT}/api/health"
assert_body_contains "proxied health reports ok" "ok" \
    "http://localhost:${FRONTEND_PORT}/api/health"
assert_status "proxied /api/v1 root metadata" 200 "http://localhost:${FRONTEND_PORT}/api/v1"

# An authenticated route must reject an anonymous caller rather than 502. A 401
# proves the request reached the backend's auth layer through nginx.
assert_status "proxied protected route rejects anonymous access" 401 \
    "http://localhost:${FRONTEND_PORT}/api/v1/auth/me"

step "Verifying nginx does not expose unintended filesystem paths"
assert_status "dotfile access is denied" 403 "http://localhost:${FRONTEND_PORT}/.env"
assert_status "nginx health endpoint"    200 "http://localhost:${FRONTEND_PORT}/healthz"

# The frontend must never be able to serve a file from outside the document root.
# Raw `..` segments are rejected by nginx outright (400); a `..` segment placed after
# the proxy prefix is normalised into a path that legitimately falls through to the
# SPA shell, so the assertion there is that no backend file content leaks rather
# than that the status is an error.
for leak in "/../alembic.ini" "/../../etc/passwd"; do
    status="$(curl --silent --output /dev/null --write-out '%{http_code}' --path-as-is \
        "http://localhost:${FRONTEND_PORT}${leak}" 2>/dev/null || echo 000)"
    if [[ "$status" == "200" ]]; then
        fail "nginx served a path outside the document root ($leak -> HTTP 200)"
    else
        pass "raw path traversal rejected ($leak -> HTTP ${status})"
    fi
done

TRAVERSAL_BODY="$(curl --silent --path-as-is \
    "http://localhost:${FRONTEND_PORT}/api/../alembic.ini" 2>/dev/null || true)"
if [[ "$TRAVERSAL_BODY" == *"sqlalchemy.url"* || "$TRAVERSAL_BODY" == *"script_location"* ]]; then
    fail "backend configuration leaked through /api/../ traversal"
else
    pass "traversal through /api/ does not expose backend configuration"
fi

# -----------------------------------------------------------------------------
# Container security assertions
# -----------------------------------------------------------------------------
step "Verifying containers run as non-root"
assert_non_root() {
    local container="$1" expected_user="$2" user
    user="$(docker inspect --format '{{.Config.User}}' "$container" 2>/dev/null || echo "unknown")"
    if [[ -z "$user" || "$user" == "root" || "$user" == "0" || "$user" == "0:0" ]]; then
        fail "$container runs as root (Config.User='${user}')"
        return 1
    fi
    if [[ "$user" != *"$expected_user"* ]]; then
        fail "$container Config.User='${user}' does not look like '${expected_user}'"
        return 1
    fi
    pass "$container runs as non-root (Config.User='${user}')"
}

assert_non_root "geosix-backend"  "geosix"
assert_non_root "geosix-frontend" "nginx"

step "Verifying the backend image carries no build tooling"
if docker compose exec -T backend sh -c 'command -v gcc cc make || exit 1' >/dev/null 2>&1; then
    fail "a compiler is present in the backend runtime image"
else
    pass "no compiler (gcc/cc/make) in the backend runtime image"
fi
if docker compose exec -T backend sh -c 'command -v pytest ruff || exit 1' >/dev/null 2>&1; then
    fail "development tooling (pytest/ruff) is present in the backend runtime image"
else
    pass "no development tooling (pytest/ruff) in the backend runtime image"
fi

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
printf '\n%s================ smoke test summary ================%s\n' "$BOLD" "$RESET"
docker compose ps

if [[ "$FAILURES" -gt 0 ]]; then
    printf '\n%sFAILED%s  %d check(s) did not pass.\n' "$RED" "$RESET" "$FAILURES"
    diagnose backend frontend
    if [[ "$TEARDOWN" -eq 1 ]]; then
        printf '\nTearing down containers (the PostGIS volume is preserved)...\n'
        docker compose down
    else
        printf '\nThe stack is still running. Inspect it with:\n'
        printf '  docker compose ps\n'
        printf '  docker compose logs -f backend\n'
        printf 'Stop it with `docker compose down` (keeps the database volume).\n'
    fi
    exit 1
fi

printf '\n%sPASSED%s  every check succeeded.\n' "$GREEN" "$RESET"
info "frontend:  http://localhost:${FRONTEND_PORT}"
info "API docs:  http://localhost:${FRONTEND_PORT}/docs  (proxied through nginx)"
info "backend:   http://127.0.0.1:${BACKEND_PORT}/docs  (loopback only)"

if [[ "$TEARDOWN" -eq 1 ]]; then
    printf '\nTearing down containers (the PostGIS volume is preserved)...\n'
    docker compose down
else
    printf '\nThe stack is left running. Stop it with `docker compose down`\n'
    printf '(this preserves the geosix_postgres_data volume).\n'
fi
