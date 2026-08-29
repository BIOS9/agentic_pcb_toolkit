"""Capture: running Python that records a Design instead of executing a circuit.

The DSL is deliberately thin. It records what the author wrote and resolves
nothing -- no symbol lookup, no refdes, no placement. Those are later passes, so
a design can be written and diffed without a KiCad library present, and so a
capture bug is never confused with a resolver bug.
"""

from __future__ import annotations

import threading
from typing import Any, Iterable

from pcbkit.ir.models import (
    Board,
    Component,
    Design,
    Net,
    NetClass,
    NetKind,
    PinRef,
)


class CaptureError(RuntimeError):
    """The DSL was used incorrectly -- a design-time authoring mistake."""


class _Capture:
    """Mutable state for one `@design` evaluation."""

    def __init__(self, name: str, board: Board) -> None:
        self.design = Design(name=name, board=board)
        self.path: list[str] = []
        self._uid_counts: dict[str, int] = {}
        self._instance_counts: dict[str, int] = {}
        self._auto_net = 0

    # -- identity ---------------------------------------------------------
    def next_uid(self, prefix: str) -> str:
        scope = ".".join(self.path) or "root"
        key = f"{scope}:{prefix}"
        self._uid_counts[key] = self._uid_counts.get(key, 0) + 1
        return f"{key}{self._uid_counts[key]}"

    def instance_name(self, base: str) -> str:
        self._instance_counts[base] = self._instance_counts.get(base, 0) + 1
        count = self._instance_counts[base]
        return base if count == 1 else f"{base}_{count}"

    @property
    def scope(self) -> tuple[str, ...]:
        return tuple(self.path)

    # -- nets -------------------------------------------------------------
    def make_net(
        self,
        name: str | None,
        kind: NetKind,
        netclass: NetClass | None,
        is_global: bool,
    ) -> Net:
        if name is None:
            self._auto_net += 1
            name = f"N${self._auto_net:03d}"

        existing = self.design.net(name)
        if existing is not None:
            # A global net is a single rail by definition: reuse it. A local one
            # with the same name in another scope is a different net, so qualify
            # the new one rather than silently shorting two sheets together.
            if existing.global_ and is_global:
                return existing
            if existing.path == self.scope:
                return existing
            name = "/".join(self.scope + (name,))
            if self.design.net(name) is not None:
                return self.design.net(name)  # type: ignore[return-value]

        net = Net(
            name=name,
            kind=kind,
            netclass=netclass or NetClass(),
            path=self.scope,
            **{"global": is_global},
        )
        self.design.nets.append(net)
        return net

    def connect(self, net: Net, ref: PinRef) -> None:
        if ref not in net.nodes:
            net.nodes.append(ref)


_local = threading.local()


def _current() -> _Capture:
    capture = getattr(_local, "capture", None)
    if capture is None:
        raise CaptureError(
            "no design is being captured; put this inside a @design function"
        )
    return capture


def _active() -> _Capture | None:
    return getattr(_local, "capture", None)


# --------------------------------------------------------------------------
# Author-facing handles
# --------------------------------------------------------------------------


class NetHandle:
    """What the author holds when they name a net.

    Thin: the Net lives in the IR, this only carries connection syntax.
    """

    __slots__ = ("_net",)

    def __init__(self, net: Net) -> None:
        self._net = net

    @property
    def net(self) -> Net:
        return self._net

    @property
    def name(self) -> str:
        return self._net.name

    def __rshift__(self, other: "PinHandle | NetHandle") -> "NetHandle":
        _join(self, other)
        return self

    def __rrshift__(self, other: "PinHandle") -> "NetHandle":
        _join(self, other)
        return self

    def __iadd__(self, other: "PinHandle | Iterable[PinHandle]") -> "NetHandle":
        targets = other if isinstance(other, Iterable) else [other]
        for target in targets:  # type: ignore[union-attr]
            _join(self, target)
        return self

    def classify(self, **kwargs: Any) -> "NetHandle":
        """Set net-class attributes: voltage, max_current_a, impedance_ohm, ..."""
        self._net.netclass = self._net.netclass.model_copy(update=kwargs)
        return self

    def __repr__(self) -> str:
        return f"Net({self._net.name!r})"


class PinHandle:
    """One pin of one component, as written by the author."""

    __slots__ = ("_component", "_pin")

    def __init__(self, component: Component, pin: str) -> None:
        self._component = component
        self._pin = pin

    @property
    def ref(self) -> PinRef:
        return PinRef(uid=self._component.uid, pin=self._pin)

    def __rshift__(self, other: "NetHandle | PinHandle") -> "NetHandle":
        if isinstance(other, PinHandle):
            # pin >> pin implies an unnamed net between them
            net = NetHandle(_current().make_net(None, NetKind.SIGNAL, None, False))
            _join(net, self)
            _join(net, other)
            return net
        _join(other, self)
        return other

    def __repr__(self) -> str:
        return f"Pin({self._component.designator}.{self._pin})"


def _join(net: NetHandle, other: PinHandle | NetHandle) -> None:
    if isinstance(other, PinHandle):
        _current().connect(net.net, other.ref)
        return
    if isinstance(other, NetHandle):
        raise CaptureError(
            f"cannot connect net {net.name!r} to net {other.name!r}; "
            "pass one net to both places instead of joining two"
        )
    raise CaptureError(f"cannot connect a net to {type(other).__name__}")


class PartHandle:
    """What the author holds when they place a component."""

    __slots__ = ("_component",)

    def __init__(self, component: Component) -> None:
        object.__setattr__(self, "_component", component)

    @property
    def component(self) -> Component:
        return self._component

    @property
    def uid(self) -> str:
        return self._component.uid

    def __getattr__(self, name: str) -> PinHandle:
        if name.startswith("_"):
            raise AttributeError(name)
        return PinHandle(self._component, name)

    def __getitem__(self, key: str | int) -> PinHandle:
        return PinHandle(self._component, str(key))

    def __call__(self, *nets: NetHandle) -> "PartHandle":
        """Connect pins 1..n positionally.

        Only meaningful for parts whose pin order is unambiguous -- passives,
        two-terminal devices. Guarded so it cannot be used on a part whose pin
        count is known and does not match.
        """
        known = self._component.pins
        if known and len(known) != len(nets):
            raise CaptureError(
                f"{self._component.designator}: positional connect got {len(nets)} "
                f"nets but the part has {len(known)} pins; connect by name instead"
            )
        for index, net in enumerate(nets, start=1):
            if not isinstance(net, NetHandle):
                raise CaptureError(
                    f"{self._component.designator}: positional connect takes nets, "
                    f"got {type(net).__name__}"
                )
            _join(net, PinHandle(self._component, str(index)))
        return self

    def set(self, **fields: str) -> "PartHandle":
        self._component.fields.update({k: str(v) for k, v in fields.items()})
        return self

    def __repr__(self) -> str:
        return f"Part({self._component.designator}, {self._component.part!r})"
