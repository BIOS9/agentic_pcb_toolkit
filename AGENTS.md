# pcbkit — conventions

Toolkit that turns a Python circuit description into a production-ready KiCad
project and fab package. Read this before changing anything under `pcbkit/`.

This file is the canonical conventions document for **every** agent and human
working on pcbkit. It is deliberately not named after one vendor -- see rule 7.

## Non-obvious rules

These each cost real debugging time to rediscover.

### 1. Never infer failure from stderr

KiCad tools write to stderr on success. Importing `pcbnew` emits three benign
`PROPERTY_ENUM()` wx asserts every single time. `kicad-cli` logs progress there.

Success is **exit code plus parsed output**. All subprocess calls go through
`pcbkit.core.kicad.run()`, which enforces this. Do not call `subprocess` directly.

### 2. `pcbnew` is not importable from our venv

It is a system-installed C++ extension module, not a pip package. A plain
virtualenv cannot see it, and `python3` off `PATH` resolves to the venv.

Never write `import pcbnew` at module scope. Use
`pcbkit.core.kicad.run_pcbnew(script)`, which resolves the interpreter that
actually owns the bindings (override with `PCBKIT_PCBNEW_PYTHON`).

### 3. Violations are data; exit 0

Every CLI verb prints **one JSON object** to stdout, logs to stderr, and exits
nonzero **only when a tool failed to run**. A board with 40 DRC errors is a
*successful* check — the agent reads `findings[]` instead of parsing a traceback.

`--strict` opts into a CI gate, mirroring `kicad-cli --exit-code-violations`.

Build output with `pcbkit.core.result.Envelope`; never `print()` to stdout
outside a frontend, and never `sys.exit()` inside `pcbkit/core/`.

### 4. Pinned file-format versions

`pcbkit.core.kicad.FORMAT_VERSIONS`, confirmed against KiCad 10.0.5:

| File | Version | Generator |
|---|---|---|
| `.kicad_pcb` | `20260206` | `10.0` |
| `.kicad_sch` | `20260306` | `10.0` |
| `.kicad_sym` | `20251024` | — |
| `.kicad_mod` | `20260206` | — |

`pcbkit doctor` warns on drift. If KiCad is upgraded, re-run the emitter tests
before changing these numbers.

`kicad-cli sch upgrade` migrates an older schematic to the current format — a
useful escape hatch if a writer library lags the installed KiCad.

### 5. KiCad 10 renumbered copper layers

`F.Cu` is `0` and `B.Cu` is **`2`**, not the pre-10 value of `31`; inner copper
takes the even numbers between. Hardcoding pre-10 ids is a silent
wrong-layer bug. Resolve layer names through `pcbnew` rather than by literal.

### 6. Never silently substitute a part

A part resolves to a complete `(symbol, footprint, 3d, lcsc, stock)` tuple or it
fails loudly with a finding. Guessing a footprint produces a board that fails at
assembly, which is discovered after the money is spent.

Selection is a ranked cost decision, and the ranking is **reported** — why the
winner won, on availability, basic/extended classification, price at the stated
quantity, and electrical fit. Stock must clear `max(quantity x margin, floor)`;
a part that only just covers the build will be gone by order time. See
[CR-007](docs/sdlc/CR-007-jlcpcb-assembly-default/).

### 7. No agent may be privileged

pcbkit must work identically under any agent -- Claude Code, Codex, Cursor, a
plain script, a human at a terminal. Enforced by `tests/test_agent_neutral.py`.

Concretely:

- **Nothing under `pcbkit/` names a vendor.** Not in code, not in comments, not
  in strings. That includes this file's old name.
- **Every capability is reachable from the CLI.** A feature that exists only
  behind a Claude Code hook, skill, or slash command does not exist for a Codex
  agent. Enforcement in particular belongs in the tool (`pcbkit gate`), not in
  one harness's hook -- a hook is bypassed by calling the CLI directly.
- **`docs/agent/workflow.md` is the source of truth** for agent-facing guidance.
  Per-agent files (`skills/pcb-design/SKILL.md`, MCP tool descriptions) are
  *generated adapters*, kept in sync by `pcbkit docs sync --check`.
- **`pcbkit/core/` reads no agent environment variables.** The only env var
  pcbkit honours is `PCBKIT_PCBNEW_PYTHON`.

Per-agent behaviour *evals* are the deliberate exception: evaluating how an
agent behaves is necessarily agent-specific. See CR-001.

### 8. Open-source software only

Everything in the path from requirements to fab output must be open source, so
a design stays maintainable for as long as the board exists. Before adding any
dependency, check its licence; absence of a stated licence is rejection, not
permission. Fab output uses published formats (Gerber X2, Excellon, IPC-2581,
ODB++) — a vendor package is an *arrangement* of those, never a private format.

Vendor part data (LCSC, EasyEDA) is an input, not a dependency: it may enrich a
build, never gate one. See [CR-003](docs/sdlc/CR-003-open-source-only/).

### 9. Build artifacts never go in git

If it can be regenerated deterministically from this repository, it does not
belong in a commit — Gerbers, PDFs, renders, Nix results, `findings/`,
`release/`. Vendored inputs are *not* regenerable from the repo and are
committed; so are fingerprints (hashes, lockfiles), which are what make
committing the artifacts unnecessary.

Run output goes to CI artifact storage, released output to a GitHub Release.
See [CR-005](docs/sdlc/CR-005-no-build-artifacts/).

### 10. Fabricator limits are profile data, never constants

Never write a manufacturing limit into code. `MIN_TRACK_MM = 0.127` in an
emitter is a bug: limits differ per fabricator, per layer count, and per copper
weight, and they change. They live in a dated profile file, and the
`.kicad_dru` is **generated** from it rather than transcribed.

DRC runs against those rules from the first build, not at fab time. A violation
caught while iterating digitally costs seconds; caught at order time it costs a
respin; caught by the fab's own optimiser it may never be reported at all.
See [CR-006](docs/sdlc/CR-006-fab-capabilities-as-drc/).

## Layout

- `pcbkit/core/` — pure functions. No argv, no stdout, no `sys.exit`.
- `pcbkit/cli.py` — thin argv shell over core.

Keeping that split strict is what makes the v2 gate layer and an MCP frontend
cheap to add later. Anything a frontend needs must be callable without argv.

## Tests

`uv run pytest`. Golden files under `tests/golden/` are regenerated only by an
explicit command — never edit one to make a failing test pass. A golden diff
means either a real regression or a KiCad format change; find out which.

## Commands

```console
uv sync                    # set up
uv run pcbkit doctor --text
uv run pytest -q
```
