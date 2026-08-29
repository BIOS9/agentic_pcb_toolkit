"""The pcbkit intermediate representation.

Every layer reads this and nothing else: the parts resolver fills it in, the
emitters render it, the rule engine judges it, and the layout engine positions
it. JSON round-trip is the contract between them, so the IR must stay
serializable and free of behaviour that only exists in memory.

Refdes assignment, symbol/footprint resolution, and placement all happen as
explicit passes *over* this model rather than during capture, so a design can be
inspected between stages.
"""

from __future__ import annotations

import enum
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class PinType(str, enum.Enum):
    """KiCad electrical pin types. ERC and our rule engine both key off these."""

    INPUT = "input"
    OUTPUT = "output"
    BIDIRECTIONAL = "bidirectional"
    TRI_STATE = "tri_state"
    PASSIVE = "passive"
    FREE = "free"
    UNSPECIFIED = "unspecified"
    POWER_IN = "power_in"
    POWER_OUT = "power_out"
    OPEN_COLLECTOR = "open_collector"
    OPEN_EMITTER = "open_emitter"
    NO_CONNECT = "no_connect"


class Pin(BaseModel):
    """One pin of a resolved symbol.

    Populated by the parts resolver (M2); empty during capture, because the DSL
    must not require a library lookup to write a connection down.
    """

    number: str
    name: str = ""
    type: PinType = PinType.PASSIVE

    @field_validator("number", mode="before")
    @classmethod
    def _coerce_number(cls, value: Any) -> str:
        return str(value)


class PinRef(BaseModel):
    """A reference to one pin of one component instance.

    `pin` is whatever the author wrote -- a number ("1") or a symbol pin name
    ("VDD"). It is resolved against the real symbol at build time, which is what
    lets capture stay library-free.
    """

    uid: str = Field(description="Component.uid, stable across passes")
    pin: str

    def __hash__(self) -> int:
        return hash((self.uid, self.pin))


class Component(BaseModel):
    """One placed part.

    `uid` is assigned at capture and never changes; `ref` is assigned by the
    annotation pass. Keeping them separate means re-annotating a design cannot
    silently rewire it.
    """

    uid: str
    prefix: str = Field(default="U", description="refdes prefix, e.g. U, R, C")
    ref: str | None = Field(default=None, description="refdes, assigned by annotate()")
    value: str = ""
    path: tuple[str, ...] = Field(
        default=(), description="module instance path, root first"
    )

    # Sourcing. Any of these may be unset during capture; the resolver fills
    # them in and fails loudly rather than guessing (see AGENTS.md #6).
    part: str | None = Field(default=None, description="requested part, e.g. 'AMS1117-3.3'")
    mpn: str | None = None
    lcsc: str | None = None
    symbol: str | None = Field(default=None, description="'Lib:Name'")
    footprint: str | None = Field(default=None, description="'Lib:Name'")
    model_3d: str | None = None
    package: str | None = Field(default=None, description="requested package, e.g. '0402'")
    datasheet: str | None = None

    pins: list[Pin] = Field(default_factory=list)
    fields: dict[str, str] = Field(default_factory=dict)
    dnp: bool = False
    exclude_from_bom: bool = False

    @property
    def designator(self) -> str:
        """Best available human identifier, for messages before annotation."""
        return self.ref or f"<{self.prefix}:{self.uid[:8]}>"

    def pin_numbers(self) -> set[str]:
        return {p.number for p in self.pins}

    def find_pin(self, key: str) -> Pin | None:
        """Look a pin up by number first, then by name (case-insensitive)."""
        for pin in self.pins:
            if pin.number == key:
                return pin
        lowered = key.lower()
        for pin in self.pins:
            if pin.name.lower() == lowered:
                return pin
        return None


class NetClass(BaseModel):
    """Electrical intent for a net.

    This is the single input to trace width, clearance, routing constraints, and
    several rule checks -- so it is stated once, on the net, rather than
    duplicated into the router and the checker.
    """

    name: str = "Default"
    voltage: float | None = Field(default=None, description="nominal volts")
    max_current_a: float | None = None
    trace_width_mm: float | None = None
    clearance_mm: float | None = None
    impedance_ohm: float | None = Field(
        default=None, description="target single-ended or differential impedance"
    )
    diff_pair: str | None = Field(default=None, description="partner net name")


class NetKind(str, enum.Enum):
    SIGNAL = "signal"
    POWER = "power"
    GROUND = "ground"


