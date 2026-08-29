"""Turn part requests into orderable parts, or fail loudly.

Offline is the default rather than a mode. CR-003 rules that vendor data is an
input and never a dependency, so a cache miss during a build is a *finding*
naming the part and the command to fetch it -- not a stall on a socket.
"""

from __future__ import annotations

from pathlib import Path

from pcbkit.core.result import Envelope, Finding, Severity
from pcbkit.ir.models import Design
from pcbkit.parts import cache
from pcbkit.parts.cost import CostModel, rank
from pcbkit.parts.index import LibraryIndex, build_index
from pcbkit.parts.models import Candidate, Classification, PartRequest


def requests_from(design: Design, quantity: int = 5) -> list[PartRequest]:
    return [
        PartRequest(
            uid=c.uid,
            ref=c.ref or c.designator,
            part=c.part,
            value=c.value,
            lcsc=c.lcsc,
            mpn=c.mpn,
            package=c.package,
            quantity=quantity,
        )
        for c in design.components
    ]


def _pick_symbol(request: PartRequest, index: LibraryIndex) -> tuple[str | None, list[str]]:
    """Locate a symbol, returning it plus any alternatives worth reporting.

    Never guesses between several matches: an ambiguous symbol silently
    resolved is a board with the wrong pinout (AGENTS.md rule 6).
    """
    for term in filter(None, (request.mpn, request.part, request.value)):
        if ":" in term and index.symbol(term):
            return term, []
        matches = index.find_symbols(term, limit=6)
        exact = [m for m in matches if m.name.lower() == term.lower()]
        if len(exact) == 1:
            return exact[0].lib_id, []
        if exact:
            return None, [m.lib_id for m in exact]
        if len(matches) == 1:
            return matches[0].lib_id, []
        if matches:
            return None, [m.lib_id for m in matches]
    return None, []


def _pick_footprint(request: PartRequest, index: LibraryIndex) -> tuple[str | None, list[str]]:
    for term in filter(None, (request.package,)):
        if ":" in term and index.footprint(term):
            return term, []
        matches = index.find_footprints(term, limit=6)
        exact = [m for m in matches if m.name.lower() == term.lower()]
        if len(exact) == 1:
            return exact[0].lib_id, []
        if matches:
            return None, [m.lib_id for m in matches]
    return None, []


def resolve_one(
    request: PartRequest,
    *,
    index: LibraryIndex | None = None,
    cache_root: Path | None = None,
    model: CostModel | None = None,
) -> tuple[Candidate | None, list[Finding]]:
    index = index or build_index()
    findings: list[Finding] = []

    if not request.lcsc:
        findings.append(
            Finding(
                source="parts",
                code="parts.no_lcsc",
                severity=Severity.ERROR,
                message=f"{request.describe()} has no LCSC part number",
                refs=[request.ref] if request.ref else [],
                fix="add lcsc=\"C...\" to the part, or run `pcbkit parts pick` to choose one",
            )
        )
        return None, findings

    try:
        sourcing = cache.get(request.lcsc, root=cache_root)
    except cache.CacheMiss as exc:
        findings.append(
            Finding(
                source="parts",
                code="parts.not_cached",
                severity=Severity.ERROR,
                message=str(exc),
                refs=[request.ref] if request.ref else [],
                fix=f"run `pcbkit parts fetch {request.lcsc}` once, then it works offline",
            )
        )
        return None, findings

    symbol, symbol_alts = _pick_symbol(request, index)
    footprint, footprint_alts = _pick_footprint(request, index)

    candidate = Candidate(sourcing=sourcing, symbol=symbol, footprint=footprint)
    rank([candidate], request, model)

    if symbol is None:
        findings.append(
            Finding(
                source="parts",
                code="parts.symbol_unresolved",
                severity=Severity.ERROR,
                message=(
                    f"{request.describe()}: no unambiguous symbol"
                    + (f"; candidates: {', '.join(symbol_alts[:5])}" if symbol_alts else "")
                ),
                refs=[request.ref] if request.ref else [],
                fix="set symbol=\"Lib:Name\" on the part",
            )
        )
    if footprint is None:
        findings.append(
            Finding(
                source="parts",
                code="parts.footprint_unresolved",
                severity=Severity.ERROR,
                message=(
                    f"{request.describe()}: no unambiguous footprint"
                    + (f"; candidates: {', '.join(footprint_alts[:5])}" if footprint_alts else "")
                ),
                refs=[request.ref] if request.ref else [],
                fix="set footprint=\"Lib:Name\" on the part",
            )
        )

    for blocker in candidate.blockers:
        if blocker.startswith("incomplete"):
            continue  # already reported above, with the actionable detail
        findings.append(
            Finding(
                source="parts",
                code="parts.sourcing",
                severity=Severity.ERROR
                if "stock" in blocker or "assembly" in blocker
                else Severity.WARNING,
                message=f"{request.describe()} ({sourcing.lcsc}): {blocker}",
                refs=[request.ref] if request.ref else [],
                fix="choose another part with `pcbkit parts pick`, or lower the quantity",
            )
        )

    if sourcing.classification is Classification.EXTENDED:
        findings.append(
            Finding(
                source="parts",
                code="parts.extended",
                severity=Severity.WARNING,
                message=(
                    f"{request.describe()} ({sourcing.lcsc}) is an extended part; "
                    "it carries a per-part assembly setup fee"
                ),
                refs=[request.ref] if request.ref else [],
                fix="prefer a basic part, or see `pcbkit parts pick` for a substitution",
            )
        )

    return (candidate if candidate.complete else None), findings


def resolve_design(
    design: Design,
    *,
    quantity: int = 5,
    cache_root: Path | None = None,
    model: CostModel | None = None,
) -> Envelope:
    index = build_index()
    model = model or CostModel()
    resolved: dict[str, dict] = {}
    findings: list[Finding] = []
    total = 0.0

    for request in requests_from(design, quantity):
        candidate, part_findings = resolve_one(
            request, index=index, cache_root=cache_root, model=model
        )
        findings.extend(part_findings)
        if candidate is not None:
            resolved[request.ref] = {
                "lcsc": candidate.sourcing.lcsc,
                "mpn": candidate.sourcing.mpn,
                "symbol": candidate.symbol,
                "footprint": candidate.footprint,
                "classification": candidate.sourcing.classification.value,
                "stock": candidate.sourcing.stock,
                "line_cost": round(model.line_cost(candidate, quantity), 4),
            }
            total += model.line_cost(candidate, quantity)

    return Envelope(
        command="parts resolve",
        data={
            "design": design.name,
            "quantity": quantity,
            "requested": len(design.components),
            "resolved": len(resolved),
            "parts": resolved,
            "estimated_cost": round(total, 2),
        },
        findings=findings,
    )
