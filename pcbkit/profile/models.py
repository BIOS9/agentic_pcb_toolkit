"""Fabricator capability profiles.

Every manufacturing limit pcbkit knows about lives in a profile file, never in
Python. See AGENTS.md rule 10: limits differ per fabricator, per layer count,
and per copper weight, and they change — a constant in an emitter is a board
that gets built wrong.

Profiles also record what they *do not* cover. The rule set this model was
derived from lost three real limits to TODO comments, which is the failure
CR-006 exists to prevent.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class LayerPair(BaseModel):
    """A limit that differs between outer and inner copper."""

    outer: float
    inner: float

    def for_layer(self, layer: Literal["outer", "inner"]) -> float:
        return self.outer if layer == "outer" else self.inner


class Range(BaseModel):
    min: float
    max: float


class HoleToHole(BaseModel):
    different_nets: float
    same_net: float


class SlotWidth(BaseModel):
    plated: float
    unplated: float


class BoardSize(BaseModel):
    x: float
    y: float


class Limits(BaseModel):
    """One process's manufacturing limits, all in millimetres.

    Extra keys are rejected: a profile with a typo'd limit name would otherwise
    silently contribute nothing, and a rule that never fires looks identical to
    a rule that always passes.
    """

    model_config = {"extra": "forbid"}

    track_width_mm: LayerPair
    track_spacing_mm: LayerPair

    hole_diameter_mm: Range
    npth_hole_min_mm: float
    castellated_hole_min_mm: float
    annular_ring_min_mm: float
    hole_to_hole_mm: HoleToHole

    track_to_npth_mm: float
    track_to_pth_mm: float
    track_to_pad_mm: float
    pad_to_pad_mm: float
    edge_clearance_mm: float
    edge_clearance_vcut_mm: float

    silk_thickness_min_mm: float
    silk_height_min_mm: float
    pad_to_silk_mm: float

    slot_width_mm: SlotWidth
    board_min_size_mm: BoardSize


class Process(BaseModel):
    """A specific stackup the fabricator offers. Limits hang off this, not off
    the vendor, because outer and inner copper already disagree at two layers."""

    id: str
    description: str = ""
    layers: int
    copper_oz: float
    limits: Limits


class Gap(BaseModel):
    """A limit known to exist that this profile does not encode.

    `encoded: partial` means something is expressed but not faithfully — a
    vendor ambiguity resolved one way, for instance. Tracking that is the point:
    an unstated omission is indistinguishable from full coverage.
    """

    id: str
    why: str
    encoded: bool | Literal["partial"] = False


class Profile(BaseModel):
    vendor: str
    source: str = Field(description="vendor capabilities URL")
    retrieved: _dt.date = Field(description="when this profile was written, not when the vendor last changed")
    derived_from: str = ""
    processes: list[Process]
    gaps: list[Gap] = Field(default_factory=list)

    @field_validator("processes")
    @classmethod
    def _at_least_one(cls, value: list[Process]) -> list[Process]:
        if not value:
            raise ValueError("a profile must define at least one process")
        return value

    def process(self, key: str | None = None, *, layers: int | None = None) -> Process:
        """Select a process by id, or by layer count, or take the only one."""
        if key is not None:
            for p in self.processes:
                if p.id == key:
                    return p
            raise KeyError(
                f"{self.vendor}: no process {key!r}; have "
                f"{', '.join(p.id for p in self.processes)}"
            )
        if layers is not None:
            matches = [p for p in self.processes if p.layers == layers]
            if not matches:
                raise KeyError(
                    f"{self.vendor}: no process for {layers} layers; have "
                    f"{', '.join(f'{p.id} ({p.layers}L)' for p in self.processes)}"
                )
            return matches[0]
        if len(self.processes) > 1:
            raise KeyError(
                f"{self.vendor} defines several processes "
                f"({', '.join(p.id for p in self.processes)}); pass --process or --layers"
            )
        return self.processes[0]

    def unencoded_gaps(self) -> list[Gap]:
        return [g for g in self.gaps if g.encoded is not True]

    def provenance(self) -> dict[str, Any]:
        return {
            "vendor": self.vendor,
            "source": self.source,
            "retrieved": self.retrieved.isoformat(),
            "derived_from": self.derived_from,
            "gaps": len(self.unencoded_gaps()),
        }
