"""Build a design file into IR, with structural validation.

Structural checks only: things that are wrong regardless of what the circuit is
meant to do (a part nobody connected, a net with one end). Electrical judgement
-- decoupling, pull-ups, trace width -- belongs to the rule engine, which runs
against a resolved design.
"""

from __future__ import annotations

import json
from pathlib import Path

from pcbkit.core.loader import DesignLoadError, load_design
from pcbkit.core.result import Envelope, Finding, Severity
from pcbkit.ir.models import Design


def validate_structure(design: Design) -> list[Finding]:
    findings: list[Finding] = []

    connected: set[str] = {node.uid for net in design.nets for node in net.nodes}
    for component in design.components:
        if component.uid not in connected:
            findings.append(
                Finding(
                    source="build",
                    code="ir.unconnected_component",
                    severity=Severity.ERROR,
                    message=f"{component.designator} ({component.value}) has no connections",
                    refs=[component.designator],
                    fix="connect its pins, or delete it if it is not needed",
                )
            )

    for net in design.nets:
        if len(net.nodes) == 1:
            node = net.nodes[0]
            owner = design.component(node.uid)
            ref = owner.designator if owner else node.uid
            findings.append(
                Finding(
                    source="build",
                    code="ir.single_node_net",
                    severity=Severity.WARNING,
                    message=f"net {net.name!r} connects only {ref}.{node.pin}",
                    nets=[net.name],
                    refs=[ref],
                    fix="connect a second pin, or mark the pin no-connect",
                )
            )
        elif not net.nodes:
            findings.append(
                Finding(
                    source="build",
                    code="ir.empty_net",
                    severity=Severity.WARNING,
                    message=f"net {net.name!r} has no connections",
                    nets=[net.name],
                    fix="remove the net, or connect it",
                )
            )

    seen: dict[str, str] = {}
    for component in design.components:
        if component.ref is None:
            findings.append(
                Finding(
                    source="build",
                    code="ir.unannotated",
                    severity=Severity.ERROR,
                    message=f"{component.uid} has no refdes",
                    fix="call design.annotate()",
                )
            )
            continue
        if component.ref in seen:
            findings.append(
                Finding(
                    source="build",
                    code="ir.duplicate_refdes",
                    severity=Severity.ERROR,
                    message=f"refdes {component.ref} used by {seen[component.ref]} and {component.uid}",
                    refs=[component.ref],
                    fix="re-run annotation; this indicates a pcbkit bug",
                )
            )
        seen[component.ref] = component.uid

    known = {c.uid for c in design.components}
    for net in design.nets:
        for node in net.nodes:
            if node.uid not in known:
                findings.append(
                    Finding(
                        source="build",
                        code="ir.dangling_reference",
                        severity=Severity.ERROR,
                        message=f"net {net.name!r} references unknown component {node.uid}",
                        nets=[net.name],
                        fix="this indicates a pcbkit bug; please report it",
                    )
                )
    return findings


def build(
    path: Path,
    *,
    design_name: str | None = None,
    outdir: Path | None = None,
    include_ir: bool = False,
) -> Envelope:
    """Load a design file, validate its structure, and emit the IR."""
    try:
        design = load_design(Path(path), design_name)
    except DesignLoadError as exc:
        return Envelope(command="build", ok=False, errors=[str(exc)])

    findings = validate_structure(design)
    data: dict = {
        "design": design.name,
        "source": str(Path(path).resolve()),
        "stats": design.stats(),
    }

    if outdir is not None:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        ir_path = outdir / f"{design.name}.ir.json"
        ir_path.write_text(json.dumps(design.model_dump(mode="json"), indent=2))
        data["ir_path"] = str(ir_path)

    if include_ir:
        data["ir"] = design.model_dump(mode="json")

    envelope = Envelope(command="build", data=data, findings=findings)
    if outdir is not None:
        envelope.write_findings(Path(outdir).parent / "findings" / "build.json")
    return envelope
