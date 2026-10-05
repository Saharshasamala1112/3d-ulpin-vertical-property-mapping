"""Deployment artifacts and health endpoint behaviour (W41).

W41 removed the hardcoded ``Access-Control-Allow-Origin`` header that
``app/api/v1/health.py`` used to set, because a production health endpoint that
advertises ``http://localhost:5173`` conflicts with the application's configured
``CORSMiddleware``. These tests pin the new behaviour in both directions:

* the health payload and status are unchanged (no API-contract break), and
* CORS is decided solely by ``settings.cors_origins``.

The deployment-artifact tests read the committed Dockerfiles, compose file, and
nginx configuration as *text*. They need no Docker daemon, so they run in the
existing unit-test suite on a machine that has never run ``docker compose``.
Container-level assertions (non-root, no build tooling, live health) are the job
of ``scripts/smoke-test.sh``.

Comment lines are stripped before every text assertion: the artifacts explain
*why* they avoid curl and secrets, and a naive substring scan would flag its own
rationale. Only executable directives are inspected.
"""

from __future__ import annotations

import ast
import re
import stat
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.healthcheck import DEFAULT_URL, probe
from app.core.healthcheck import main as healthcheck_main
from app.main import create_app

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
BACKEND_DOCKERFILE = BACKEND_DIR / "Dockerfile"
FRONTEND_DOCKERFILE = FRONTEND_DIR / "Dockerfile"
NGINX_CONF = FRONTEND_DIR / "nginx" / "default.conf"
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
SMOKE_SCRIPT = REPO_ROOT / "scripts" / "smoke-test.sh"
DEPLOYMENT_DOC = REPO_ROOT / "docs" / "deployment.md"

DOCKERFILES = (BACKEND_DOCKERFILE, FRONTEND_DOCKERFILE)

#: The origin the health endpoint used to hardcode, and which the application still
#: allows in development because it is the Vite dev-server origin.
DEV_ORIGIN = "http://localhost:5173"

#: An origin no configuration in the repository permits.
FOREIGN_ORIGIN = "https://attacker.example.com"


def directives(path: Path) -> str:
    """Return the file with full-line comments removed.

    Docker, Compose, and nginx files here are heavily commented on purpose. Only
    the executable lines are asserted on, so a comment that explains the absence
    of a secret cannot be mistaken for the presence of one.
    """
    lines = []
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)


@pytest.fixture(scope="module")
def backend_dockerfile() -> str:
    return directives(BACKEND_DOCKERFILE)


@pytest.fixture(scope="module")
def frontend_dockerfile() -> str:
    return directives(FRONTEND_DOCKERFILE)


@pytest.fixture(scope="module")
def nginx_conf() -> str:
    return directives(NGINX_CONF)


@pytest.fixture(scope="module")
def compose_file() -> str:
    return directives(COMPOSE_FILE)


def service_block(compose_text: str, service: str) -> str:
    """Extract one top-level service block from the (comment-stripped) compose file."""
    lines = compose_text.splitlines()
    start = None
    collected: list[str] = []
    for index, line in enumerate(lines):
        if line.startswith(f"  {service}:"):
            start = index + 1
            continue
        if start is not None:
            # A new top-level key ends the block; so does the next service.
            if re.match(r"^\S", line):
                break
            collected.append(line)
    assert start is not None, f"service {service!r} not found in docker-compose.yml"
    return "\n".join(collected)


