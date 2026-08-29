# M0 — Environment guard

## Problem

Every later milestone assumes a specific toolchain: KiCad 10 with `kicad-cli`
and the `pcbnew` Python module, plus optional `ngspice` and `java`. Without an
up-front check, a missing or drifted dependency surfaces as an opaque failure
deep inside an emitter subprocess, and an agent cannot tell a broken install
from a broken design.

## Outcome

`pcbkit doctor` verifies every assumption and, for each failure, says what is
wrong and how to fix it. The package skeleton, the CLI output contract, and the
pinned KiCad file-format versions land with it.

## Constraints

- Findings are data: a broken environment must not crash the tool.
- Format versions must be discovered empirically, not assumed from documentation.

## Open questions (resolved during M0)

- **Which interpreter owns `pcbnew`?** Resolved: it is a system C++ extension
  invisible to our venv. `kicad.pcbnew_python()` resolves it; see AGENTS.md #2.
- **What format versions does KiCad 10.0.5 emit?** Resolved: see the table in
  `spec.md`.
