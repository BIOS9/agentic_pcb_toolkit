"""The pcbkit CLI output contract.

One JSON object on stdout, logs on stderr, and a nonzero exit only when a tool
failed to run. Design violations are *data*: they come back inside a successful
envelope so the agent loop reads them instead of parsing a traceback.
"""

from __future__ import annotations

import enum
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class Severity(str, enum.Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    IGNORE = "ignore"


class Finding(BaseModel):
    """One normalized violation, whatever produced it.

    ERC, DRC, the IR rule engine, and the simulator all reduce to this shape so
    the agent has a single thing to read and `findings/*.json` has one schema.
    """

    source: str = Field(description="erc | drc | rules | sim | parity")
    code: str = Field(description="stable machine identifier, e.g. 'pcb.clearance'")
    severity: Severity = Severity.ERROR
    message: str = ""
    refs: list[str] = Field(default_factory=list, description="component refdes")
    nets: list[str] = Field(default_factory=list)
    location_mm: tuple[float, float] | None = None
    layer: str | None = None
    fix: str | None = Field(default=None, description="suggested remedy, if known")

    def one_line(self) -> str:
        where = ""
        if self.refs:
            where = f" [{','.join(self.refs)}]"
        elif self.nets:
            where = f" <{','.join(self.nets)}>"
        return f"{self.severity.value}: {self.code}{where}: {self.message}"


class Envelope(BaseModel):
    """What every CLI verb prints."""

    ok: bool = True
    command: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)
    errors: list[str] = Field(
        default_factory=list, description="tool failures, not design violations"
    )

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.findings if f.severity is Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity is Severity.WARNING)

    def summary(self) -> dict[str, int]:
        return {"errors": self.error_count, "warnings": self.warning_count}

    def to_json(self) -> str:
        payload = self.model_dump(mode="json")
        payload["summary"] = self.summary()
        return json.dumps(payload, indent=2)

    def emit(self) -> int:
        """Print to stdout and return the process exit code.

        Exit is nonzero only when a tool failed (`ok=False`). A design with 40
        DRC errors still exits 0 -- that is a successful check run.
        """
        print(self.to_json())
        return 0 if self.ok else 1

    def write_findings(self, path: Path) -> None:
        """Persist findings for later gate stages (see plan: v2 gate layer)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "command": self.command,
                    "summary": self.summary(),
                    "findings": [f.model_dump(mode="json") for f in self.findings],
                },
                indent=2,
            )
        )


def log(message: str) -> None:
    """Human-facing progress. Always stderr, never stdout."""
    print(message, file=sys.stderr)
