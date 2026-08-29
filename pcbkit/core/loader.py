"""Load a design file: import it and hand back the Design objects it defines.

A design file is an ordinary Python module. `@design` runs at import and rebinds
the decorated name to a finished `Design`, so discovery is just "look for Design
instances" -- no registry, no plugin protocol, and the file stays runnable with
a bare `python`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from pcbkit.ir.models import Design


class DesignLoadError(RuntimeError):
    """The design file could not be imported, or defines no usable design."""


def load_designs(path: Path) -> dict[str, Design]:
    """Import `path` and return every Design it defines, keyed by variable name."""
    path = Path(path).resolve()
    if not path.exists():
        raise DesignLoadError(f"no such design file: {path}")

    spec = importlib.util.spec_from_file_location(f"pcbkit_design_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise DesignLoadError(f"cannot import {path} as a Python module")

    module = importlib.util.module_from_spec(spec)
    # Let the design file import siblings next to it.
    sys.path.insert(0, str(path.parent))
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise DesignLoadError(f"{path.name}: {type(exc).__name__}: {exc}") from exc
    finally:
        sys.path.remove(str(path.parent))
        sys.modules.pop(spec.name, None)

    return {
        name: value
        for name, value in vars(module).items()
        if isinstance(value, Design) and not name.startswith("_")
    }


def load_design(path: Path, name: str | None = None) -> Design:
    """Load exactly one design, failing clearly when the choice is ambiguous."""
    designs = load_designs(path)
    if not designs:
        raise DesignLoadError(
            f"{Path(path).name} defines no design; decorate a function with @design"
        )
    if name is not None:
        for var, value in designs.items():
            if name in (var, value.name):
                return value
        raise DesignLoadError(
            f"no design named {name!r} in {Path(path).name}; "
            f"found: {', '.join(sorted(designs))}"
        )
    if len(designs) > 1:
        raise DesignLoadError(
            f"{Path(path).name} defines several designs "
            f"({', '.join(sorted(designs))}); pass --design to choose"
        )
    return next(iter(designs.values()))
