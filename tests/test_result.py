"""The CLI output contract is load-bearing for the agent loop, so pin it."""

import json

from pcbkit.core.result import Envelope, Finding, Severity


def test_envelope_json_is_a_single_object_with_summary():
    env = Envelope(command="check")
    payload = json.loads(env.to_json())
    assert payload["ok"] is True
    assert payload["summary"] == {"errors": 0, "warnings": 0}


def test_findings_do_not_make_the_run_fail():
    """A board with violations is a *successful* check run."""
    env = Envelope(
        command="check",
        findings=[
            Finding(source="drc", code="pcb.clearance", severity=Severity.ERROR),
            Finding(source="drc", code="pcb.silk_overlap", severity=Severity.WARNING),
        ],
    )
    assert env.ok is True
    assert env.summary() == {"errors": 1, "warnings": 1}


def test_tool_failure_is_distinct_from_violations():
    env = Envelope(command="build", ok=False, errors=["kicad-cli not found"])
    assert env.ok is False
    assert env.summary() == {"errors": 0, "warnings": 0}


def test_finding_round_trips_through_json():
    finding = Finding(
        source="rules",
        code="rules.undecoupled_power_pin",
        severity=Severity.ERROR,
        message="U1 pin 12 (VDD) has no decoupling capacitor within 5 mm",
        refs=["U1"],
        nets=["+3V3"],
        location_mm=(42.1, 18.0),
        layer="F.Cu",
        fix="add a 100nF 0402 from U1.12 to GND",
    )
    restored = Finding.model_validate(json.loads(finding.model_dump_json()))
    assert restored == finding
    assert restored.location_mm == (42.1, 18.0)


def test_write_findings_creates_parent_directories(tmp_path):
    env = Envelope(
        command="check",
        findings=[Finding(source="erc", code="sch.pin_conflict")],
    )
    target = tmp_path / "findings" / "erc.json"
    env.write_findings(target)
    payload = json.loads(target.read_text())
    assert payload["findings"][0]["code"] == "sch.pin_conflict"
    assert payload["summary"]["errors"] == 1


def test_one_line_prefers_refs_then_nets():
    with_refs = Finding(source="drc", code="c", refs=["R1"], nets=["GND"], message="m")
    with_nets = Finding(source="drc", code="c", nets=["GND"], message="m")
    bare = Finding(source="drc", code="c", message="m")
    assert with_refs.one_line() == "error: c [R1]: m"
    assert with_nets.one_line() == "error: c <GND>: m"
    assert bare.one_line() == "error: c: m"
