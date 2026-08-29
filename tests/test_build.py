"""Loading design files and the structural checks that run on every build."""

import json

import pytest

from pcbkit.cli import main
from pcbkit.core.build import build, validate_structure
from pcbkit.core.loader import DesignLoadError, load_design, load_designs

EXAMPLE = "examples/blinky.py"


def test_loads_the_example_design():
    design = load_design(EXAMPLE)
    assert design.name == "blinky"
    assert design.stats()["components"] == 10
    assert {m.name for m in design.modules} == {"power_in", "astable", "indicator"}


def test_missing_file_raises_a_clear_error():
    with pytest.raises(DesignLoadError, match="no such design file"):
        load_design("does/not/exist.py")


def test_import_error_names_the_file(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("raise RuntimeError('nope')\n")
    with pytest.raises(DesignLoadError, match="bad.py: RuntimeError: nope"):
        load_design(bad)


def test_file_with_no_design_is_reported(tmp_path):
    empty = tmp_path / "empty.py"
    empty.write_text("x = 1\n")
    with pytest.raises(DesignLoadError, match="defines no design"):
        load_design(empty)


def test_ambiguous_file_requires_a_choice(tmp_path):
    two = tmp_path / "two.py"
    two.write_text(
        "from pcbkit.dsl import design, R\n"
        "@design('a')\n"
        "def a():\n    R('1k')\n"
        "@design('b')\n"
        "def b():\n    R('2k')\n"
    )
    assert set(load_designs(two)) == {"a", "b"}
    with pytest.raises(DesignLoadError, match="pass --design"):
        load_design(two)
    assert load_design(two, "b").name == "b"


def _broken(tmp_path):
    path = tmp_path / "broken.py"
    path.write_text(
        "from pcbkit.dsl import design, R, C, Power, Gnd, Net\n"
        "@design('broken')\n"
        "def broken():\n"
        "    vcc = Power('+3V3', 3.3)\n"
        "    gnd = Gnd()\n"
        "    R('10k')\n"
        "    C('100nF')[1] >> vcc\n"
        "    Net('NOWHERE')\n"
    )
    return path


def test_structural_checks_catch_authoring_mistakes(tmp_path):
    design = load_design(_broken(tmp_path))
    codes = {f.code for f in validate_structure(design)}
    assert codes == {
        "ir.unconnected_component",
        "ir.single_node_net",
        "ir.empty_net",
    }


def test_every_structural_finding_suggests_a_fix(tmp_path):
    findings = validate_structure(load_design(_broken(tmp_path)))
    assert findings and all(f.fix for f in findings)


def test_a_clean_design_produces_no_findings():
    assert validate_structure(load_design(EXAMPLE)) == []


def test_build_writes_ir_and_findings(tmp_path):
    outdir = tmp_path / "build"
    envelope = build(EXAMPLE, outdir=outdir)
    assert envelope.ok
    ir = json.loads((outdir / "blinky.ir.json").read_text())
    assert ir["name"] == "blinky"
    findings = json.loads((tmp_path / "findings" / "build.json").read_text())
    assert findings["summary"] == {"errors": 0, "warnings": 0}


def test_build_failure_is_a_tool_error_not_a_finding():
    envelope = build("does/not/exist.py")
    assert envelope.ok is False
    assert envelope.errors and not envelope.findings


def test_cli_build_emits_one_json_object(capsys, tmp_path):
    exit_code = main(["build", EXAMPLE, "-o", str(tmp_path)])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["data"]["stats"]["components"] == 10


def test_cli_build_strict_gates_on_errors(capsys, tmp_path):
    broken = str(_broken(tmp_path))
    out = str(tmp_path / "b")
    assert main(["build", broken, "-o", out]) == 0
    capsys.readouterr()
    assert main(["build", broken, "-o", out, "--strict"]) == 1
    capsys.readouterr()


def test_cli_print_ir_inlines_the_design(capsys, tmp_path):
    main(["build", EXAMPLE, "-o", str(tmp_path), "--print-ir"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["data"]["ir"]["name"] == "blinky"