# ---------------------------------------------------------------------------
# Health endpoint payload / status contract is unchanged
# ---------------------------------------------------------------------------
class TestHealthContractIsPreserved:
    @pytest.mark.parametrize("path", ["/api/v1/health", "/api/health"])
    def test_both_health_routes_still_exist(self, path: str) -> None:
        """Both routes are part of the documented API contract; neither is removed."""
        with TestClient(create_app()) as client:
            response = client.get(path)

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "geosix-api"}

    def test_health_module_no_longer_references_a_cors_header(self) -> None:
        """app/api/v1/health.py must not mention a CORS header in code.

        Checked against the module *source* with string literals inspected, so the
        explanation of why the header was removed stays readable in the docstring.
        """
        from app.api.v1 import health

        tree = ast.parse(Path(health.__file__).read_text())
        # clean=False: the raw literal is what appears as an ast.Constant, so the
        # default dedent would fail to match it.
        docstrings = {
            ast.get_docstring(node, clean=False)
            for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }
        literals = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            # The route docstring legitimately explains the removal, so it is allowed
            # to name the header and the development origin.
            and node.value not in docstrings
        ]

        for literal in literals:
            assert "Access-Control" not in literal, f"health.py sets a CORS header: {literal!r}"
            assert "5173" not in literal, f"health.py hardcodes the dev origin: {literal!r}"

        assert literals == ["/health", "status", "service", "ok", "geosix-api"]

    def test_health_handler_writes_no_response_headers(self) -> None:
        """No runtime code path may assign a response header in the handler."""
        from app.api.v1 import health

        tree = ast.parse(Path(health.__file__).read_text())
        assignments = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Subscript)
            # response.headers["X"] = ...
            and isinstance(target.value, ast.Attribute)
            and target.value.attr == "headers"
        ]

        assert assignments == [], "health.py must not set response headers"

    def test_configured_origin_is_allowed(self) -> None:
        """The Vite dev origin is in the default cors_origins, so it is echoed."""
        with TestClient(create_app()) as client:
            response = client.get("/api/v1/health", headers={"Origin": DEV_ORIGIN})

        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == DEV_ORIGIN

    @pytest.mark.parametrize("origin", [FOREIGN_ORIGIN, "http://localhost:9999", "null"])
    def test_unconfigured_origin_is_not_echoed(self, origin: str) -> None:
        """No allow-origin header may appear for an origin outside cors_origins."""
        with TestClient(create_app()) as client:
            response = client.get("/api/v1/health", headers={"Origin": origin})

        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers

    def test_cors_follows_configured_origins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With explicit origins the middleware, not the handler, decides.

        ``create_app()`` builds ``CORSMiddleware`` from ``settings.cors_origins`` at
        construction time, so the setting must be replaced *before* the app is built.
        """
        from app import main as main_module

        monkeypatch.setattr(main_module.settings, "cors_origins", ["https://geosix.example.com"])
        app = create_app()

        with TestClient(app) as client:
            allowed = client.get("/api/v1/health", headers={"Origin": "https://geosix.example.com"})
            previously_allowed = client.get("/api/v1/health", headers={"Origin": DEV_ORIGIN})

        assert allowed.headers.get("access-control-allow-origin") == "https://geosix.example.com"
        assert "access-control-allow-origin" not in previously_allowed.headers

    def test_health_route_declares_no_database_dependency(self) -> None:
        """Readiness is gated by pg_isready in Compose, so health must stay cheap.

        Static rather than dynamic: ``lifespan`` runs one ``SELECT 1`` at startup
        (see ``app/main.py``), and that must not be confused with the health route
        re-querying on every request. Asserting the route has no ``Depends(get_db)``
        pins that without needing a database.
        """
        from app.core.database import get_db

        app = create_app()
        health_routes = [
            route for route in app.routes if getattr(route, "path", "").endswith("/health")
        ]
        assert health_routes, "no health route found on the application"

        for route in health_routes:
            for dependency in route.dependant.dependencies:
                assert dependency.call is not get_db, (
                    f"{route.path} must not depend on the database session"
                )
                for sub_dependency in dependency.dependencies:
                    assert sub_dependency.call is not get_db

    def test_health_answers_while_the_database_is_unreachable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A liveness probe must not fail just because PostGIS is down."""
        from app.core import database as database_module

        def _explode(*args, **kwargs):
            raise AssertionError("the health endpoint must not open a database session")

        # The lifespan probe is the one place the database is legitimately touched.
        # Bypass it by not entering the TestClient context manager (which would fire
        # startup), then make any session creation fail loudly.
        monkeypatch.setattr(database_module, "SessionLocal", _explode)

        client = TestClient(create_app())
        try:
            response = client.get("/api/v1/health")
        finally:
            client.close()

        assert response.status_code == 200
        assert response.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# The stdlib health probe used by HEALTHCHECK
