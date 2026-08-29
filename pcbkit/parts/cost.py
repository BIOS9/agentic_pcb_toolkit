"""Ranking and the basic-part substitution suggester (CR-007).

Selection is a cost decision, not a lookup: an extended part carries a per-part
setup fee that dominates the bill at low volume, so the cheapest correct board
often uses a worse-fitting basic part. The ranking is always reported, because
a substitution that changes cost or availability without saying so is exactly
what AGENTS.md rule 6 forbids.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from pcbkit.parts.models import Candidate, Classification, PartRequest

# Defaults; a fabricator profile overrides them (CR-006 -- fees are data).
DEFAULT_EXTENDED_SETUP_FEE = 3.00
DEFAULT_STOCK_MARGIN = 10
DEFAULT_STOCK_FLOOR = 500

# JLCPCB's basic resistors and capacitors are E24 at 1%. Combinations are
# searched over this set rather than over every purchasable value.
E24 = (
    1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0,
    3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1,
)


@dataclass
class CostModel:
    """Assembly economics. Figures are data, dated in the profile, never
    constants in an emitter (AGENTS.md rule 10)."""

    extended_setup_fee: float = DEFAULT_EXTENDED_SETUP_FEE
    stock_margin: int = DEFAULT_STOCK_MARGIN
    stock_floor: int = DEFAULT_STOCK_FLOOR

    def line_cost(self, candidate: Candidate, quantity: int, per_board: int = 1) -> float:
        """Total cost of using this part across the whole build."""
        unit = candidate.sourcing.price or 0.0
        parts = quantity * per_board
        fee = (
            self.extended_setup_fee
            if candidate.sourcing.classification is Classification.EXTENDED
            else 0.0
        )
        return unit * parts + fee


def rank(
    candidates: list[Candidate],
    request: PartRequest,
    model: CostModel | None = None,
) -> list[Candidate]:
    """Score candidates and sort best first, recording why.

    Blockers are recorded rather than filtering the candidate away: knowing that
    the only match is out of stock is more useful than an empty list.
    """
    model = model or CostModel()
    quantity = request.quantity

    for candidate in candidates:
        sourcing = candidate.sourcing
        score = 0.0
        reasons: list[str] = []
        blockers: list[str] = []

        if not candidate.complete:
            missing = [
                n for n, v in (("symbol", candidate.symbol),
                               ("footprint", candidate.footprint)) if not v
            ]
            blockers.append(f"incomplete: no {' or '.join(missing)}")

        if not sourcing.assembly:
            blockers.append("not offered for assembly")
        else:
            score += 20
            reasons.append("available for assembly")

        if sourcing.stock_ok(quantity, margin=model.stock_margin, floor=model.stock_floor):
            score += 30
            reasons.append(f"stock {sourcing.stock:,} clears margin")
        else:
            needed = max(quantity * model.stock_margin, model.stock_floor)
            blockers.append(f"stock {sourcing.stock:,} below margin of {needed:,}")

        if sourcing.classification is Classification.BASIC:
            score += 25
            reasons.append("basic part, no setup fee")
        elif sourcing.classification is Classification.EXTENDED:
            fee = model.extended_setup_fee
            unit_total = (sourcing.price or 0) * quantity
            reasons.append(
                f"extended part, ${fee:.2f} setup"
                + (f" vs ${unit_total:.2f} of parts" if unit_total else "")
            )
            # The fee matters in proportion to how much it dominates the line.
            score += 5 if unit_total > fee * 3 else 0
        else:
            blockers.append("classification unknown")

        total = model.line_cost(candidate, quantity)
        if sourcing.price is not None:
            score += max(0.0, 15.0 - total)
            reasons.append(f"${total:.2f} total at qty {quantity}")

        age = sourcing.age_days()
        if age > 90:
            blockers.append(f"sourcing data is {age} days old")
        elif age > 30:
            reasons.append(f"sourcing data {age} days old")

        candidate.score = round(score, 2)
        candidate.reasons = reasons
        candidate.blockers = blockers

    return sorted(
        candidates,
        key=lambda c: (len(c.blockers), -c.score, c.sourcing.price or math.inf),
    )


# --------------------------------------------------------------------------
# Basic-part substitution
# --------------------------------------------------------------------------


@dataclass
class Combination:
    """Two basic parts standing in for one extended part."""

    topology: str  # "series" | "parallel"
    values: tuple[float, float]
    achieved: float
    target: float
    part_tolerance_pct: float
    saving: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def nominal_error_pct(self) -> float:
        return abs(self.achieved - self.target) / self.target * 100.0

    @property
    def worst_case_pct(self) -> float:
        """Worst-case deviation of the combination from the *target*.

        Combining equal-tolerance resistors does not multiply their tolerance:
        two 1% parts in series worst-case both high give (R1+R2)x1.01, still 1%.
        What the substitution actually costs is the nominal error from not
        landing on the target exactly, which adds to the part tolerance.
        """
        return self.nominal_error_pct + self.part_tolerance_pct

    def describe(self) -> str:
        a, b = self.values
        joiner = "+" if self.topology == "series" else "∥"
        return (
            f"{_eng(a)} {joiner} {_eng(b)} = {_eng(self.achieved)} "
            f"(target {_eng(self.target)}, nominal error {self.nominal_error_pct:.2f}%, "
            f"worst case {self.worst_case_pct:.2f}% vs {self.part_tolerance_pct:.2f}% single)"
        )


def _eng(value: float) -> str:
    for limit, suffix in ((1e6, "M"), (1e3, "k"), (1.0, "")):
        if abs(value) >= limit:
            return f"{value / limit:g}{suffix}"
    return f"{value:g}"


def _decade_values(target: float, series: tuple[float, ...]) -> list[float]:
    """Series values spanning the decades that could combine to the target."""
    if target <= 0:
        return []
    top = math.floor(math.log10(target))
    values: list[float] = []
    for decade in range(top - 2, top + 1):
        values.extend(v * (10 ** decade) for v in series)
    return values


def suggest_substitution(
    target: float,
    *,
    extended_unit_price: float,
    basic_unit_price: float,
    quantity: int,
    per_board: int = 1,
    part_tolerance_pct: float = 1.0,
    setup_fee: float = DEFAULT_EXTENDED_SETUP_FEE,
    series: tuple[float, ...] = E24,
    max_error_pct: float = 1.0,
) -> Combination | None:
    """Best two-basic-part stand-in for an extended value, or None.

    Reported, never applied: substitution changes schematic topology to save
    money, trading board area, part count, and nominal accuracy. Whether that
    is worth it is a design decision (CR-007).
    """
    values = _decade_values(target, series)
    if not values:
        return None

    best: Combination | None = None
    for i, a in enumerate(values):
        for b in values[i:]:
            for topology, achieved in (
                ("series", a + b),
                ("parallel", (a * b) / (a + b) if (a + b) else 0.0),
            ):
                if achieved <= 0:
                    continue
                error = abs(achieved - target) / target * 100.0
                if error > max_error_pct:
                    continue
                if best is None or error < best.nominal_error_pct:
                    best = Combination(
                        topology=topology,
                        values=(a, b),
                        achieved=achieved,
                        target=target,
                        part_tolerance_pct=part_tolerance_pct,
                    )
    if best is None:
        return None

    parts = quantity * per_board
    single_cost = extended_unit_price * parts + setup_fee
    combo_cost = basic_unit_price * parts * 2
    best.saving = round(single_cost - combo_cost, 2)
    best.notes = [
        f"one extended part: ${single_cost:.2f} (${extended_unit_price:.4f} x {parts} + ${setup_fee:.2f} setup)",
        f"two basic parts:   ${combo_cost:.2f} (${basic_unit_price:.4f} x {parts * 2})",
        "adds a component and its placement; check there is room",
    ]
    return best
