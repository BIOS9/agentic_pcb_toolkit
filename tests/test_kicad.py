"""Interop helpers. These touch the real toolchain where that is the point."""

import pytest

from pcbkit.core import kicad


def test_format_versions_are_pinned():
    """Emitters target these exactly; `pcbkit doctor` warns when KiCad drifts."""
    assert kicad.FORMAT_VERSIONS["kicad_pcb"] == 20260206
    assert kicad.FORMAT_VERSIONS["kicad_sch"] == 20260306


def test_kicad10_copper_layer_ids():
    """KiCad 10 renumbered copper: B.Cu is 2, not the pre-10 value of 31."""
    assert (kicad.F_CU, kicad.B_CU) == (0, 2)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("10.0.5", (10, 0, 5)),
        ("10.0.5-1-g226df246f3", (10, 0, 5)),
        ("KiCad version 9.0.1", (9, 0, 1)),
        ("no version here", None),
        ("", None),
    ],
)
def test_parse_version(text, expected):
    assert kicad.parse_version(text) == expected


def test_run_reports_exit_code_not_stderr():
    """The stderr rule: writing to stderr is not failure."""
    result = kicad.run(["sh", "-c", "echo oops >&2; exit 0"])
    assert result.ok
    assert "oops" in result.stderr


def test_run_check_raises_on_nonzero():
    with pytest.raises(kicad.KicadError):
        kicad.run(["sh", "-c", "exit 3"], check=True)


def test_run_missing_executable_raises_kicad_error():
    with pytest.raises(kicad.KicadError, match="not found"):
        kicad.run(["pcbkit-no-such-binary-xyz"])


def test_pcbnew_resolves_to_an_interpreter_outside_this_venv():
    """pcbnew is a system C extension; a plain venv cannot import it."""
    interpreter = kicad.pcbnew_python()
    if interpreter is None:
        pytest.skip("no pcbnew on this machine")
    assert kicad.pcbnew_version().startswith("10.")


def test_run_pcbnew_executes_in_that_interpreter():
    if kicad.pcbnew_python() is None:
        pytest.skip("no pcbnew on this machine")
    result = kicad.run_pcbnew("import pcbnew; print(pcbnew.GetBuildVersion())")
    assert result.ok
    # stderr carries the benign PROPERTY_ENUM asserts; stdout carries the answer
    assert "10." in result.stdout
