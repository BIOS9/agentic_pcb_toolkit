"""One place that answers "where is this tool, and who said so".

Before M2, `core/kicad.py` hardcoded four `/usr/share/kicad` paths and resolved
executables off `PATH`, which made a design's output a function of the machine
that built it. Everything external now resolves here, and every answer carries
its provenance, so `pcbkit doctor` can state whether the environment is pinned
instead of quietly hoping.

The unpinned fallback is deliberate: locking out a user who has KiCad installed
but not Nix would be a worse failure than being unpinned. What changed is that
pcbkit knows which happened.
"""

from __future__ import annotations

import enum
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

# Set by the flake's devShell. Its presence is what "pinned" means.
TOOLCHAIN_ENV = "PCBKIT_TOOLCHAIN"


class Source(str, enum.Enum):
    """Where a resolved value came from. Ordered most to least authoritative."""

    OVERRIDE = "override"  # explicit PCBKIT_* environment variable
    PINNED = "pinned"  # supplied by the flake
    SYSTEM = "system"  # PATH lookup or a historical default
    MISSING = "missing"


@dataclass(frozen=True)
class Resolved:
    name: str
    path: Path | None
    source: Source

    @property
    def found(self) -> bool:
        return self.path is not None

    def describe(self) -> str:
        if self.path is None:
            return f"not found ({self.source.value})"
        return f"{self.path} ({self.source.value})"


@dataclass(frozen=True)
class Tool:
    """An external program pcbkit shells out to."""

    name: str
    env_var: str
    executable: str


@dataclass(frozen=True)
class LibraryDir:
    """A KiCad data directory."""

    name: str
    env_var: str
    fallback: Path


TOOLS = (
    Tool("kicad-cli", "PCBKIT_KICAD_CLI", "kicad-cli"),
    Tool("ngspice", "PCBKIT_NGSPICE", "ngspice"),
    Tool("java", "PCBKIT_JAVA", "java"),
    Tool("freerouting", "PCBKIT_FREEROUTING", "freerouting"),
)

# The historical /usr/share/kicad defaults. These are the *only* place such
# literals may appear -- tests/test_toolchain.py enforces that.
LIBRARY_DIRS = (
    LibraryDir("symbols", "PCBKIT_KICAD_SYMBOLS", Path("/usr/share/kicad/symbols")),
    LibraryDir("footprints", "PCBKIT_KICAD_FOOTPRINTS", Path("/usr/share/kicad/footprints")),
    LibraryDir("3dmodels", "PCBKIT_KICAD_3DMODELS", Path("/usr/share/kicad/3dmodels")),
    LibraryDir("templates", "PCBKIT_KICAD_TEMPLATES", Path("/usr/share/kicad/template")),
)

# pcbnew is a system C++ extension, so the interpreter that owns it is found by
# probing candidates rather than by PATH. These literals live here for the same
# reason the library fallbacks do.
PCBNEW_PYTHON_FALLBACKS = ("/usr/bin/python3", "/usr/local/bin/python3")

# Nix ships the bindings in kicad-base's site-packages rather than on any
# interpreter's default path, so the flake names the directory here and
# `kicad.run_pcbnew` puts it on PYTHONPATH for that subprocess only. Setting it
# globally would leak into the uv venv.
PCBNEW_PYTHONPATH_ENV = "PCBKIT_PCBNEW_PYTHONPATH"


def pcbnew_pythonpath() -> str | None:
    return os.environ.get(PCBNEW_PYTHONPATH_ENV) or None

_TOOLS_BY_NAME = {t.name: t for t in TOOLS}
_DIRS_BY_NAME = {d.name: d for d in LIBRARY_DIRS}


def is_pinned() -> bool:
    """True inside the flake devShell, which is what pinning means here."""
    return os.environ.get(TOOLCHAIN_ENV) == "nix"


def _from_env(var: str) -> Path | None:
    value = os.environ.get(var)
    return Path(value) if value else None


def resolve_tool(name: str) -> Resolved:
    """Locate an external program, recording where the answer came from."""
    tool = _TOOLS_BY_NAME.get(name)
    if tool is None:
        raise KeyError(f"unknown tool: {name}")

    override = _from_env(tool.env_var)
    if override is not None:
        # An explicit override wins even inside a flake: it is how a user pins
        # something the flake does not know about.
        source = Source.PINNED if is_pinned() else Source.OVERRIDE
        return Resolved(name, override if override.exists() else None,
                        source if override.exists() else Source.MISSING)

    found = shutil.which(tool.executable)
    if found is None:
        return Resolved(name, None, Source.MISSING)
    # Inside the flake shell PATH is the store, so a PATH hit is a pinned hit.
    return Resolved(name, Path(found), Source.PINNED if is_pinned() else Source.SYSTEM)


def resolve_library(name: str) -> Resolved:
    """Locate a KiCad data directory, recording where the answer came from."""
    entry = _DIRS_BY_NAME.get(name)
    if entry is None:
        raise KeyError(f"unknown library directory: {name}")

    override = _from_env(entry.env_var)
    if override is not None:
        source = Source.PINNED if is_pinned() else Source.OVERRIDE
        return Resolved(name, override if override.is_dir() else None,
                        source if override.is_dir() else Source.MISSING)

    if entry.fallback.is_dir():
        return Resolved(name, entry.fallback, Source.SYSTEM)
    return Resolved(name, None, Source.MISSING)


def summary() -> dict[str, object]:
    """Everything doctor needs to state provenance in one call."""
    tools = {t.name: resolve_tool(t.name) for t in TOOLS}
    libs = {d.name: resolve_library(d.name) for d in LIBRARY_DIRS}
    return {
        "pinned": is_pinned(),
        "tools": {k: v.describe() for k, v in tools.items()},
        "libraries": {k: v.describe() for k, v in libs.items()},
    }
