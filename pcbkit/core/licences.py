"""Licence audit over the installed dependency tree (CR-003).

A board is revised years after it is designed. If any step between requirements
and Gerbers depends on software that can be discontinued or relicensed, the
design stops being maintainable at that moment, and the failure is silent until
someone tries to open it.

Checked over what is actually installed rather than the declared direct
dependencies, because a transitive dependency is just as load-bearing and far
easier to acquire without noticing.
"""

from __future__ import annotations

import re
from importlib import metadata

from pcbkit.core.result import Envelope, Finding, Severity

# Permissive and copyleft licences that are OSI-approved. Matched
# case-insensitively against the declared licence or classifier.
OSI_PATTERNS = (
    r"\bMIT\b", r"\bBSD\b", r"\bApache\b", r"\bISC\b", r"\bPSF\b",
    r"\bPython Software Foundation\b", r"\bMPL\b", r"\bMozilla Public\b",
    r"\bGPL\b", r"\bLGPL\b", r"\bAGPL\b", r"\bZlib\b", r"\bUnlicense\b",
    r"\bCC0\b", r"\bArtistic\b", r"\bEPL\b", r"\bEclipse Public\b",
    r"\bBoost\b", r"\bAFL\b", r"\bHPND\b",
)
_OSI = re.compile("|".join(OSI_PATTERNS), re.IGNORECASE)

# Distributions whose metadata is absent or unhelpful but whose licence is
# known and OSI-approved. Each entry is a deliberate, reviewable exception.
KNOWN: dict[str, str] = {
    "pcbkit": "MIT",
}


def _declared(dist: metadata.Distribution) -> str:
    """Best licence string available, across the several places it may hide."""
    meta = dist.metadata
    for key in ("License-Expression", "License"):
        value = meta.get(key)
        if value and value.strip() and value.strip().upper() != "UNKNOWN":
            return value.strip()
    classifiers = meta.get_all("Classifier") or []
    for classifier in classifiers:
        if classifier.startswith("License ::"):
            return classifier.split("::")[-1].strip()
    return ""


def audit() -> Envelope:
    findings: list[Finding] = []
    packages: list[dict[str, str]] = []

    for dist in sorted(metadata.distributions(), key=lambda d: d.metadata["Name"] or ""):
        name = dist.metadata["Name"]
        if not name:
            continue
        licence = _declared(dist) or KNOWN.get(name.lower(), "")
        packages.append({"name": name, "version": dist.version, "licence": licence})

        if not licence:
            # CR-003: absence of a stated licence is rejection, not permission.
            findings.append(
                Finding(
                    source="licences",
                    code="licence.unstated",
                    severity=Severity.ERROR,
                    message=f"{name} {dist.version} declares no licence",
                    refs=[name],
                    fix="verify the licence upstream and add it to KNOWN, or drop the dependency",
                )
            )
        elif not _OSI.search(licence):
            findings.append(
                Finding(
                    source="licences",
                    code="licence.not_osi",
                    severity=Severity.ERROR,
                    message=f"{name} {dist.version} is {licence!r}, not a recognised OSI licence",
                    refs=[name],
                    fix="replace the dependency, or extend OSI_PATTERNS if this is a false negative",
                )
            )

    return Envelope(
        command="licences",
        data={"packages": packages, "count": len(packages)},
        findings=findings,
    )
