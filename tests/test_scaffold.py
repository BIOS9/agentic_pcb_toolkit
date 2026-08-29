"""`pcbkit new`: a project correct by construction (CR-005, CR-006)."""

from __future__ import annotations

import json
import subprocess
import textwrap
import tomllib
from pathlib import Path

import pytest

from pcbkit import __version__
from pcbkit.cli import main
from pcbkit.core import kicad, scaffold
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
        ".github/workflows/checks.yml",
        ".gitignore",
        "README.md",
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


# CR-008: a board change reaches main only through a reviewed pull request whose
# checks passed. pcbkit cannot enable branch protection on someone else's
# account, so it emits the workflow and documents the settings.


def test_generated_ci_runs_only_verbs_the_cli_actually_has():
    """The defect CR-008 was raised over was a CI step that could not fail. A
    step naming a verb that does not exist is the same failure one stage
    earlier, and it would be discovered by a user, in their CI, not here."""
    import shlex

    from pcbkit.cli import build_parser

    parser = build_parser()
    for label, command in scaffold.CHECK_STEPS:
        argv = shlex.split(command.format(design="src/demo.py"))
        assert argv[0] == "pcbkit", f"{label}: not a pcbkit invocation"
        try:
            parser.parse_args(argv[1:])
        except SystemExit as exc:  # argparse exits rather than raising
            pytest.fail(f"{label}: `{command}` is not a valid pcbkit invocation ({exc})")


def test_generated_ci_gates_rather_than_reports(tmp_path):
    """Every step must be able to fail. `--strict` is what turns pcbkit's
    findings-are-data contract into a gate (AGENTS.md rule 3); a step without it
    has to be one whose nonzero exit means a tool failed."""
    gating = {"--strict", "regenerate"}
    for label, command in scaffold.CHECK_STEPS:
        assert gating & set(command.split()), f"{label}: `{command}` cannot fail"


def test_generated_workflow_supplies_kicad_and_pcbkit(tmp_path):
    """A workflow that runs `pcbkit doctor --strict` on a bare hosted runner
    fails on its first run: KiCad 10 and pcbnew are not installed there."""
    new_project(tmp_path / "demo")
    workflow = (tmp_path / "demo" / ".github" / "workflows" / "checks.yml").read_text()

    assert f"container: {scaffold.KICAD_IMAGE}" in workflow
    assert "pull_request:" in workflow
    for _, command in scaffold.CHECK_STEPS:
        assert command.format(design="src/demo.py") in workflow


def test_generated_ci_pins_pcbkit(tmp_path):
    """CR-004: an unpinned toolchain gives a board whose CI result can change
    without the board changing."""
    new_project(tmp_path / "demo")
    workflow = (tmp_path / "demo" / ".github" / "workflows" / "checks.yml").read_text()
    assert f"@v{__version__}" in workflow
    assert scaffold.KICAD_IMAGE.count(":") == 1, "image tag must be pinned, not latest"
    assert not scaffold.KICAD_IMAGE.endswith(("latest", "nightly"))


def test_generated_workflow_is_valid_yaml(tmp_path):
    """It is a Python f-string producing YAML, which is a shape that breaks
    silently: the file only fails when a user pushes it."""
    import yaml

    new_project(tmp_path / "demo")
    parsed = yaml.safe_load(
        (tmp_path / "demo" / ".github" / "workflows" / "checks.yml").read_text()
    )
    assert set(parsed["jobs"]) == {"checks", "gate"}
    assert parsed["jobs"]["gate"]["needs"] == ["checks"]
    # `edited` is what makes a deferral added to the body take effect.
    # YAML 1.1 reads a bare `on:` key as the boolean true, hence the subscript.
    assert "edited" in parsed[True]["pull_request"]["types"]


def test_the_gate_job_has_exactly_one_definition():
    """This repository's own workflow and every generated one must run the same
    deferral gate. Two copies of a rule are two rules, and the one nobody looks
    at is the one that rots."""
    ours = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "checks.yml").read_text()
    assert scaffold.GATE_JOB in ours, (
        "the gate job in .github/workflows/checks.yml has drifted from "
        "pcbkit.core.scaffold.GATE_JOB"
    )


@pytest.mark.parametrize(
    "body,expected",
    [
        ("deferred: checks\nwhy: layout lands later\nresolves: #42\n", "declared"),
        # CRLF: GitHub delivers pull request bodies with Windows line endings.
        ("prose\r\n\r\ndeferred: checks\r\nwhy: staged\r\nresolves: #42\r\n", "declared"),
        ("deferred: checks\nwhy: staged\nresolves: 42\n", "declared"),
        # Each missing field is a malformed declaration, not an absent one:
        # someone tried to defer and the gate must say why it did not take.
        ("deferred: checks\nresolves: #42\n", "malformed"),
        ("deferred: checks\nwhy:\nresolves: #42\n", "malformed"),
        ("deferred: checks\nwhy: staged\nresolves: later\n", "malformed"),
        ("deferred: checks\nwhy: staged\n", "malformed"),
        # A deferral of some other check does not excuse this one.
        ("deferred: drc\nwhy: staged\nresolves: #42\n", ""),
        ("an ordinary pull request body\n", ""),
        # Indented, so it is prose or a quoted example rather than a declaration.
        ("  deferred: checks\n  why: x\n  resolves: #42\n", ""),
        (
            "deferred: drc\nwhy: a\nresolves: #1\ndeferred: checks\nwhy: b\nresolves: #2\n",
            "declared",
        ),
    ],
)
def test_deferral_parser(body, expected, tmp_path):
    """The gate is a shell script in YAML, which nothing else here can test.
    Extracting its awk program and running it is the only way to know it works
    before it decides whether a real change may merge."""
    import re
    import subprocess

    match = re.search(r"awk -v want=checks '\n(.*?)\n\s*'\)", scaffold.GATE_JOB, re.S)
    assert match, "could not extract the awk program from GATE_JOB"
    program = textwrap.dedent(match.group(1))

    script = tmp_path / "gate.awk"
    script.write_text(program)
    result = subprocess.run(
        ["awk", "-v", "want=checks", "-f", str(script)],
        input=body.replace("\r", ""),
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == expected


def test_readme_names_the_settings_pcbkit_cannot_enable(tmp_path):
    """pcbkit produces the workflow and documents the rest rather than
    pretending it configured the repository."""
    new_project(tmp_path / "demo")
    readme = (tmp_path / "demo" / "README.md").read_text()

    for context in scaffold.REQUIRED_CONTEXTS:
        assert f"`{context}`" in readme
    assert "Require a pull request before merging" in readme
    # The reader must be told the workflow alone blocks nothing.
    assert "does not block" in readme
    # And which of the two contexts nothing in the project produces.
    assert "agent-review` is produced only" in readme
    # The escape hatch has to be documented where someone hitting a red check
    # will look, or they will reach for an admin bypass instead.
    assert "deferred: checks" in readme
    assert "resolves: #42" in readme


def test_generated_project_documents_what_is_not_committed(tmp_path):
    """CR-005. The README and the .gitignore must agree, or one of them is
    teaching the wrong habit."""
    new_project(tmp_path / "demo")
    project = tmp_path / "demo"
    readme = (project / "README.md").read_text()
    ignored = (project / ".gitignore").read_text()

    assert "demo.kicad_dru" in readme
    assert "*.kicad_dru" in ignored
    # The workflow and README are project source, so they must not be ignored.
    assert "README" not in ignored
    assert ".github" not in ignored
