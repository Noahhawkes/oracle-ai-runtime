"""Single source of truth for the ORACLE runtime network endpoint.

The runtime (`oracle_server.py`) binds exactly one port. Every displayed
operational receipt, health check, and SourceMap runtime string must report
*that* port — not a stale literal copied into a dozen modules. Reading the port
from here keeps them all in sync.

Resolution order:
  1. ``ORACLE_PORT`` environment variable (set by oracle_server at startup to the
     actually-bound CLI/default port, so in-process diagnostics agree with the
     live socket).
  2. ``DEFAULT_RUNTIME_PORT`` below.

Preview/dev runs on a separate, fixed port (``PREVIEW_PORT``) and is
intentionally unaffected by the runtime port.
"""

from __future__ import annotations

import os

# Canonical ORACLE runtime port. Changing this default moves the runtime
# everywhere that reads through this module.
DEFAULT_RUNTIME_PORT = 7781

# Preview/dev only. NOT the runtime port; never derived from it.
PREVIEW_PORT = 7778

DEFAULT_RUNTIME_HOST = "127.0.0.1"

_ENV_PORT = "ORACLE_PORT"
_ENV_HOST = "ORACLE_HOST"


def _coerce_port(raw: object) -> int | None:
    try:
        port = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return port if 1 <= port <= 65535 else None


def runtime_port() -> int:
    """The configured runtime port (env override, else the built-in default)."""
    return _coerce_port(os.environ.get(_ENV_PORT)) or DEFAULT_RUNTIME_PORT


def set_runtime_port(port: int) -> int:
    """Record the actually-bound runtime port so in-process diagnostics match it.

    Called once by ``oracle_server`` after the CLI/default port is resolved.
    Persisting it in the environment lets sibling modules (operational_state,
    capability_broker, presence_daemon) report the same port without being
    passed it explicitly.
    """
    coerced = _coerce_port(port)
    if coerced is None:
        raise ValueError(f"invalid runtime port: {port!r}")
    os.environ[_ENV_PORT] = str(coerced)
    return coerced


def runtime_host() -> str:
    return os.environ.get(_ENV_HOST) or DEFAULT_RUNTIME_HOST


def runtime_authority(host: str = "localhost") -> str:
    """`host:port` authority for human-facing strings (defaults to localhost)."""
    return f"{host}:{runtime_port()}"


def runtime_base_url(host: str | None = None) -> str:
    """`http://host:port` base URL for probes and links."""
    return f"http://{host or runtime_host()}:{runtime_port()}"
