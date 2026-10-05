"""Dependency-free HTTP probe used by the container ``HEALTHCHECK`` (W41).

The production image must not install an extra package (curl, wget, ...) purely
so Docker has something to execute, so this module probes the API using only the
Python standard library. It is importable *and* runnable:

    python -m app.core.healthcheck --url http://127.0.0.1:8000/api/v1/health

Exit code ``0`` means the service answered ``200``; any other outcome exits ``1``
after printing the reason to stderr, so ``docker inspect``/Compose health status
stays useful instead of collapsing to a bare "unhealthy".

The probe deliberately targets the *existing* public health route and performs no
database query of its own: Compose already gates database start-up on
``pg_isready``, and ``/api/v1/health`` is the contract documented in
``docs/authentication.md``. Nothing here is secret-bearing, so nothing here needs
to be treated as a deployment value.
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from collections.abc import Sequence

#: The established public health route (see ``app/api/v1/health.py``). Loopback on
#: purpose: the probe must succeed even when CORS origins do not include the
#: caller's origin, because a health check is not a browser request.
DEFAULT_URL = "http://127.0.0.1:8000/api/v1/health"

#: Socket timeout, deliberately shorter than the Dockerfile HEALTHCHECK timeout so
#: the probe always fails *before* Docker kills it and records a useless timeout.
DEFAULT_TIMEOUT = 4.0

#: Accepted success codes. Only ``200`` is treated as healthy: a redirect or a
#: proxy error page must not be reported as a healthy API.
EXPECTED_STATUS = 200


def probe(url: str = DEFAULT_URL, timeout: float = DEFAULT_TIMEOUT) -> tuple[bool, str]:
    """Request ``url`` and report whether it answered ``200``.

    Returns a ``(healthy, detail)`` pair. ``detail`` is always populated so the
    caller can print it; it never contains a credential because the URL is a
    health path, not a connection string.
    """
    request = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", None) or response.getcode()
            if status == EXPECTED_STATUS:
                return True, f"GET {url} -> {status}"
            return False, f"GET {url} -> unexpected status {status} (expected {EXPECTED_STATUS})"
    except urllib.error.HTTPError as exc:
        return False, f"GET {url} -> HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return False, f"GET {url} -> connection failed: {exc.reason}"
    except OSError as exc:  # socket timeouts, refused connections, bad DNS, ...
        return False, f"GET {url} -> {type(exc).__name__}: {exc}"


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point used by the image ``HEALTHCHECK``."""
    parser = argparse.ArgumentParser(
        prog="python -m app.core.healthcheck",
        description="Probe the GEOSIX health endpoint and exit non-zero when it is unhealthy.",
    )
    parser.add_argument("--url", default=DEFAULT_URL, help=f"health URL (default: {DEFAULT_URL})")
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"socket timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument("--quiet", action="store_true", help="suppress output on success")
    args = parser.parse_args(list(argv) if argv is not None else None)

    healthy, detail = probe(url=args.url, timeout=args.timeout)
    if healthy:
        if not args.quiet:
            print(detail)
        return 0
    print(detail, file=sys.stderr)
    return 1


if __name__ == "__main__":  # pragma: no cover - exercised via the CLI subprocess
    raise SystemExit(main())
