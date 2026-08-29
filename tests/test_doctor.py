"""Doctor exists so later milestones fail loudly and early, not deep and opaque."""

import json

import pytest

from pcbkit.cli import main
from pcbkit.core import env, toolchain


@pytest.fixture
def broken_env(monkeypatch):
    """An environment with no external tools at all.

    Patches the resolver rather than `kicad.which`: since M2 that is the seam
    every lookup goes through, and patching the old one left this exercising
    "version unparseable" instead of "tool missing".
    """
    missing = lambda name: toolchain.Resolved(name, None, toolchain.Source.MISSING)
    monkeypatch.setattr(env.toolchain, "resolve_tool", missing)
    monkeypatch.setattr(env.toolchain, "resolve_library", missing)
    monkeypatch.setattr(env.kicad, "pcbnew_python", lambda: None)


def test_doctor_reports_every_check():
    envelope = env.doctor()
    ids = {c["id"] for c in envelope.data["checks"]}
    assert {"python", "kicad-cli", "pcbnew", "symbols", "footprints"} <= ids


def test_doctor_envelope_is_ok_even_when_environment_is_broken(broken_env):
    """A broken environment is a finding, not a crashed tool."""
    envelope = env.doctor()
    assert envelope.ok is True
    assert envelope.data["healthy"] is False
    assert any(f.code == "env.kicad-cli" for f in envelope.findings)
    kicad_check = next(c for c in envelope.data["checks"] if c["id"] == "kicad-cli")
    assert kicad_check["detail"] == "not found"


def test_every_failing_check_carries_a_remedy(broken_env):
    envelope = env.doctor()
    assert envelope.findings
    assert all(f.fix for f in envelope.findings)


def test_format_drift_is_a_warning_not_a_failure(monkeypatch):
    """A KiCad upgrade should flag loudly but not block the whole toolkit."""
    monkeypatch.setitem(env.kicad.FORMAT_VERSIONS, "kicad_pcb", 19700101)
    if env.kicad.pcbnew_python() is None:
        return
    check = env.check_pcb_format()
    assert check.status is env.Status.WARN
    assert "19700101" in check.detail


def test_cli_doctor_emits_one_json_object(capsys):
    exit_code = main(["doctor"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["command"] == "doctor"
    assert "checks" in payload["data"]


def test_cli_strict_gates_on_health(capsys, broken_env):
    assert main(["doctor", "--strict"]) == 1
    capsys.readouterr()
    assert main(["doctor"]) == 0


def test_doctor_reports_toolchain_provenance():
    """CR-004: an unpinned environment works, but must say so."""
    envelope = env.doctor()
    assert "pinned" in envelope.data
    assert envelope.data["toolchain"]["tools"]
    check = next(c for c in envelope.data["checks"] if c["id"] == "toolchain")
    assert check["status"] in ("ok", "warn")


def test_require_pinned_gates_separately_from_health(capsys, monkeypatch):
    """--require-pinned is about reproducibility, not whether tools work."""
    monkeypatch.setattr(env.toolchain, "is_pinned", lambda: False)
    assert main(["doctor", "--require-pinned"]) == 1
    capsys.readouterr()
    monkeypatch.setattr(env.toolchain, "is_pinned", lambda: True)
    assert main(["doctor", "--require-pinned"]) == 0
    capsys.readouterr()
