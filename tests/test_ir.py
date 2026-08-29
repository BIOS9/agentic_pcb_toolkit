"""The IR is the contract between every layer, so pin its guarantees."""

import json

import pytest

from pcbkit.core.loader import load_design
from pcbkit.ir.models import (
    Component,
    Design,
    Net,
    NetKind,
    Pin,
    PinRef,
    PinType,
    split_ref,
)

EXAMPLE = "examples/blinky.py"


def test_json_round_trip_is_identity():
    """Plan verification #1: DSL -> IR -> JSON -> IR must be lossless."""
    design = load_design(EXAMPLE)
    dumped = design.model_dump(mode="json")
    restored = Design.model_validate(json.loads(json.dumps(dumped)))
    assert restored == design
    assert restored.model_dump(mode="json") == dumped


def test_global_flag_serializes_under_its_alias():
    design = load_design(EXAMPLE)
    keys = set(design.model_dump(mode="json")["nets"][0])
    assert "global" in keys and "global_" not in keys
    assert Net.model_validate({"name": "X", "global_": True}).global_ is True


def test_power_and_ground_are_global_by_construction():
    """Rails cross every sheet; threading them through ports is pure noise."""
    assert Net(name="+3V3", kind=NetKind.POWER).global_ is True
    assert Net(name="GND", kind=NetKind.GROUND).global_ is True
    assert Net(name="SDA", kind=NetKind.SIGNAL).global_ is False


def test_annotate_is_deterministic_and_order_independent():
    """Refdes must not depend on capture order, or every diff churns."""
    design = Design(
        name="t",
        components=[
            Component(uid="b", prefix="R", path=("m",)),
            Component(uid="a", prefix="R", path=("m",)),
            Component(uid="c", prefix="C", path=("m",)),
        ],
    )
    reversed_design = Design(
        name="t", components=list(reversed(design.components))
    )
    refs = {c.uid: c.ref for c in design.annotate().components}
    refs_reversed = {c.uid: c.ref for c in reversed_design.annotate().components}
    assert refs == refs_reversed
    assert refs == {"a": "R1", "b": "R2", "c": "C1"}


def test_lookup_helpers():
    design = load_design(EXAMPLE)
    timer = next(c for c in design.components if c.part == "NE555")
    assert design.component(timer.uid) is timer
    assert design.component(timer.ref) is timer
    assert design.component("nope") is None
    assert design.net_of_pin(timer.uid, "VCC").name == "+5V"
    assert {n.name for n in design.nets_of(timer.uid)} >= {"+5V", "GND"}


def test_find_pin_matches_number_then_name():
    component = Component(
        uid="u",
        pins=[
            Pin(number="1", name="VDD", type=PinType.POWER_IN),
            Pin(number="2", name="GND", type=PinType.POWER_IN),
        ],
    )
    assert component.find_pin("1").name == "VDD"
    assert component.find_pin("gnd").number == "2"
    assert component.find_pin("MISSING") is None


def test_pin_number_is_coerced_to_string():
    """Authors write led[1]; KiCad pin numbers are strings like '1' or 'A1'."""
    assert Pin(number=1).number == "1"


def test_designator_is_usable_before_annotation():
    component = Component(uid="root:U1", prefix="U")
    assert component.ref is None
    assert "U" in component.designator


@pytest.mark.parametrize(
    "ref,expected", [("R12", ("R", 12)), ("U1", ("U", 1)), ("GND", None), ("", None)]
)
def test_split_ref(ref, expected):
    assert split_ref(ref) == expected


def test_pinref_is_hashable_for_set_membership():
    assert len({PinRef(uid="a", pin="1"), PinRef(uid="a", pin="1")}) == 1
