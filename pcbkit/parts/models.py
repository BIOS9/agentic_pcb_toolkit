"""What a resolved part is.

CR-007 makes an assembled JLCPCB order the default target, which changes what
counts as valid: a part must be in the assembler's library, in stock with
margin, and its basic/extended class is a first-class cost input rather than
something discovered at checkout.
"""

from __future__ import annotations

import datetime as _dt
import enum

from pydantic import BaseModel, Field


class Classification(str, enum.Enum):
    """JLCPCB assembly class. Extended parts carry a per-part setup fee that
    dominates cost at low volume, so this drives selection, not just reporting."""

    BASIC = "basic"
    EXTENDED = "extended"
    UNKNOWN = "unknown"

    @classmethod
    def parse(cls, text: str | None) -> "Classification":
        if not text:
            return cls.UNKNOWN
        lowered = text.lower()
        if "basic" in lowered:
            return cls.BASIC
        if "extended" in lowered or "expand" in lowered:
            return cls.EXTENDED
        return cls.UNKNOWN


class Sourcing(BaseModel):
    """Availability and cost for one orderable part.

    `fetched` is mandatory: stock and price are perishable, and a cached figure
    with no date cannot be judged. CR-003 requires builds to work offline from
    this cache, so knowing how stale it is matters more than it would if the
    network were always consulted.
    """

    lcsc: str
    mpn: str = ""
    manufacturer: str = ""
    package: str = ""
    description: str = ""

    price: float | None = Field(default=None, description="unit price at min qty")
    stock: int = 0
    min_qty: int = 1
    step_qty: int = 1
    classification: Classification = Classification.UNKNOWN
    assembly: bool = Field(default=False, description="offered for SMT assembly")

    fetched: _dt.date
    source: str = "easyeda"

    def stock_ok(self, quantity: int, *, margin: int = 10, floor: int = 500) -> bool:
        """A part that only just covers the build will be gone by order time."""
        return self.stock >= max(quantity * margin, floor)

    def age_days(self, today: _dt.date | None = None) -> int:
        return ((today or _dt.date.today()) - self.fetched).days


class Candidate(BaseModel):
    """A part that could satisfy a request, with the reasoning for its rank.

    The ranking is reported rather than applied silently: a substitution that
    changes cost or availability without saying so is what AGENTS.md rule 6
    forbids.
    """

    sourcing: Sourcing
    symbol: str | None = None
    footprint: str | None = None
    model_3d: str | None = None

    score: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)

    @property
    def complete(self) -> bool:
        """Anything less is a board that fails at assembly (AGENTS.md rule 6)."""
        return bool(self.symbol and self.footprint and self.sourcing.lcsc)

    def summary(self) -> str:
        s = self.sourcing
        price = f"${s.price:.4f}" if s.price is not None else "price unknown"
        return (
            f"{s.lcsc} {s.mpn or '?'} [{s.classification.value}] "
            f"stock {s.stock:,} {price}"
        )


class PartRequest(BaseModel):
    """What the design asked for, before anything is resolved."""

    uid: str = ""
    ref: str = ""
    part: str | None = None
    value: str = ""
    lcsc: str | None = None
    mpn: str | None = None
    package: str | None = None
    quantity: int = Field(default=5, description="board build quantity")

    def describe(self) -> str:
        bits = [b for b in (self.ref or None, self.part, self.value, self.package) if b]
        return " ".join(bits) or self.lcsc or "<unspecified part>"
