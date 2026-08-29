"""The pcbkit circuit DSL.

```python
from pcbkit.dsl import design, module, Part, C, Power, Gnd, rule

@module
def power_3v3(vin, v3v3, gnd):
    u = Part("AMS1117-3.3", lcsc="C6186")
    cin, cout = C("10uF", pkg="0805"), C("22uF", pkg="0805")
    vin >> u.VI; u.VO >> v3v3; u.GND >> gnd
    cin(vin, gnd); cout(v3v3, gnd)
    rule.decouple(u, max_mm=5)

@design("devboard", width_mm=40, height_mm=25)
def top():
    vbus, v3v3, gnd = Power("VBUS", 5.0), Power("+3V3", 3.3), Gnd()
    power_3v3(vbus, v3v3, gnd)
```
"""

from __future__ import annotations

import functools
from typing import Any, Callable

from pcbkit.dsl.capture import (
    CaptureError,
    NetHandle,
    PartHandle,
    PinHandle,
    _active,
    _current,
    _local,
    _Capture,
)
from pcbkit.ir.models import (
    Board,
    Component,
    Constraint,
    Design,
    ModuleInfo,
    NetClass,
    NetKind,
    Pin,
    PinType,
    Stackup,
)

__all__ = [
    "design",
    "module",
    "Net",
    "Power",
    "Gnd",
    "Part",
    "R",
    "C",
    "L",
    "D",
    "LED",
    "Q",
    "SW",
    "J",
    "TP",
    "rule",
    "CaptureError",
    "NetHandle",
    "PartHandle",
    "PinHandle",
]


# --------------------------------------------------------------------------
# Nets
# --------------------------------------------------------------------------


def Net(name: str | None = None, **netclass: Any) -> NetHandle:
    """A local signal net. Unnamed nets get a generated `N$nnn` name."""
    nc = NetClass(**netclass) if netclass else None
    return NetHandle(_current().make_net(name, NetKind.SIGNAL, nc, False))


def Power(name: str, voltage: float | None = None, **netclass: Any) -> NetHandle:
    """A power rail. Global across every sheet -- see Net._power_and_ground_are_global."""
    nc = NetClass(name=name, voltage=voltage, **netclass)
    return NetHandle(_current().make_net(name, NetKind.POWER, nc, True))


def Gnd(name: str = "GND", **netclass: Any) -> NetHandle:
    """The ground reference. Global, and voltage 0 by definition."""
    nc = NetClass(name=name, voltage=0.0, **netclass)
    return NetHandle(_current().make_net(name, NetKind.GROUND, nc, True))


# --------------------------------------------------------------------------
# Components
# --------------------------------------------------------------------------

_TWO_TERMINAL = [
    Pin(number="1", name="1", type=PinType.PASSIVE),
    Pin(number="2", name="2", type=PinType.PASSIVE),
]


def Part(
    part: str | None = None,
    *,
    value: str = "",
    prefix: str = "U",
    symbol: str | None = None,
    footprint: str | None = None,
    lcsc: str | None = None,
    mpn: str | None = None,
    pkg: str | None = None,
    dnp: bool = False,
    pins: list[Pin] | None = None,
    **fields: str,
) -> PartHandle:
    """Place a component.

    Nothing is resolved here: `part`, `lcsc`, and `mpn` are *requests* that the
    parts resolver (M2) turns into a symbol, footprint, and 3D model, or fails
    on. Capture deliberately works with no KiCad library present.
    """
    capture = _current()
    component = Component(
        uid=capture.next_uid(prefix),
        prefix=prefix,
        value=value or (part or ""),
        path=capture.scope,
        part=part,
        symbol=symbol,
        footprint=footprint,
        lcsc=lcsc,
        mpn=mpn,
        package=pkg,
        dnp=dnp,
        pins=list(pins) if pins else [],
        fields={k: str(v) for k, v in fields.items()},
    )
    capture.design.components.append(component)
    return PartHandle(component)


def _passive(prefix: str, part: str) -> Callable[..., PartHandle]:
    """Build a two-terminal helper: R('10k'), C('100nF', pkg='0402'), ..."""

    def factory(value: str = "", **kwargs: Any) -> PartHandle:
        kwargs.setdefault("pins", list(_TWO_TERMINAL))
        return Part(part, value=value, prefix=prefix, **kwargs)

    factory.__name__ = prefix
    factory.__doc__ = f"A {part}. Pins 1 and 2, so positional connect works."
    return factory


R = _passive("R", "R")
C = _passive("C", "C")
L = _passive("L", "L")
D = _passive("D", "D")
LED = _passive("D", "LED")
TP = _passive("TP", "TestPoint")


