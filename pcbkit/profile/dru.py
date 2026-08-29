"""Generate KiCad custom design rules from a fabricator profile.

Generated, never transcribed. A hand-written `.kicad_dru` drifts from the vendor
and from KiCad, and its omissions become TODO comments nobody reads — which is
what CR-006 was raised about.

The output is a generated artifact under CR-005: it is reproduced from the
profile, which is what gets committed.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from pcbkit import __version__
from pcbkit.profile.models import Process, Profile

DRU_VERSION = 1


@dataclass(frozen=True)
class Rule:
    name: str
    constraints: list[str]
    condition: str | None = None
    layer: str | None = None
    comment: str | None = None

    def render(self) -> str:
        lines = []
        if self.comment:
            lines.extend(f"# {line}" for line in self.comment.splitlines())
        lines.append(f'(rule "{self.name}"')
        if self.layer:
            lines.append(f"\t(layer {self.layer})")
        if self.condition:
            lines.append(f'\t(condition "{self.condition}")')
        for constraint in self.constraints:
            lines.append(f"\t(constraint {constraint})")
        lines.append(")")
        return "\n".join(lines)


def _mm(value: float) -> str:
    """KiCad wants a unit suffix; trailing zeros are noise in a diffed file."""
    return f"{value:g}mm"


def rules_for(process: Process) -> list[Rule]:
    """Every rule this profile can express, in a stable order.

    Order is fixed so regeneration produces a byte-identical file and
    `pcbkit profile check` reports real drift rather than reordering.
    """
    limits = process.limits
    return [
        Rule(
            "Track width, outer layer",
            [f"track_width (min {_mm(limits.track_width_mm.outer)})"],
            condition="A.Type == 'track'",
            layer="outer",
        ),
        Rule(
            "Track width, inner layer",
            [f"track_width (min {_mm(limits.track_width_mm.inner)})"],
            condition="A.Type == 'track'",
            layer="inner",
        ),
        Rule(
            "Track spacing, outer layer",
            [f"clearance (min {_mm(limits.track_spacing_mm.outer)})"],
            condition="A.Type == 'track' && B.Type == A.Type",
            layer="outer",
        ),
        Rule(
            "Track spacing, inner layer",
            [f"clearance (min {_mm(limits.track_spacing_mm.inner)})"],
            condition="A.Type == 'track' && B.Type == A.Type",
            layer="inner",
        ),
        Rule(
            "Hole diameter",
            [
                f"hole_size (min {_mm(limits.hole_diameter_mm.min)}) "
                f"(max {_mm(limits.hole_diameter_mm.max)})"
            ],
            comment="Covers all holes; more specific rules follow.",
        ),
        Rule(
            "Hole (NPTH) diameter",
            [f"hole_size (min {_mm(limits.npth_hole_min_mm)})"],
            condition="!A.isPlated()",
            layer="outer",
        ),
        Rule(
            "Hole (castellated) diameter",
            [f"hole_size (min {_mm(limits.castellated_hole_min_mm)})"],
            condition="A.Type == 'pad' && A.Fabrication_Property == 'Castellated pad'",
            layer="outer",
        ),
        Rule(
            "Annular ring width (via and PTH)",
            [f"annular_width (min {_mm(limits.annular_ring_min_mm)})"],
            condition="A.isPlated()",
            layer="outer",
        ),
        Rule(
            "Clearance: hole to hole, different nets",
            [f"hole_to_hole (min {_mm(limits.hole_to_hole_mm.different_nets)})"],
            condition="A.Net != B.Net",
            layer="outer",
        ),
        Rule(
            "Clearance: hole to hole, same net",
            [f"hole_to_hole (min {_mm(limits.hole_to_hole_mm.same_net)})"],
            condition="A.Net == B.Net",
            layer="outer",
        ),
        Rule(
            "Clearance: track to NPTH hole",
            [f"hole_clearance (min {_mm(limits.track_to_npth_mm)})"],
            condition="!A.isPlated() && B.Type == 'track' && A.Net != B.Net",
        ),
        Rule(
            "Clearance: track to PTH hole",
            [f"hole_clearance (min {_mm(limits.track_to_pth_mm)})"],
            condition="A.isPlated() && B.Type == 'track' && A.Net != B.Net",
        ),
        Rule(
            "Clearance: track to pad",
            [f"clearance (min {_mm(limits.track_to_pad_mm)})"],
            condition="A.Type == 'pad' && B.Type == 'track' && A.Net != B.Net",
        ),
        Rule(
            "Clearance: pad/via to pad/via",
            [f"clearance (min {_mm(limits.pad_to_pad_mm)})"],
            condition="A.isPlated() && B.isPlated() && A.Net != B.Net",
            layer="outer",
        ),
        Rule(
            "Edge clearance (routed)",
            [f"edge_clearance (min {_mm(limits.edge_clearance_mm)})"],
            condition="A.Type == 'track'",
            comment=(
                "V-cut edges need "
                f"{_mm(limits.edge_clearance_vcut_mm)}; pcbkit does not yet know "
                "which edges are v-cut, so the routed figure is applied."
            ),
        ),
        Rule(
            "Silkscreen text",
            [
                f"text_thickness (min {_mm(limits.silk_thickness_min_mm)})",
                f"text_height (min {_mm(limits.silk_height_min_mm)})",
            ],
            condition="A.Type == 'Text' || A.Type == 'Text Box'",
            layer='"?.Silkscreen"',
        ),
        Rule(
            "Pad to silkscreen",
            [f"silk_clearance (min {_mm(limits.pad_to_silk_mm)})"],
            condition="A.Type == 'pad' && B.Layer == '?.Silkscreen'",
            layer="outer",
        ),
    ]


def render(profile: Profile, process: Process) -> str:
    """The complete `.kicad_dru` text for one process."""
    header = [
        f"(version {DRU_VERSION})",
        "#",
        f"# GENERATED by pcbkit {__version__} — do not edit.",
        "# Edit the profile and regenerate; `pcbkit profile check` reports drift.",
        "#",
        f"# Fabricator: {profile.vendor}",
        f"# Process:    {process.id} ({process.layers} layer, {process.copper_oz} oz)",
        f"# Source:     {profile.source}",
        f"# Retrieved:  {profile.retrieved.isoformat()}",
    ]
    gaps = profile.unencoded_gaps()
    if gaps:
        header += [
            "#",
            f"# {len(gaps)} known limit(s) are NOT enforced by these rules:",
            *[f"#   - {g.id}: {' '.join(g.why.split())}" for g in gaps],
            "# A clean DRC does not mean the board is within every published limit.",
        ]
    body = "\n\n".join(rule.render() for rule in rules_for(process))
    return "\n".join(header) + "\n\n" + body + "\n"


def digest(text: str) -> str:
    """Fingerprint used to detect a stale generated file."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]
