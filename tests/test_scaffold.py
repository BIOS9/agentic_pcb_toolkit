"""`pcbkit new`: a project correct by construction (CR-005, CR-006)."""

from __future__ import annotations

import json
import subprocess
import tomllib
from pathlib import Path

import pytest

from pcbkit.cli import main
from pcbkit.core import kicad
from pcbkit.core.scaffold import (
    check_design_rules,
    new_project,
    read_project,
    regenerate_design_rules,
)


def test_new_project_layout(tmp_path):
    envelope = new_project(tmp_path / "demo")
    assert envelope.ok
    created = set(envelope.data["created"])
    assert created == {
        ".gitignore",
        "demo.kicad_dru",
        "pcbkit.toml",
        "profiles/jlcpcb.yaml",
        "src/demo.py",
    }


def test_gitignore_excludes_every_generated_path(tmp_path):
    """CR-005: the user will not know to do this, and by the time the repo is
    unwieldy the history already contains the artifacts."""
    new_project(tmp_path / "demo")
    ignored = (tmp_path / "demo" / ".gitignore").read_text()
    for path in ("findings/", "release/", "*.kicad_dru"):
        assert path in ignored


def test_profile_is_copied_into_the_project_not_referenced(tmp_path):
    """A board revised in two years must regenerate the same rules."""
    new_project(tmp_path / "demo")
    copied = tmp_path / "demo" / "profiles" / "jlcpcb.yaml"
    assert copied.is_file()
    # Comments carry the provenance, so the copy must keep them.
    assert "PROVENANCE" in copied.read_text()


def test_project_file_records_profile_and_process(tmp_path):
    new_project(tmp_path / "demo", layers=2)
    config = tomllib.loads((tmp_path / "demo" / "pcbkit.toml").read_text())
    assert config["name"] == "demo"
    assert config["fabrication"]["profile"] == "jlcpcb"
    assert config["fabrication"]["process"] == "2layer-1oz"


def test_unencoded_gaps_surface_as_warnings(tmp_path):
    """Creating a project is the moment to learn what DRC will not catch."""
    envelope = new_project(tmp_path / "demo")
    codes = {f.code for f in envelope.findings}
    assert "profile.gap.npth_pad_margin" in codes
    assert envelope.error_count == 0


def test_starter_design_builds(tmp_path):
    from pcbkit.core.build import build

    new_project(tmp_path / "demo")
    envelope = build(tmp_path / "demo" / "src" / "demo.py", outdir=tmp_path / "out")
    assert envelope.ok
    assert envelope.error_count == 0


def test_refuses_a_non_empty_directory(tmp_path):
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "keep.txt").write_text("x")
    envelope = new_project(tmp_path / "demo")
    assert envelope.ok is False
    assert "not empty" in envelope.errors[0]


@pytest.mark.parametrize("name", ["9lives", "my board", "demo/../etc"])
def test_rejects_unusable_names(tmp_path, name):
    envelope = new_project(tmp_path / "d", name=name)
    assert envelope.ok is False


def test_check_reports_current_then_stale_without_overwriting(tmp_path):
    project = tmp_path / "demo"
    new_project(project)
    assert check_design_rules(project).data["state"] == "current"

    dru = project / "demo.kicad_dru"
    edited = dru.read_text() + "\n# hand edit\n"
    dru.write_text(edited)

    envelope = check_design_rules(project)
    assert envelope.data["state"] == "stale"
    assert envelope.error_count == 1
    # The whole point: it reports, it does not silently fix.
    assert dru.read_text() == edited

    regenerate_design_rules(project)
    assert check_design_rules(project).data["state"] == "current"


def test_check_on_a_non_project_is_a_tool_error(tmp_path):
    envelope = check_design_rules(tmp_path)
    assert envelope.ok is False
    assert "not a pcbkit project" in envelope.errors[0]


def test_read_project_raises_clearly(tmp_path):
    from pcbkit.core.scaffold import ScaffoldError

    with pytest.raises(ScaffoldError, match="not a pcbkit project"):
        read_project(tmp_path)


def test_cli_new_and_profile_emit_json(capsys, tmp_path):
    assert main(["new", str(tmp_path / "demo")]) == 0
    assert json.loads(capsys.readouterr().out)["data"]["name"] == "demo"

    assert main(["profile", "gaps"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["data"]["gaps"]

    assert main(["profile", "check", str(tmp_path / "demo")]) == 0
    assert json.loads(capsys.readouterr().out)["data"]["state"] == "current"


@pytest.mark.skipif(
    kicad.pcbnew_python() is None or kicad.which("kicad-cli") is None,
    reason="needs KiCad",
)
def test_generated_rules_are_enforced_by_real_kicad(tmp_path):
    """End to end: profile YAML -> .kicad_dru -> KiCad DRC actually rejecting a board.

    A rules file that parses but never fires would be worse than none, since a
    clean DRC would then mean nothing.
    """
    project = tmp_path / "demo"
    new_project(project)
    board = project / "demo.kicad_pcb"
    limit = 0.127  # the profile's outer minimum; the track below is thinner

    script = f"""
import pcbnew
mm = pcbnew.FromMM
b = pcbnew.NewBoard({str(board)!r})
pts = [(100,100),(140,100),(140,130),(100,130),(100,100)]
for (x1,y1),(x2,y2) in zip(pts, pts[1:]):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1)))
    s.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
    s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1)); b.Add(s)
t = pcbnew.PCB_TRACK(b)
t.SetStart(pcbnew.VECTOR2I(mm(110), mm(110)))
t.SetEnd(pcbnew.VECTOR2I(mm(130), mm(110)))
t.SetWidth(mm(0.10)); t.SetLayer(pcbnew.F_Cu); b.Add(t)
pcbnew.SaveBoard({str(board)!r}, b)
"""
    assert kicad.run_pcbnew(script).ok

    report = tmp_path / "drc.json"
    result = kicad.run(
        [kicad.which("kicad-cli"), "pcb", "drc", "--format", "json",
         "-o", str(report), str(board)]
    )
    assert result.ok, result.stderr

    violations = json.loads(report.read_text())["violations"]
    widths = [v for v in violations if v["type"] == "track_width"]
    assert widths, f"generated rules did not fire: {[v['type'] for v in violations]}"
    # KiCad names our rule, which proves the rules file is the source.
    assert "Track width, outer layer" in widths[0]["description"]
    assert f"{limit:.4f}" in widths[0]["description"]
