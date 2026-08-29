"""Index of the KiCad symbol and footprint libraries on this machine.

Purely local and network-free. Most passives, connectors, and common ICs are
already in the stock libraries, so the resolver consults this before it
considers fetching anything — the cheapest fetch is the one not made.

Library paths come from `toolchain`, never from a literal (AGENTS.md rule 11).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from pcbkit.core import toolchain

# Top-level symbol definitions in a .kicad_sym file. Nested `(symbol "NAME_1_1"`
# unit definitions are indented, so anchoring to the line start skips them
# without parsing the whole s-expression.
_SYMBOL_RE = re.compile(r'^\t\(symbol "([^"]+)"', re.MULTILINE)


@dataclass(frozen=True)
class SymbolRef:
    library: str
    name: str

    @property
    def lib_id(self) -> str:
        return f"{self.library}:{self.name}"


@dataclass(frozen=True)
class FootprintRef:
    library: str
    name: str
    path: Path

    @property
    def lib_id(self) -> str:
        return f"{self.library}:{self.name}"


@dataclass
class LibraryIndex:
    symbols: dict[str, SymbolRef] = field(default_factory=dict)
    footprints: dict[str, FootprintRef] = field(default_factory=dict)

    @property
    def counts(self) -> dict[str, int]:
        return {"symbols": len(self.symbols), "footprints": len(self.footprints)}

    def symbol(self, lib_id: str) -> SymbolRef | None:
        return self.symbols.get(lib_id)

    def footprint(self, lib_id: str) -> FootprintRef | None:
        return self.footprints.get(lib_id)

    def find_symbols(self, term: str, limit: int = 20) -> list[SymbolRef]:
        """Case-insensitive substring search, exact matches first."""
        needle = term.lower()
        exact = [s for s in self.symbols.values() if s.name.lower() == needle]
        partial = [
            s
            for s in self.symbols.values()
            if needle in s.name.lower() and s not in exact
        ]
        return (exact + partial)[:limit]

    def find_footprints(self, term: str, limit: int = 20) -> list[FootprintRef]:
        needle = term.lower()
        exact = [f for f in self.footprints.values() if f.name.lower() == needle]
        partial = [
            f
            for f in self.footprints.values()
            if needle in f.name.lower() and f not in exact
        ]
        return (exact + partial)[:limit]


def _scan_symbols(directory: Path) -> dict[str, SymbolRef]:
    found: dict[str, SymbolRef] = {}
    for lib_file in sorted(directory.glob("*.kicad_sym")):
        library = lib_file.stem
        try:
            text = lib_file.read_text(errors="replace")
        except OSError:
            continue
        for name in _SYMBOL_RE.findall(text):
            ref = SymbolRef(library, name)
            found[ref.lib_id] = ref
    return found


def _scan_footprints(directory: Path) -> dict[str, FootprintRef]:
    found: dict[str, FootprintRef] = {}
    for lib_dir in sorted(directory.glob("*.pretty")):
        library = lib_dir.name[: -len(".pretty")]
        for mod in sorted(lib_dir.glob("*.kicad_mod")):
            ref = FootprintRef(library, mod.stem, mod)
            found[ref.lib_id] = ref
    return found


@lru_cache(maxsize=1)
def build_index() -> LibraryIndex:
    """Scan the resolved library directories. Cached: it walks ~40k files."""
    index = LibraryIndex()
    symbols_dir = toolchain.resolve_library("symbols").path
    footprints_dir = toolchain.resolve_library("footprints").path
    if symbols_dir is not None:
        index.symbols = _scan_symbols(symbols_dir)
    if footprints_dir is not None:
        index.footprints = _scan_footprints(footprints_dir)
    return index
