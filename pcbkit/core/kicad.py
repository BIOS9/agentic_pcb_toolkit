"""KiCad interop primitives: pinned format versions and subprocess helpers.

Everything in pcbkit that shells out to KiCad goes through `run()`. See the
stderr rule in AGENTS.md: KiCad tools write benign diagnostics to stderr, so
success is determined by exit code and parsed output only.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# File format versions emitted by KiCad 10.0.5, confirmed empirically on the
# target machine (see docs/sdlc/M0/spec.md). Emitters target these exactly; the
# doctor check warns when the installed KiCad drifts away from them.
FORMAT_VERSIONS = {
    "kicad_pcb": 20260206,
    "kicad_sch": 20260306,
    "kicad_sym": 20251024,
    "kicad_mod": 20260206,
}

GENERATOR_VERSION = "10.0"
MIN_KICAD_VERSION = (10, 0, 0)

# KiCad 10 renumbered copper layers: F.Cu is 0 and B.Cu is 2 (not 31). Inner
# copper occupies the even numbers between them. Hardcoding pre-10 layer ids is
# a silent-wrong-layer bug, so callers resolve names through pcbnew instead.
F_CU = 0
B_CU = 2

DEFAULT_SYMBOL_DIR = Path("/usr/share/kicad/symbols")
DEFAULT_FOOTPRINT_DIR = Path("/usr/share/kicad/footprints")
DEFAULT_3DMODEL_DIR = Path("/usr/share/kicad/3dmodels")
DEFAULT_TEMPLATE_DIR = Path("/usr/share/kicad/template")


class _Unset:
    """Sentinel: distinguishes 'not probed yet' from a cached None."""


class KicadError(RuntimeError):
    """A KiCad tool failed to run (not: a design has violations)."""


@dataclass(frozen=True)
class Completed:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run(argv: list[str], *, timeout: int = 300, check: bool = False) -> Completed:
    """Run a subprocess, capturing output.

    `check=True` raises KicadError on a nonzero exit. Never infer failure from
    stderr being non-empty: importing pcbnew emits three harmless
    `PROPERTY_ENUM()` wx asserts, and kicad-cli logs progress there.
    """
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "LC_ALL": "C"},
        )
    except FileNotFoundError as exc:
        raise KicadError(f"executable not found: {argv[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise KicadError(f"timed out after {timeout}s: {' '.join(argv)}") from exc

    result = Completed(argv, proc.returncode, proc.stdout, proc.stderr)
    if check and not result.ok:
        raise KicadError(
            f"{' '.join(argv)} exited {result.returncode}\n{result.stderr.strip()}"
        )
    return result


def which(name: str) -> str | None:
    return shutil.which(name)


def parse_version(text: str) -> tuple[int, ...] | None:
    """Parse a leading dotted-numeric version out of arbitrary tool output."""
    for token in text.split():
        head = token.split("-")[0]
        parts = head.split(".")
        if parts and all(p.isdigit() for p in parts) and len(parts) >= 2:
            return tuple(int(p) for p in parts)
    return None


def kicad_cli_version() -> tuple[int, ...] | None:
    exe = which("kicad-cli")
    if exe is None:
        return None
    result = run([exe, "version"], timeout=30)
    return parse_version(result.stdout) if result.ok else None


# pcbnew is a system-installed C++ extension, not a pip package: a plain
# virtualenv cannot see it. So we never `import pcbnew` in-process. Instead we
# resolve the interpreter that owns the bindings once and drive it as a
# subprocess -- which also keeps the wx asserts and GUI-library side effects
# out of our own process.
PCBNEW_PYTHON_ENV = "PCBKIT_PCBNEW_PYTHON"

_PCBNEW_PROBE = (
    "import json, pcbnew;"
    "print(json.dumps({'version': pcbnew.GetBuildVersion()}))"
)

_pcbnew_python: str | None | _Unset = _Unset()


def _interpreter_candidates() -> list[str]:
    override = os.environ.get(PCBNEW_PYTHON_ENV)
    if override:
        return [override]
    candidates = [sys.executable, "/usr/bin/python3", "/usr/local/bin/python3"]
    found = which("python3")
    if found:
        candidates.append(found)
    seen: set[str] = set()
    ordered = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            ordered.append(c)
    return ordered


def _probe_pcbnew(interpreter: str) -> str | None:
    """Return the pcbnew build version this interpreter reports, or None."""
    if not Path(interpreter).exists():
        return None
    try:
        result = run([interpreter, "-c", _PCBNEW_PROBE], timeout=60)
    except KicadError:
        return None
    if not result.ok:
        return None
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)["version"]
            except (json.JSONDecodeError, KeyError):
                continue
    return None


def pcbnew_python() -> str | None:
    """Path to an interpreter that can `import pcbnew`, or None.

    Set PCBKIT_PCBNEW_PYTHON to pin one explicitly on unusual installs.
    """
    global _pcbnew_python
    if not isinstance(_pcbnew_python, _Unset):
        return _pcbnew_python
    for candidate in _interpreter_candidates():
        if _probe_pcbnew(candidate) is not None:
            _pcbnew_python = candidate
            return candidate
    _pcbnew_python = None
    return None


def run_pcbnew(script: str, *, timeout: int = 300) -> Completed:
    """Execute a Python snippet in the interpreter that owns pcbnew."""
    interpreter = pcbnew_python()
    if interpreter is None:
        raise KicadError(
            "no Python interpreter with the pcbnew module was found; "
            f"set {PCBNEW_PYTHON_ENV} to point at one"
        )
    return run([interpreter, "-c", script], timeout=timeout)


def pcbnew_version() -> str | None:
    interpreter = pcbnew_python()
    return _probe_pcbnew(interpreter) if interpreter else None
