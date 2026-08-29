"""Capture semantics. These are the behaviours a design author relies on."""

import pytest

from pcbkit.dsl import (
    C,
    CaptureError,
    Gnd,
    LED,
    Net,
    Part,
    Power,
    R,
    design,
    module,
    rule,
)
from pcbkit.ir.models import NetKind


def test_captures_hierarchy_rails_and_constraints():
    @module
    def power_3v3(vin, v3v3, gnd):
        u = Part("AMS1117-3.3", lcsc="C6186")
        cin, cout = C("10uF", pkg="0805"), C("22uF", pkg="0805")
        vin >> u.VI
        u.VO >> v3v3
        u.GND >> gnd
        cin(vin, gnd)
        cout(v3v3, gnd)
        rule.decouple(u, max_mm=5)

    @design("d", width_mm=40, height_mm=25)
    def d():
        power_3v3(Power("VBUS", 5.0), Power("+3V3", 3.3), Gnd())

    assert d.stats() == {
        "components": 3,
        "nets": 3,
        "modules": 1,
        "constraints": 1,
        "pins": 7,
    }
    assert d.board.width_mm == 40
    assert [c.path for c in d.components] == [("power_3v3",)] * 3
    assert d.modules[0].ports == ["VBUS", "+3V3", "GND"]
    assert d.constraints[0].kind == "decouple"
    assert d.constraints[0].args == {"max_mm": 5}
    regulator = d.component("U1")
    assert regulator.lcsc == "C6186"
    assert d.net_of_pin(regulator.uid, "VI").name == "VBUS"


def test_rails_are_shared_across_module_instances():
    """Two instances of a block must land on one rail, not two."""

    @module
    def load(v, gnd):
        R("1k")(v, gnd)

    @design("d")
    def d():
        v, gnd = Power("+3V3", 3.3), Gnd()
        load(v, gnd)
        load(v, gnd)

    assert [n.name for n in d.nets] == ["+3V3", "GND"]
    assert len(d.net("+3V3").nodes) == 2
    assert [m.path for m in d.modules] == [("load",), ("load_2",)]


def test_same_local_net_name_in_two_modules_stays_separate():
    """Reusing a block must not short its internals together."""

    @module
    def stage(out):
        mid = Net("MID")
        R("1k")(mid, out)

    @design("d")
    def d():
        out = Power("+3V3", 3.3)
        stage(out)
        stage(out)

    local = [n.name for n in d.nets if n.kind is NetKind.SIGNAL]
    assert len(local) == 2 and len(set(local)) == 2
    assert "stage_2/MID" in local


def test_pin_to_pin_creates_an_implicit_net():
    @design("d")
    def d():
        a, b = R("1k"), LED("red")
        a[2] >> b[1]

    implicit = [n for n in d.nets if n.name.startswith("N$")]
    assert len(implicit) == 1
    assert len(implicit[0].nodes) == 2


def test_positional_connect_is_guarded_by_pin_count():
    with pytest.raises(CaptureError, match="positional connect"):

        @design("d")
        def d():
            gnd = Gnd()
            C("1uF")(gnd)  # a two-terminal part given one net


def test_positional_connect_rejects_non_nets():
    with pytest.raises(CaptureError, match="takes nets"):

        @design("d")
        def d():
            gnd = Gnd()
            C("1uF")(gnd, "GND")


def test_joining_two_nets_is_refused():
    """Silently merging nets would hide a wiring mistake."""
    with pytest.raises(CaptureError, match="pass one net to both"):

        @design("d")
        def d():
            Power("A", 5.0) >> Power("B", 3.3)


def test_dsl_outside_a_design_fails_clearly():
    with pytest.raises(CaptureError, match="no design is being captured"):
        R("1k")


def test_designs_cannot_nest():
    with pytest.raises(CaptureError, match="cannot be nested"):

        @design("outer")
        def outer():
            @design("inner")
            def inner():
                R("1k")


def test_capture_state_is_released_after_a_failed_design():
    """A raising design file must not poison the next capture."""
    with pytest.raises(ValueError):

        @design("boom")
        def boom():
            raise ValueError("kaboom")

    @design("fine")
    def fine():
        R("1k")

    assert fine.stats()["components"] == 1


def test_rule_current_and_diff_pair_write_through_to_the_netclass():
    """Constraints that are also electrical intent belong on the net."""

    @design("d")
    def d():
        vbus = Power("VBUS", 5.0)
        dp, dm = Net("D+"), Net("D-")
        rule.current(vbus, amps=3.0)
        rule.diff_pair(dp, dm, impedance_ohm=90.0)

    assert d.net("VBUS").netclass.max_current_a == 3.0
    assert d.net("D+").netclass.diff_pair == "D-"
    assert d.net("D-").netclass.impedance_ohm == 90.0


def test_bare_design_decorator_uses_the_function_name():
    @design
    def widget():
        R("1k")

    assert widget.name == "widget"


def test_part_fields_and_set():
    @design("d")
    def d():
        Part("STM32F103", prefix="U", Tolerance="1%").set(Note="hand-solder")

    component = d.component("U1")
    assert component.fields == {"Tolerance": "1%", "Note": "hand-solder"}


def test_uids_are_stable_across_identical_captures():
    def make():
        @design("d")
        def d():
            R("1k")
            C("1uF")

        return d

    assert [c.uid for c in make().components] == [c.uid for c in make().components]