def Q(part: str | None = None, **kwargs: Any) -> PartHandle:
    """A transistor. Pin order is package-dependent, so connect by name."""
    return Part(part, prefix="Q", **kwargs)


def SW(part: str | None = None, **kwargs: Any) -> PartHandle:
    return Part(part, prefix="SW", **kwargs)


def J(part: str | None = None, **kwargs: Any) -> PartHandle:
    return Part(part, prefix="J", **kwargs)


# --------------------------------------------------------------------------
# Constraints
# --------------------------------------------------------------------------


def _target(item: Any) -> str:
    if isinstance(item, PartHandle):
        return item.uid
    if isinstance(item, NetHandle):
        return item.name
    if isinstance(item, str):
        return item
    raise CaptureError(f"constraint target must be a part, net, or name; got {item!r}")


class _Rules:
    """`rule.<kind>(...)` records intent for the rule engine and the placer.

    Recording rather than checking: capture must not need a resolved library or
    a placed board, and the same constraint often drives both a check and a
    placement decision.
    """

    def _add(self, kind: str, targets: list[Any], **args: Any) -> Constraint:
        capture = _current()
        constraint = Constraint(
            kind=kind,
            targets=[_target(t) for t in targets],
            args=args,
            path=capture.scope,
        )
        capture.design.constraints.append(constraint)
        return constraint

    def decouple(self, part: Any, max_mm: float = 5.0, **args: Any) -> Constraint:
        """Every power pin of `part` needs a bypass cap within `max_mm`."""
        return self._add("decouple", [part], max_mm=max_mm, **args)

    def near(self, a: Any, b: Any, max_mm: float = 5.0) -> Constraint:
        return self._add("near", [a, b], max_mm=max_mm)

    def edge(self, part: Any, side: str = "any", **args: Any) -> Constraint:
        """Pin a connector to a board edge."""
        return self._add("edge", [part], side=side, **args)

    def max_length(self, net: Any, mm: float) -> Constraint:
        return self._add("max_length", [net], mm=mm)

    def diff_pair(self, a: Any, b: Any, impedance_ohm: float = 90.0) -> Constraint:
        if isinstance(a, NetHandle) and isinstance(b, NetHandle):
            a.classify(diff_pair=b.name, impedance_ohm=impedance_ohm)
            b.classify(diff_pair=a.name, impedance_ohm=impedance_ohm)
        return self._add("diff_pair", [a, b], impedance_ohm=impedance_ohm)

    def current(self, net: Any, amps: float) -> Constraint:
        """State a net's worst-case current so trace width can be checked."""
        if isinstance(net, NetHandle):
            net.classify(max_current_a=amps)
        return self._add("current", [net], amps=amps)

    def custom(self, kind: str, *targets: Any, **args: Any) -> Constraint:
        return self._add(kind, list(targets), **args)


rule = _Rules()


# --------------------------------------------------------------------------
# Structure
# --------------------------------------------------------------------------


def module(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Mark a function as a reusable circuit block.

    Each call becomes one instance -- one schematic sheet, and one placement
    cluster on the board. Net arguments become the sheet's hierarchical ports.
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        capture = _current()
        instance = capture.instance_name(fn.__name__)
        capture.path.append(instance)
        try:
            ports = [
                a.name
                for a in list(args) + list(kwargs.values())
                if isinstance(a, NetHandle)
            ]
            capture.design.modules.append(
                ModuleInfo(name=fn.__name__, path=capture.scope, ports=ports)
            )
            return fn(*args, **kwargs)
        finally:
            capture.path.pop()

    wrapper.__pcbkit_module__ = True  # type: ignore[attr-defined]
    return wrapper


def design(
    name: str | Callable[..., Any] | None = None,
    *,
    width_mm: float | None = None,
    height_mm: float | None = None,
    layers: int = 2,
    thickness_mm: float = 1.6,
    **meta: str,
) -> Any:
    """Capture a design. Decorating runs the function immediately.

    The decorated name is rebound to the finished `Design`, so a design file is
    just a module with `Design` objects in it and the loader needs no registry.
    """

    def build(fn: Callable[..., Any], design_name: str) -> Design:
        if _active() is not None:
            raise CaptureError(
                "@design cannot be nested; use @module for reusable blocks"
            )
        board = Board(
            width_mm=width_mm,
            height_mm=height_mm,
            stackup=Stackup(layers=layers, thickness_mm=thickness_mm),
        )
        capture = _Capture(design_name, board)
        _local.capture = capture
        try:
            fn()
        finally:
            _local.capture = None
        result = capture.design
        result.meta.update({k: str(v) for k, v in meta.items()})
        return result.annotate()

    if callable(name):  # bare @design
        return build(name, name.__name__)

    def decorator(fn: Callable[..., Any]) -> Design:
        return build(fn, name or fn.__name__)

    return decorator
