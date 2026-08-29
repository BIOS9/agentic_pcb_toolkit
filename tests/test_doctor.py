"""Doctor exists so later milestones fail loudly and early, not deep and opaque."""

import json

from pcbkit.cli import main
from pcbkit.core import env


def test_doctor_reports_every_check():
    envelope = env.doctor()
    ids = {c["id"] for c in envelope.data["checks"]}
    assert {"python", "kicad-cli", "pcbnew", "symbols", "footprints"} <= ids


def test_doctor_envelope_is_ok_even_when_environment_is_broken(monkeypatch):
    """A broken environment is a finding, not a crashed tool."""
    monkeypatch.setattr(env.kicad, "which", lambda name: None)
    monkeypatch.setattr(env.kicad, "pcbnew_python", lambda: None)
    envelope = env.doctor()
    assert envelope.ok is True
    assert envelope.data["healthy"] is False
    assert any(f.code == "env.kicad-cli" for f in envelope.findings)


def test_every_failing_check_carries_a_remedy(monkeypatch):
    monkeypatch.setattr(env.kicad, "which", lambda name: None)
    monkeypatch.setattr(env.kicad, "pcbnew_python", lambda: None)
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


def test_cli_strict_gates_on_health(capsys, monkeypatch):
    monkeypatch.setattr(env.kicad, "which", lambda name: None)
    monkeypatch.setattr(env.kicad, "pcbnew_python", lambda: None)
    assert main(["doctor", "--strict"]) == 1
    capsys.readouterr()
    assert main(["doctor"]) == 0
