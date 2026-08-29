"""Vendored part data. The source of truth, not an optimisation.

CR-003 rules that vendor data is an input, never a dependency: a build must
succeed with the service unreachable. That inverts the obvious design — the
cache is authoritative and the network merely populates it.

Contents are a *vendored input* under CR-005, so they are committed. A part
resolved today must keep resolving in three years when the API has changed.
"""

from __future__ import annotations

import json
from pathlib import Path

from pcbkit.parts.models import Sourcing

# Repository-level vendor directory, established by M2.
DEFAULT_CACHE = Path(__file__).resolve().parent.parent.parent / "vendor" / "parts"


class CacheMiss(LookupError):
    """A part is not cached. Not an error during a build -- a finding."""


def _path(lcsc: str, root: Path) -> Path:
    return root / f"{lcsc.upper()}.json"


def get(lcsc: str, *, root: Path | None = None) -> Sourcing:
    path = _path(lcsc, root or DEFAULT_CACHE)
    if not path.is_file():
        raise CacheMiss(f"{lcsc} is not cached; run `pcbkit parts fetch {lcsc}`")
    try:
        return Sourcing.model_validate(json.loads(path.read_text()))
    except Exception as exc:
        raise CacheMiss(f"{path} is unreadable: {exc}") from exc


def has(lcsc: str, *, root: Path | None = None) -> bool:
    return _path(lcsc, root or DEFAULT_CACHE).is_file()


def put(sourcing: Sourcing, *, root: Path | None = None) -> Path:
    root = root or DEFAULT_CACHE
    root.mkdir(parents=True, exist_ok=True)
    path = _path(sourcing.lcsc, root)
    path.write_text(json.dumps(sourcing.model_dump(mode="json"), indent=2, sort_keys=True))
    return path


def entries(root: Path | None = None) -> list[str]:
    root = root or DEFAULT_CACHE
    return sorted(p.stem for p in root.glob("*.json")) if root.is_dir() else []
