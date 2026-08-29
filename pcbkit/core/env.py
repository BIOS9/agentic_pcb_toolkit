"""Environment verification: `pcbkit doctor`.

Every later milestone assumes a specific toolchain. Rather than let an emitter
fail deep inside a subprocess with an opaque message, verify the assumptions up
front and say exactly what is missing and how to fix it.
"""

from __future__ import annotations

import enum
import re
import sys
import tempfile
from pathlib import Path

from pydantic import BaseModel

from pcbkit.core import kicad, toolchain
from pcbkit.core.result import Envelope, Finding, Severity

CACHE_DIR = Path.home() / ".cache" / "pcbkit"
FREEROUTING_JAR = CACHE_DIR / "freerouting-2.3.0.jar"


class Status(str, enum.Enum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


class Check(BaseModel):
    id: str
    status: Status
    detail: str
    remedy: str | None = None


def _ok(id_: str, detail: str) -> Check:
    return Check(id=id_, status=Status.OK, detail=detail)


def _fail(id_: str, detail: str, remedy: str) -> Check:
    return Check(id=id_, status=Status.FAIL, detail=detail, remedy=remedy)


def _warn(id_: str, detail: str, remedy: str) -> Check:
    return Check(id=id_, status=Status.WARN, detail=detail, remedy=remedy)


def check_python() -> Check:
    v = sys.version_info
    text = f"{v.major}.{v.minor}.{v.micro}"
    if (v.major, v.minor) < (3, 12):
        return _fail("python", text, "pcbkit requires Python >= 3.12")
    return _ok("python", text)


def check_kicad_cli() -> Check:
    resolved = toolchain.resolve_tool("kicad-cli")
    exe = str(resolved.path) if resolved.path else None
    if exe is None:
        return _fail(
            "kicad-cli",
            "not found",
            "install KiCad 10 or later, or enter the flake shell (`nix develop`)",
        )
    version = kicad.kicad_cli_version()
    if version is None:
        return _fail("kicad-cli", f"{exe}: could not parse version", "check the install")
    text = ".".join(str(p) for p in version)
    if version < kicad.MIN_KICAD_VERSION:
        want = ".".join(str(p) for p in kicad.MIN_KICAD_VERSION)
        return _fail("kicad-cli", f"{text} at {exe}", f"pcbkit needs >= {want}")
    return _ok("kicad-cli", f"{text} at {resolved.describe()}")


def check_pcbnew() -> Check:
    interpreter = kicad.pcbnew_python()
    if interpreter is None:
        return _fail(
            "pcbnew",
            "no interpreter on this system can import pcbnew",
            "install the KiCad Python bindings (Arch: kicad; Debian: python3-pcbnew), "
            f"or set {kicad.PCBNEW_PYTHON_ENV} to an interpreter that has them",
        )
    version = kicad.pcbnew_version()
    return _ok("pcbnew", f"{version} via {interpreter}")


def check_libraries() -> list[Check]:
    checks: list[Check] = []
    for id_, pattern, minimum in (
        ("symbols", "*.kicad_sym", 50),
        ("footprints", "*.pretty", 50),
        ("3dmodels", "*", 10),
    ):
        resolved = toolchain.resolve_library(id_)
        path = resolved.path
        if path is None:
            checks.append(
                _fail(
                    id_,
                    "not found",
                    f"install the KiCad {id_} library package, or set "
                    f"{toolchain._DIRS_BY_NAME[id_].env_var}",
                )
            )
            continue
        count = len(list(path.glob(pattern)))
        detail = f"{count} in {resolved.describe()}"
        if count < minimum:
            checks.append(
                _warn(id_, detail, f"expected at least {minimum}; library may be partial")
            )
        else:
            checks.append(_ok(id_, detail))
    return checks


def check_pcb_format() -> Check:
    """Detect file-format drift by asking pcbnew to write a board.

    A KiCad upgrade that bumps the format is the most likely way the emitters
    silently start producing files the installed tools reject, so catch it here
    rather than three milestones downstream.
    """
    expected = kicad.FORMAT_VERSIONS["kicad_pcb"]
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "probe.kicad_pcb"
        script = (
            "import pcbnew;"
            f"b = pcbnew.NewBoard({str(target)!r});"
            f"pcbnew.SaveBoard({str(target)!r}, b)"
        )
        try:
            result = kicad.run_pcbnew(script, timeout=60)
        except kicad.KicadError as exc:
            return _fail("pcb-format", str(exc), "resolve the pcbnew check first")
        if not result.ok or not target.exists():
            return _fail(
                "pcb-format",
                "pcbnew could not write a probe board",
                result.stderr.strip()[:200] or "check the KiCad install",
            )
        match = re.search(r"\(version (\d+)\)", target.read_text()[:400])

    if match is None:
        return _fail("pcb-format", "no version token in written board", "unexpected format")
    found = int(match.group(1))
    if found != expected:
        return _warn(
            "pcb-format",
            f"KiCad writes {found}, pcbkit targets {expected}",
            "review pcbkit/core/kicad.py FORMAT_VERSIONS and re-run the emitter tests",
        )
    return _ok("pcb-format", str(found))


def check_ngspice() -> Check:
    resolved = toolchain.resolve_tool("ngspice")
    if not resolved.found:
        return _warn(
            "ngspice", "not found", "optional; needed for `pcbkit check --sim` (M7)"
        )
    return _ok("ngspice", resolved.describe())


def check_java() -> Check:
    resolved = toolchain.resolve_tool("java")
    if not resolved.found:
        return _warn(
            "java", "not found", "optional; needed by the freerouting autorouter (M9)"
        )
    return _ok("java", resolved.describe())


def check_pinned() -> Check:
    """Provenance, not availability.

    An unpinned environment works; it just cannot promise the same output on
    another machine. Reporting that plainly is the point of CR-004 -- the old
    format-drift warning was a symptom of not knowing.
    """
    if toolchain.is_pinned():
        return _ok("toolchain", "pinned (nix)")
    return _warn(
        "toolchain",
        "unpinned (system tools)",
        "run `nix develop` for a reproducible toolchain; builds still work "
        "without it, but are not guaranteed to match another machine",
    )


def check_freerouting() -> Check:
    """Since M2 this comes from the flake rather than a downloaded jar.

    The cached-jar path stays as a fallback for unpinned users, but a pinned
    environment should never reach it -- downloading a router at first use is
    exactly the non-reproducibility CR-004 removes.
    """
    resolved = toolchain.resolve_tool("freerouting")
    if resolved.found:
        return _ok("freerouting", resolved.describe())
    if FREEROUTING_JAR.exists():
        size_mb = FREEROUTING_JAR.stat().st_size // (1024 * 1024)
        return _ok("freerouting", f"{FREEROUTING_JAR} ({size_mb} MB, unpinned cache)")
    return _warn(
        "freerouting",
        "not found",
        "optional until M9; provided by `nix develop`, or cached on first use",
    )


def all_checks() -> list[Check]:
    checks = [check_pinned(), check_python(), check_kicad_cli(), check_pcbnew()]
    checks.extend(check_libraries())
    # Only meaningful once pcbnew imports; skip rather than report a confusing
    # second failure for the same root cause.
    if checks[3].status is Status.OK:
        checks.append(check_pcb_format())
    checks.extend([check_ngspice(), check_java(), check_freerouting()])
    return checks


_SEVERITY = {Status.FAIL: Severity.ERROR, Status.WARN: Severity.WARNING}


def doctor() -> Envelope:
    checks = all_checks()
    findings = [
        Finding(
            source="env",
            code=f"env.{c.id}",
            severity=_SEVERITY[c.status],
            message=c.detail,
            fix=c.remedy,
        )
        for c in checks
        if c.status is not Status.OK
    ]
    return Envelope(
        command="doctor",
        data={
            "checks": [c.model_dump(mode="json") for c in checks],
            "healthy": not any(c.status is Status.FAIL for c in checks),
            "pinned": toolchain.is_pinned(),
            "toolchain": toolchain.summary(),
            "format_versions": kicad.FORMAT_VERSIONS,
        },
        findings=findings,
    )
