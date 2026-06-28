"""ORACLE runtime healthcheck — honest probe of the three local endpoints.

Reports the canonical runtime port (from runtime_config — the single source of
truth), the Ollama model service, and warns if a *stale* instance is squatting
the legacy 7777 port. Makes no claim it cannot verify: if a socket does not
answer, it says DOWN, not "probably fine".

Usage:
    python core/healthcheck.py
Exit code is non-zero if the canonical runtime (7781) is not answering, so the
desktop launcher / scheduled checks can detect a dead runtime.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime_config  # noqa: E402

# Legacy UI port. The canonical runtime is runtime_config.runtime_port() (7781);
# anything answering here is an older/stale copy (historically the Google Drive
# mirror launched with `--port 7777`) and is NOT the governed runtime.
LEGACY_PORT = 7777
OLLAMA_PORT = 11434


def _probe(url: str, timeout: float = 2.0) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return True, f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        # An HTTP error still proves something is listening and answering.
        return True, f"HTTP {e.code}"
    except (urllib.error.URLError, OSError) as e:
        return False, f"no answer ({getattr(e, 'reason', e)})"


def check() -> dict:
    host = runtime_config.runtime_host()
    runtime_port = runtime_config.runtime_port()

    runtime_up, runtime_detail = _probe(f"http://{host}:{runtime_port}/api/mode")
    ollama_up, ollama_detail = _probe(f"http://{host}:{OLLAMA_PORT}/api/tags")
    legacy_up, legacy_detail = _probe(f"http://{host}:{LEGACY_PORT}/api/mode")

    return {
        "runtime": {
            "port": runtime_port,
            "role": "ORACLE canonical runtime UI",
            "up": runtime_up,
            "detail": runtime_detail,
        },
        "ollama": {
            "port": OLLAMA_PORT,
            "role": "Ollama local model service",
            "up": ollama_up,
            "detail": ollama_detail,
        },
        "legacy_7777": {
            "port": LEGACY_PORT,
            "role": "legacy/stale port - NOT the governed runtime",
            "up": legacy_up,
            "detail": legacy_detail,
        },
    }


def _line(name: str, info: dict) -> str:
    state = "UP  " if info["up"] else "DOWN"
    return f"  [{state}] {name:<13} :{info['port']:<5} {info['role']}  ({info['detail']})"


def main() -> int:
    result = check()
    print("ORACLE RUNTIME HEALTHCHECK")
    print(_line("runtime", result["runtime"]))
    print(_line("ollama", result["ollama"]))
    print(_line("legacy", result["legacy_7777"]))

    if result["legacy_7777"]["up"] and not result["runtime"]["up"]:
        print(
            "\n  WARNING: a stale instance is answering on 7777 while the "
            "canonical runtime port is DOWN. The 7777 process is most likely an "
            "older copy (e.g. the Google Drive mirror). Stop it and launch this "
            "repo's runtime on "
            f"{result['runtime']['port']}."
        )

    if not result["runtime"]["up"]:
        print(f"\n  RESULT: canonical runtime ({result['runtime']['port']}) is DOWN.")
        return 1
    print(f"\n  RESULT: canonical runtime ({result['runtime']['port']}) is UP.")
    return 0


if __name__ == "__main__":
    print(json.dumps(check(), indent=2)) if "--json" in sys.argv else None
    raise SystemExit(main())