class Net(BaseModel):
    name: str
    kind: NetKind = NetKind.SIGNAL
    netclass: NetClass = Field(default_factory=NetClass)
    nodes: list[PinRef] = Field(default_factory=list)
    path: tuple[str, ...] = Field(
        default=(), description="module scope that owns this net"
    )
    global_: bool = Field(
        default=False, alias="global", description="visible across all sheets"
    )

    # Serialize as "global": the alias exists so the IR JSON reads naturally;
    # populate_by_name keeps "global_" accepted on the way back in.
    model_config = {"populate_by_name": True, "serialize_by_alias": True}

    @model_validator(mode="after")
    def _power_and_ground_are_global(self) -> Net:
        # Power rails cross every sheet. Forcing the author to thread them
        # through each module port is the single biggest source of noise in
        # code-defined schematics, so they are global by construction.
        if self.kind in (NetKind.POWER, NetKind.GROUND):
            object.__setattr__(self, "global_", True)
        return self

    def connected(self, uid: str) -> bool:
        return any(node.uid == uid for node in self.nodes)


class Constraint(BaseModel):
    """A designer-stated requirement the rule engine and placer must honour.

    Deliberately open-ended: `kind` selects the checker, `args` carries its
    parameters. New rules add a kind without changing the IR schema.
    """

    kind: str = Field(description="e.g. 'decouple', 'near', 'edge', 'max_length'")
    targets: list[str] = Field(
        default_factory=list, description="component uids or net names"
    )
    args: dict[str, Any] = Field(default_factory=dict)
    path: tuple[str, ...] = ()


class ModuleInfo(BaseModel):
    """One instance of a captured module. Becomes one schematic sheet."""

    name: str
    path: tuple[str, ...]
    ports: list[str] = Field(default_factory=list, description="net names at the boundary")

    @property
    def instance_name(self) -> str:
        return self.path[-1] if self.path else self.name


class Stackup(BaseModel):
    layers: int = 2
    thickness_mm: float = 1.6
    copper_weight_oz: float = 1.0


class Board(BaseModel):
    """Physical board parameters. Consumed by the PCB emitter and the fab layer."""

    width_mm: float | None = None
    height_mm: float | None = None
    corner_radius_mm: float = 1.0
    stackup: Stackup = Field(default_factory=Stackup)
    origin_mm: tuple[float, float] = (100.0, 100.0)


class Design(BaseModel):
    """A complete captured circuit.

    Flat collections keyed by module path rather than a nested tree: emitters,
    the rule engine, and the placer all want to iterate components or nets
    globally far more often than they want to walk a hierarchy, and the path
    field preserves the hierarchy for the ones that do.
    """

    name: str
    components: list[Component] = Field(default_factory=list)
    nets: list[Net] = Field(default_factory=list)
    modules: list[ModuleInfo] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    board: Board = Field(default_factory=Board)
    meta: dict[str, str] = Field(default_factory=dict)

    def component(self, key: str) -> Component | None:
        """Look up by uid or by refdes."""
        for c in self.components:
            if c.uid == key or c.ref == key:
                return c
        return None

    def net(self, name: str) -> Net | None:
        for n in self.nets:
            if n.name == name:
                return n
        return None

    def nets_of(self, uid: str) -> list[Net]:
        return [n for n in self.nets if n.connected(uid)]

    def net_of_pin(self, uid: str, pin: str) -> Net | None:
        for n in self.nets:
            if any(node.uid == uid and node.pin == pin for node in n.nodes):
                return n
        return None

    def in_module(self, path: tuple[str, ...]) -> list[Component]:
        return [c for c in self.components if c.path == path]

    def annotate(self) -> Design:
        """Assign refdes deterministically.

        Sorting by (path, prefix, uid) rather than capture order means an
        unrelated edit elsewhere in the design cannot renumber a whole sheet,
        which keeps schematic and PCB diffs reviewable.
        """
        counters: dict[str, int] = {}
        for component in sorted(
            self.components, key=lambda c: (c.path, c.prefix, c.uid)
        ):
            counters[component.prefix] = counters.get(component.prefix, 0) + 1
            component.ref = f"{component.prefix}{counters[component.prefix]}"
        return self

    def stats(self) -> dict[str, int]:
        return {
            "components": len(self.components),
            "nets": len(self.nets),
            "modules": len(self.modules),
            "constraints": len(self.constraints),
            "pins": sum(len(n.nodes) for n in self.nets),
        }


_REF_RE = re.compile(r"^([A-Za-z_]+)(\d+)$")


def split_ref(ref: str) -> tuple[str, int] | None:
    """Split 'R12' into ('R', 12). Returns None for anything else."""
    match = _REF_RE.match(ref)
    return (match.group(1), int(match.group(2))) if match else None


Direction = Literal["horizontal", "vertical"]
