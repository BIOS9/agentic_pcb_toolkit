"""M2: every external path resolves in one place, and says where it came from."""

from __future__ import annotations

from pathlib import Path

import pytest

from pcbkit.core import toolchain

REPO = Path(__file__).resolve().parent.parent
PACKAGE = REPO / "pcbkit"


def test_system_paths_are_confined_to_the_fallback_table():
    """CR-004: a hardcoded /usr path is how output becomes machine-dependent.

    They are permitted only in toolchain.py, which is the documented fallback
    for users without Nix.
    """
    offenders = []
    for path in PACKAGE.rglob("*.py"):
        if path.name == "toolchain.py" or "__pycache__" in path.parts:
            continue
        for n, line in enumerate(path.read_text().splitlines(), start=1):
            if "/usr/" in line:
                offenders.append(f"{path.relative_to(REPO)}:{n}: {line.strip()}")
    assert not offenders, "system paths outside toolchain.py:\n" + "\n".join(offenders)


def test_override_wins_over_system(monkeypatch, tmp_path):
    monkeypatch.setenv("PCBKIT_KICAD_SYMBOLS", str(tmp_path))
    monkeypatch.delenv(toolchain.TOOLCHAIN_ENV, raising=False)
    resolved = toolchain.resolve_library("symbols")
    assert resolved.path == tmp_path
    assert resolved.source is toolchain.Source.OVERRIDE


def test_override_pointing_nowhere_is_missing_not_silently_ignored(monkeypatch):
    """Falling back on a bad override would hide the user's mistake."""
    monkeypatch.setenv("PCBKIT_KICAD_SYMBOLS", "/nonexistent/symbols")
    resolved = toolchain.resolve_library("symbols")
    assert resolved.path is None
    assert resolved.source is toolchain.Source.MISSING


def test_flake_environment_marks_resolution_as_pinned(monkeypatch, tmp_path):
    monkeypatch.setenv(toolchain.TOOLCHAIN_ENV, "nix")
    monkeypatch.setenv("PCBKIT_KICAD_SYMBOLS", str(tmp_path))
    assert toolchain.is_pinned() is True
    assert toolchain.resolve_library("symbols").source is toolchain.Source.PINNED


def test_path_hits_are_system_when_unpinned(monkeypatch):
    monkeypatch.delenv(toolchain.TOOLCHAIN_ENV, raising=False)
    monkeypatch.delenv("PCBKIT_KICAD_CLI", raising=False)
    resolved = toolchain.resolve_tool("kicad-cli")
    if not resolved.found:
        pytest.skip("no kicad-cli on this machine")
    assert resolved.source is toolchain.Source.SYSTEM


def test_missing_tool_is_reported_not_raised(monkeypatch):
    monkeypatch.setenv("PCBKIT_NGSPICE", "/nonexistent/ngspice")
    resolved = toolchain.resolve_tool("ngspice")
    assert not resolved.found
    assert "not found" in resolved.describe()


def test_unknown_names_raise_rather_than_returning_missing():
    """A typo in a tool name is a bug, not an absent tool."""
    with pytest.raises(KeyError):
        toolchain.resolve_tool("kicadcli")
    with pytest.raises(KeyError):
        toolchain.resolve_library("symbol")


def test_summary_covers_every_declared_tool_and_library():
    summary = toolchain.summary()
    assert set(summary["tools"]) == {t.name for t in toolchain.TOOLS}
    assert set(summary["libraries"]) == {d.name for d in toolchain.LIBRARY_DIRS}


def test_kicad_module_delegates_rather_than_hardcoding():
    from pcbkit.core import kicad

    assert kicad.library_dir("symbols") == toolchain.resolve_library("symbols").path
    assert not hasattr(kicad, "DEFAULT_SYMBOL_DIR")