# ---------------------------------------------------------------------------
class TestHealthcheckProbe:
    def test_default_url_targets_the_documented_route(self) -> None:
        assert DEFAULT_URL == "http://127.0.0.1:8000/api/v1/health"

    def test_probe_reports_healthy_for_200(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *exc_info):
                return False

        monkeypatch.setattr(
            "app.core.healthcheck.urllib.request.urlopen", lambda *a, **kw: _Response()
        )

        healthy, detail = probe()

        assert healthy is True
        assert "200" in detail

    def test_probe_rejects_a_non_200_status(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _Response:
            status = 503

            def __enter__(self):
                return self

            def __exit__(self, *exc_info):
                return False

        monkeypatch.setattr(
            "app.core.healthcheck.urllib.request.urlopen", lambda *a, **kw: _Response()
        )

        healthy, detail = probe()

        assert healthy is False
        assert "503" in detail

    def test_probe_reports_http_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import urllib.error

        def _raise(*args, **kwargs):
            raise urllib.error.HTTPError(url="x", code=503, msg="unavailable", hdrs=None, fp=None)

        monkeypatch.setattr("app.core.healthcheck.urllib.request.urlopen", _raise)

        healthy, detail = probe()

        assert healthy is False
        assert "503" in detail

    def test_probe_reports_connection_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import urllib.error

        def _raise(*args, **kwargs):
            raise urllib.error.URLError("connection refused")

        monkeypatch.setattr("app.core.healthcheck.urllib.request.urlopen", _raise)

        healthy, detail = probe()

        assert healthy is False
        assert "connection refused" in detail

    def test_main_exits_zero_when_healthy(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr("app.core.healthcheck.probe", lambda **kw: (True, "GET ok -> 200"))

        assert healthcheck_main(["--quiet"]) == 0
        assert capsys.readouterr().out == ""

    def test_main_exits_non_zero_when_unhealthy(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr("app.core.healthcheck.probe", lambda **kw: (False, "boom"))

        assert healthcheck_main([]) == 1
        assert "boom" in capsys.readouterr().err

    def test_probe_uses_only_the_standard_library(self) -> None:
        """No third-party import may leak into the probe module."""
        from app.core import healthcheck as module

        tree = ast.parse(Path(module.__file__).read_text())
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])

        assert imported <= {
            "__future__",
            "argparse",
            "sys",
            "urllib",
            "collections",
        }, f"healthcheck.py imported {sorted(imported)}"


# ---------------------------------------------------------------------------
# Deployment artifacts exist
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("path", DOCKERFILES, ids=lambda p: p.parent.name)
def test_dockerfile_is_multi_stage(path: Path) -> None:
    assert path.is_file(), f"{path} is required by W41"
    stages = re.findall(r"^FROM ", directives(path), flags=re.MULTILINE)
    assert len(stages) >= 2, "W41 requires a multi-stage build"


def test_nginx_config_exists() -> None:
    assert NGINX_CONF.is_file()


def test_dockerignore_files_exist() -> None:
    assert (BACKEND_DIR / ".dockerignore").is_file()
    assert (FRONTEND_DIR / ".dockerignore").is_file()


def test_dockerignores_exclude_env_files() -> None:
    """`COPY . .` must not be able to pick up a developer's .env."""
    for ignore in (BACKEND_DIR / ".dockerignore", FRONTEND_DIR / ".dockerignore"):
        text = ignore.read_text()
        assert re.search(r"^\.env$", text, flags=re.MULTILINE), f"{ignore} must exclude .env"


def test_smoke_test_script_exists_and_is_executable() -> None:
    assert SMOKE_SCRIPT.is_file()
    assert SMOKE_SCRIPT.read_text().startswith("#!")
    assert SMOKE_SCRIPT.stat().st_mode & stat.S_IXUSR, "smoke-test.sh must be executable"


def test_smoke_test_never_destroys_the_postgis_volume() -> None:
    """No destructive volume command may appear in any executed line.

    Comments are stripped first: the script's header explains *why* ``down -v`` is
    never run, and that explanation must not trip this check.
    """
    executable = "\n".join(
        line for line in SMOKE_SCRIPT.read_text().splitlines() if not line.strip().startswith("#")
    )
    for forbidden in ("down -v", "--volumes", "volume rm", "prune"):
        assert forbidden not in executable, f"smoke-test.sh runs a destructive command: {forbidden}"


def test_smoke_test_uses_the_compose_v2_plugin() -> None:
    text = SMOKE_SCRIPT.read_text()
    assert "docker compose" in text
    assert "docker-compose" not in text, "use the v2 `docker compose` plugin"


def test_deployment_documentation_covers_the_required_sections() -> None:
    assert DEPLOYMENT_DOC.is_file()
    text = DEPLOYMENT_DOC.read_text()
    for heading in (
        "## Purpose",
        "## Architecture",
        "## Prerequisites",
        "## Environment configuration",
        "## Local development",
        "## Full Compose deployment",
        "## Database-only Compose usage",
        "## Production checklist",
        "## Backend configuration",
        "## Frontend configuration",
        "## JWT and security",
        "## CORS",
        "## SMTP",
        "## Database and PostGIS",
        "## Reverse proxy and TLS",
        "## Health checks",
        "## Smoke test",
        "## Migrations",
        "## Backup and restore",
        "## Upgrade procedure",
        "## Troubleshooting",
        "## Secret handling",
        "## Container hardening",
        "## CI and image registry",
    ):
        assert heading in text, f"docs/deployment.md must contain a {heading!r} section"


def test_deployment_documentation_does_not_claim_cloud_provisioning() -> None:
    text = DEPLOYMENT_DOC.read_text().lower()
    for forbidden in ("terraform", "kubernetes", "helm chart"):
        assert forbidden not in text, f"docs/deployment.md mentions {forbidden!r}"


# ---------------------------------------------------------------------------
# No secrets in the deployment artifacts
# ---------------------------------------------------------------------------
#: Directives that would assign a credential inside an image.
_SECRET_ASSIGNMENT = re.compile(
    r"^\s*(?:ENV|ARG)\s+(?:JWT_SECRET_KEY|SMTP_PASSWORD|POSTGRES_PASSWORD|DATABASE_URL)\s*=\s*\S",
    flags=re.MULTILINE,
)


@pytest.mark.parametrize("path", DOCKERFILES, ids=lambda p: p.parent.name)
def test_dockerfiles_bake_in_no_secrets(path: Path) -> None:
    matches = _SECRET_ASSIGNMENT.findall(directives(path))
    assert not matches, f"{path} assigns a credential via ENV/ARG: {matches}"


@pytest.mark.parametrize("path", DOCKERFILES, ids=lambda p: p.parent.name)
def test_dockerfiles_never_copy_env_files(path: Path) -> None:
    for line in directives(path).splitlines():
        assert not re.search(r"^COPY\b.*\.env", line.strip()), (
            f"{path} copies a .env file into the image: {line.strip()}"
        )


def test_compose_interpolates_every_credential(compose_file: str) -> None:
    """Compose must interpolate, never assign, credential-bearing variables."""
    for variable in ("JWT_SECRET_KEY", "SMTP_PASSWORD", "POSTGRES_PASSWORD"):
        occurrences = re.findall(rf"{variable}[^\n]*", compose_file)
        assert occurrences, f"{variable} should still be wired into compose"
        for occurrence in occurrences:
            assert "${" in occurrence, (
                f"docker-compose.yml assigns {variable} without interpolation: {occurrence}"
            )


def test_compose_never_points_the_browser_at_a_docker_service_name(compose_file: str) -> None:
    """The browser must keep using the frontend origin, never `backend:8000`."""
    assert "VITE_API_BASE_URL" not in compose_file
    assert "http://backend:8000" not in compose_file


def test_compose_local_defaults_are_the_documented_development_values(compose_file: str) -> None:
    """The zero-setup defaults must match backend/.env.example, not a real secret."""
    assert "${DEBUG:-true}" in compose_file
    assert "${JWT_SECRET_KEY:-geosix-insecure-development-only-secret}" in compose_file


# ---------------------------------------------------------------------------
# Backend Dockerfile specifics
# ---------------------------------------------------------------------------
class TestBackendDockerfile:
    def test_runs_as_a_dedicated_non_root_user(self, backend_dockerfile: str) -> None:
        assert re.search(r"^USER\s+(?!root$|0$)(\S+)", backend_dockerfile, flags=re.MULTILINE), (
            "the backend image must switch to a non-root user"
        )
        assert "useradd" in backend_dockerfile
        assert "--system" in backend_dockerfile
        # The USER directive must appear after the filesystem copies, otherwise the
        # build would run as root.
        assert backend_dockerfile.index("USER ") > backend_dockerfile.rindex("COPY")

    def test_exposes_port_8000(self, backend_dockerfile: str) -> None:
        assert re.search(r"^EXPOSE\s+8000", backend_dockerfile, flags=re.MULTILINE)

    def test_startup_is_production_uvicorn_without_reload(self, backend_dockerfile: str) -> None:
        # HEALTHCHECK also uses CMD, so select the instruction that starts the app.
        cmd_lines = [
            line.strip()
            for line in backend_dockerfile.splitlines()
            if line.strip().startswith("CMD ") and "uvicorn" in line
        ]
        assert cmd_lines, "the backend image needs a CMD that starts uvicorn"
        assert len(cmd_lines) == 1
        command = cmd_lines[0]

        assert command.startswith("CMD ["), "use exec form so signals reach uvicorn"
        assert "uvicorn" in command
        assert "0.0.0.0" in command
        assert "--reload" not in command
        assert "--workers" in command, "production startup should use multiple workers"

    def test_healthcheck_uses_the_health_endpoint(self, backend_dockerfile: str) -> None:
        assert "HEALTHCHECK" in backend_dockerfile
        assert "app.core.healthcheck" in backend_dockerfile
        assert "/api/v1/health" in backend_dockerfile
        assert "--start-period" in backend_dockerfile

    def test_healthcheck_adds_no_package(self, backend_dockerfile: str) -> None:
        """No apt-get and no curl/wget download: the probe is stdlib only."""
        assert "apt-get" not in backend_dockerfile
        for binary in ("curl", "wget"):
            assert not re.search(
                rf"^\s*(?:RUN|ENV|ARG).*\b{binary}\b", backend_dockerfile, flags=re.MULTILINE
            ), f"the backend image should not install {binary}"

    def test_installs_the_application_not_the_dev_extra(self, backend_dockerfile: str) -> None:
        assert re.search(r"pip install[^\n]*\s\.(?!\")", backend_dockerfile)
        assert ".[dev]" not in backend_dockerfile
        assert '"dev"' not in backend_dockerfile

    def test_never_installs_test_requirements(self, backend_dockerfile: str) -> None:
        assert "requirements.txt" not in backend_dockerfile
        assert not re.search(r"pip install[^\n]*(pytest|ruff)", backend_dockerfile)

    def test_removes_the_package_installer_from_the_final_image(
        self, backend_dockerfile: str
    ) -> None:
        """The builder uninstalls pip; the final venv must carry no build tooling."""
        assert "pip uninstall" in backend_dockerfile
        assert re.search(r"pip uninstall[^\n]*\bpip\b", backend_dockerfile)

    def test_ships_the_alembic_migration_environment(self, backend_dockerfile: str) -> None:
        """`alembic upgrade head` must be runnable inside the image."""
        assert "COPY --chown=root:root alembic.ini ./alembic.ini" in backend_dockerfile
        assert "COPY --chown=root:root alembic ./alembic" in backend_dockerfile

    def test_does_not_copy_tests_or_virtualenvs(self, backend_dockerfile: str) -> None:
        for forbidden in ("COPY tests", "COPY .venv", "COPY venv", "COPY . "):
            assert forbidden not in backend_dockerfile

    def test_uses_a_supported_python_version(self, backend_dockerfile: str) -> None:
        assert re.search(r"ARG PYTHON_VERSION=3\.1[1-9]", backend_dockerfile)


# ---------------------------------------------------------------------------
# Frontend Dockerfile / nginx specifics
# ---------------------------------------------------------------------------
class TestFrontendDockerfile:
    def test_uses_node_then_nginx(self, frontend_dockerfile: str) -> None:
        assert "FROM node:" in frontend_dockerfile
        assert re.search(r"^FROM\s+\S*nginx", frontend_dockerfile, flags=re.MULTILINE)

    def test_final_stage_has_no_node_tooling(self, frontend_dockerfile: str) -> None:
        stages = frontend_dockerfile.split("FROM ")[1:]
        assert len(stages) >= 2
        runtime_stage = stages[-1]
        assert "node:" not in runtime_stage
        assert not re.search(r"^\s*RUN.*\bnpm\b", runtime_stage, flags=re.MULTILINE)

    def test_runs_as_non_root(self, frontend_dockerfile: str) -> None:
        match = re.search(r"^USER\s+(?!root$|0$)(\S+)", frontend_dockerfile, flags=re.MULTILINE)
        assert match, "the frontend image must declare a non-root user"
        assert "nginx" in match.group(1)

    def test_does_not_bake_in_an_api_base_url(self, frontend_dockerfile: str) -> None:
        """The image stays environment independent: no ARG/ENV for the API host."""
        assert not re.search(
            r"^(?:ARG|ENV)\s+VITE_API_BASE_URL=", frontend_dockerfile, flags=re.MULTILINE
        )

    def test_installs_dependencies_from_the_lockfile(self, frontend_dockerfile: str) -> None:
        assert "npm ci" in frontend_dockerfile
        assert "package-lock.json" in frontend_dockerfile

    def test_has_a_healthcheck(self, frontend_dockerfile: str) -> None:
        assert "HEALTHCHECK" in frontend_dockerfile
        assert "/healthz" in frontend_dockerfile

    def test_exposes_8080(self, frontend_dockerfile: str) -> None:
        assert re.search(r"^EXPOSE\s+8080", frontend_dockerfile, flags=re.MULTILINE)


class TestNginxConfiguration:
    def test_proxies_api_to_the_backend_service(self, nginx_conf: str) -> None:
        assert re.search(r"location\s+/api/\s*\{", nginx_conf)
        assert "proxy_pass" in nginx_conf
        assert "backend:8000" in nginx_conf

    def test_spa_history_fallback_is_configured(self, nginx_conf: str) -> None:
        assert re.search(r"try_files\s+\$uri\s+\$uri/\s+/index\.html;", nginx_conf)

    def test_sets_forwarding_headers(self, nginx_conf: str) -> None:
        for header in ("Host", "X-Real-IP", "X-Forwarded-For", "X-Forwarded-Proto"):
            assert f"proxy_set_header {header}" in nginx_conf

    def test_caches_hashed_assets(self, nginx_conf: str) -> None:
        assert "location /assets/" in nginx_conf
        assert "immutable" in nginx_conf

    def test_hides_the_server_token(self, nginx_conf: str) -> None:
        assert "server_tokens off;" in nginx_conf

    def test_denies_dotfiles(self, nginx_conf: str) -> None:
        assert re.search(r"location\s+~\s+/\\\.\s*\{", nginx_conf)
        assert "deny all;" in nginx_conf

    def test_sets_an_explicit_local_health_probe(self, nginx_conf: str) -> None:
        assert "location = /healthz" in nginx_conf
        assert "return 200" in nginx_conf

    def test_contains_no_credential(self, nginx_conf: str) -> None:
        for marker in ("password", "secret", "Authorization", "proxy_set_header Cookie"):
            assert marker not in nginx_conf, f"nginx configuration mentions {marker!r}"

    def test_does_not_expose_the_filesystem_root(self, nginx_conf: str) -> None:
        """Document root must be the copied static output, never / or /etc."""
        roots = re.findall(r"^\s*root\s+(\S+);", nginx_conf, flags=re.MULTILINE)
        assert roots, "a root directive is expected"
        for value in roots:
            assert value.startswith("/usr/share/nginx/html"), f"unexpected document root {value}"

    def test_listens_on_8080(self, nginx_conf: str) -> None:
        assert re.search(r"listen\s+8080;", nginx_conf)


# ---------------------------------------------------------------------------
# Compose specifics
# ---------------------------------------------------------------------------
class TestComposeFile:
    def test_defines_all_three_services(self, compose_file: str) -> None:
        assert re.search(r"^services:", compose_file, flags=re.MULTILINE)
        for service in ("postgres", "backend", "frontend"):
            assert service_block(compose_file, service), f"missing service {service}"

    def test_preserves_the_postgis_image_and_volume(self, compose_file: str) -> None:
        assert "postgis/postgis:16-3.4" in compose_file
        assert "geosix_postgres_data" in compose_file
        assert "/var/lib/postgresql/data" in compose_file
        assert re.search(r"^volumes:", compose_file, flags=re.MULTILINE)

    def test_preserves_the_postgres_healthcheck(self, compose_file: str) -> None:
        assert "pg_isready" in service_block(compose_file, "postgres")

    def test_backend_waits_for_a_healthy_database(self, compose_file: str) -> None:
        backend = service_block(compose_file, "backend")
        assert "postgres:" in backend
        assert "condition: service_healthy" in backend

    def test_backend_database_url_uses_the_compose_service_name(self, compose_file: str) -> None:
        """`localhost` inside the backend container is the backend container."""
        match = re.search(r"DATABASE_URL:\s*(\S+)", compose_file)
        assert match
        assert "@postgres:5432/" in match.group(1)
        assert "localhost" not in match.group(1)

    def test_backend_is_built_from_its_own_dockerfile(self, compose_file: str) -> None:
        backend = service_block(compose_file, "backend")
        assert "context: ./backend" in backend
        assert "dockerfile: Dockerfile" in backend

    def test_backend_healthcheck_uses_the_health_endpoint(self, compose_file: str) -> None:
        backend = service_block(compose_file, "backend")
        assert "app.core.healthcheck" in backend
        assert "http://127.0.0.1:8000/api/v1/health" in backend

    def test_backend_passes_jwt_and_cors_through_the_environment(self, compose_file: str) -> None:
        backend = service_block(compose_file, "backend")
        assert "${JWT_SECRET_KEY:-" in backend
        assert "${CORS_ORIGINS:-" in backend
        assert "${DEBUG:-" in backend

    def test_backend_passes_every_settings_field(self, compose_file: str) -> None:
        """Every app/core/config.py field must be reachable from Compose.

        Guards against a deployment that silently runs on a Settings default.
        """
        backend = service_block(compose_file, "backend")
        for field in Settings.model_fields:
            variable = field.upper()
            assert re.search(rf"^\s+{variable}:", backend, flags=re.MULTILINE), (
                f"{variable} ({field}) is not passed to the backend container"
            )

    def test_frontend_waits_for_a_healthy_backend(self, compose_file: str) -> None:
        frontend = service_block(compose_file, "frontend")
        assert "backend:" in frontend
        assert "condition: service_healthy" in frontend

    def test_frontend_does_not_depend_on_postgres(self, compose_file: str) -> None:
        frontend = service_block(compose_file, "frontend")
        assert "postgres" not in frontend
        assert "DATABASE_URL" not in frontend

    def test_frontend_is_built_from_its_own_dockerfile(self, compose_file: str) -> None:
        frontend = service_block(compose_file, "frontend")
        assert "context: ./frontend" in frontend
        assert "dockerfile: Dockerfile" in frontend

    def test_frontend_port_avoids_the_vite_dev_port_by_default(self, compose_file: str) -> None:
        frontend = service_block(compose_file, "frontend")
        assert "${FRONTEND_PORT:-8080}:8080" in frontend

    def test_healthchecks_are_defined_for_every_service(self, compose_file: str) -> None:
        for service in ("postgres", "backend", "frontend"):
            assert "healthcheck:" in service_block(compose_file, service)

    def test_published_ports_are_bound_to_loopback_for_the_data_services(
        self, compose_file: str
    ) -> None:
        """Postgres and the backend must not listen on every host interface."""
        for service in ("postgres", "backend"):
            block = service_block(compose_file, service)
            port_match = re.search(r"^    ports:\n((?:      .*\n?)*)", block, flags=re.MULTILINE)
            assert port_match, f"{service} has no ports: mapping"
            published = re.findall(r'-\s*"([^"]+)"', port_match.group(1))
            assert published, f"{service} publishes no port"
            for mapping in published:
                # e.g. 127.0.0.1:${BACKEND_PORT:-8000}:8000
                assert mapping.startswith("127.0.0.1:"), (
                    f"{service} publishes {mapping} on all host interfaces"
                )
