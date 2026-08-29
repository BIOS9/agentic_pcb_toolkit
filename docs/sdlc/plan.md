# Implementation plan — M2 to M10

Supersedes the original M0–M7 plan, which was approved before any of the seven
change requests existed. M0 and M1 shipped under it and are unchanged.

## Why re-plan

The CRs did not add features to the old plan; they moved things it treated as
settled. Three shifts in particular make the old M2–M7 aim at the wrong target:

1. **The entry point moved up a level.** CR-002 puts requirements above the
   Python DSL, so "parts resolution" and "build" now sit under a layer the old
   plan did not have.
2. **Constraints moved earlier.** CR-006 pulls manufacturing limits out of the
   output stage and into every build; CR-004 pulls toolchain pinning ahead of
   the emitters that would otherwise hardcode system paths.
3. **The gate stopped being optional.** CR-001 puts enforcement in the CLI
   rather than a harness hook, CR-002 makes the gate the boundary between a free
   loop and an expensive one, and CR-005 changes how its approval is recorded.

Building M2 as originally written would produce work the CRs then invalidate.

## The accepted decisions, in one place

| CR | Decision | Where it lands |
|---|---|---|
| 001 | No agent is privileged; CLI is the portable surface | M2, M10 |
| 002 | Requirements are the entry point; two loops split at the fab gate | M8, M9 |
| 003 | Open-source toolchain; vendor data enriches, never gates | M2, M4 |
| 004 | Hermetic, reproducible builds via Nix; deterministic fab output | M2, M9 |
| 005 | No build artifacts in git; approval record split from payload | M3, M9 |
| 006 | Fabricator limits are profile data; DRC from the first build | M3, M6 |
| 007 | Assembled JLCPCB order is the default; ranked part selection | M4 |

## Architecture

Changes from the original tree are marked.

```
flake.nix                    NEW  pins the entire toolchain (CR-004)
profiles/jlcpcb.yaml         NEW  fab + assembly capabilities as data (CR-006/007)
vendor/                      NEW  fetched inputs, hash-recorded (CR-003/004)
docs/agent/workflow.md       NEW  canonical agent guidance (CR-001)
docs/releases/<version>.md   NEW  approval records, committed (CR-005)

pcbkit/
  ir/          Design, Component, Net, NetClass, Constraint      (shipped)
  dsl/         @module, @design, Part/R/C, rule.*                (shipped)
  requirements/  NEW  schema, elicitation checklist, gap analysis (CR-002)
  profile/       NEW  load a fab profile, generate .kicad_dru     (CR-006)
  parts/         resolver + cost model + ranking report           (CR-007)
  emit/        project.py, sch.py, pcb.py
  layout/      place.py, route.py
  check/       erc, drc, rules, parity, sim, errata registry
  fab/         deterministic output, vendor packaging
  render/      board and schematic images for the digital loop
  gate/          NEW  fab gate and approval records (CR-001/002/005)
  core/        kicad interop, result envelope, env, loader, build
  cli.py
```

## Milestones

### M2 — Hermetic environment (CR-004, CR-003)

First because it is the only milestone that gets more expensive with every
other one. Pinning a toolchain after three emitters assume `/usr/share/kicad`
is a retrofit.

- `flake.nix` pinning KiCad 10, its libraries, ngspice, java, freerouting,
  Python, and all Python packages.
- `core/kicad.py` stops hardcoding `/usr/share/kicad/{symbols,footprints,
  3dmodels,template}` (lines 37–40) and resolving `kicad-cli`, `ngspice`, and
  `java` off `PATH`. Values are injected, with the current constants as
  fallback so a non-Nix user is not locked out. `PCBKIT_PCBNEW_PYTHON` is
  already the seam for the awkward one.
- `doctor` inverts: from warning about drift to asserting the pin holds, and
  reporting which source supplied each tool.
- CI runs `nix run .#checks` — never a YAML reimplementation of the same steps.
- Licence check over the resolved dependency tree (CR-003).
- `vendor/` established with recorded hashes.

### M3 — Project scaffold and fabricator profiles (CR-005, CR-006)

- `pcbkit new` writes the project layout (`src/`, `findings/`, `release/`), a
  `.gitignore` excluding the generated ones, and the KiCad project files.
- `profiles/jlcpcb.yaml`: limits keyed by layer count and copper weight, dated,
  citing the vendor's published capabilities.
- `.kicad_dru` **generated** from the profile, never transcribed. Regenerating
  one that differs from disk is a finding, not a silent overwrite.
- `doctor --profile` lists published limits the profile does not yet encode, so
  a gap is tracked rather than silent.

### M4 — Parts resolver and cost model (CR-007, CR-003)

- Index the stock KiCad libraries first; `easyeda2kicad` only for what they lack.
- Resolution yields a complete `(symbol, footprint, 3d, lcsc, stock)` tuple or
  fails loudly (AGENTS.md rule 6).
- Ranked selection on availability, basic/extended classification, unit price at
  the stated quantity, and electrical fit — **with the ranking reported**.
- Stock margin `max(quantity x 10, 500)`, overridable.
- Basic-part substitution **suggested, never applied**, always with worst-case
  tolerance stated.
- Availability lookup is enrichment: a build succeeds offline from `vendor/`.

### M5 — Schematic emitter

Unchanged in substance; the M3 spike already settled the approach.

- `kicad-sch-api` as the writer, followed by a **mandatory**
  `kicad-cli sch upgrade` and a format-version assertion.
- One sheet per `@module`, hierarchical sheet pins for ports, power symbols
  rather than long rails, orthogonal wires.
- Acceptance is readability, judged on the exported PDF, not just a clean ERC.

### M6 — PCB emitter, placement, profile DRC (CR-006)

- `pcbnew` builds the board; stackup comes from the profile, not a constant.
- Placement in passes: locked parts to edges, module clustering, rule-driven
  local placement (decoupling to its pin, load caps to the crystal), then
  relaxation.
- **DRC runs against the generated `.kicad_dru` from the first build**, not at
  fab time. `fab.*` findings carry the limit, the measured value, and the
  profile that set it.

### M7 — Rule engine and checks

- IR-level electrical rules: decoupling, floating inputs, pull-ups, straps,
  voltage-domain compatibility, trace width vs. current, polarity.
- Each rule declares `id`, `severity`, `why`, and a suggested fix.
- ERC, DRC, and schematic parity normalised into the one `Finding` shape.
- ngspice DC-operating-point pass.
- **Errata registry** (CR-002): a `source: "bringup"` finding becomes a
  candidate rule, so a lesson paid for once applies to every future board.

### M8 — Requirements layer (CR-002)

Deliberately after the pipeline exists. Requirements *lower to* the DSL, so
building the pipeline DSL-first is not wasted work — this sits on top of it.

- `requirements.yaml` schema.
- Elicitation checklist as versioned data, including CR-007's `quantity`,
  `assembly.service`, `assembly.prefer_basic`, and `cost_target`.
- `pcbkit spec --check` reports gaps: `blocking: true` where no sensible default
  exists, otherwise a default with the assumption recorded visibly.
- Architecture selection from a library of known-good reference designs, saying
  which was chosen and why. Not synthesis.
- The inner return edge: findings that contradict a requirement name the field.

### M9 — Routing, render, fab, and the gate (CR-002, CR-004, CR-005)

- Route via freerouting; diff pairs and power widths from `NetClass`.
- Render board and schematic — these are what the digital loop *looks at*, not
  a nicety.
- Deterministic fab output: pinned toolchain plus `SOURCE_DATE_EPOCH`
  normalisation of `%TF.CreationDate`. Acceptance is a checked-in
  fab-package hash.
- **`pcbkit gate fab`**: refuses while any `fab.*` violation stands, requires
  every digital check in CR-002's table to have been produced, and reports the
  order's real cost and lead time from the vendor.
- Approval recorded in `docs/releases/<version>.md` (committed) naming the
  package hash; the package itself becomes a GitHub Release asset.

### M10 — Agent surface (CR-001)

- `docs/agent/workflow.md` as the canonical source; `skills/pcb-design/SKILL.md`
  and MCP tool descriptions are **generated adapters**, kept honest by
  `pcbkit docs sync --check`.
- `examples/blinky.py` as the CI smoke test, the USB-C MCU devboard as the
  worked exemplar.
- Per-agent behaviour evals — necessarily agent-specific, and stated as a
  deliberate exception to CR-001.

## Sequencing rationale

Ordered by retrofit cost, not by visible progress.

M2 first: every later milestone would otherwise bake in system paths. M3 next
because profiles-as-data underpins both the DRC in M6 and the assembly model in
M4. M4 before the emitters because a resolved part is the emitters' input. M5
and M6 are the pipeline. M7 judges what they produce. M8 sits on top of a
working pipeline. M9 closes the expensive loop. M10 packages it.

## Risks

| Risk | Mitigation |
|---|---|
| Nix pinning is a large up-front cost before visible output | It is bounded and mechanical, and `PCBKIT_PCBNEW_PYTHON` shows the seam already exists |
| Schematic readability | Unchanged: the acceptance gate is a human reading the exported PDF |
| Vendor profile drifts from published capabilities | Profiles are dated, declare coverage, and `doctor --profile` reports gaps |
| Autorouted result is fab-legal but poor | Profile DRC plus the rule engine; manual pre-routes survive |
| Requirements layer becomes a questionnaire | Only `blocking` gaps stop the loop; everything else defaults with a recorded assumption |
| Agent produces a plausible but non-working circuit | The residual risk. Rules, sim, reference architectures, and the errata registry narrow it; they do not remove it. Say so in the skill. |

## Verification

1. **Environment** — `nix flake check`; `nix run .#checks` from a clean checkout
   runs exactly what CI runs.
2. **IR** — DSL → IR → JSON → IR is identity. *(shipped)*
3. **Profile** — a 0.10 mm track produces `fab.track_width` naming the 0.127 mm
   limit and the profile; switching profiles changes findings with no code change.
4. **Parts** — every part in the exemplar resolves to a complete tuple with
   stock above margin; the build succeeds with networking disabled.
5. **Schematic** — `kicad-cli sch erc --exit-code-violations` exits 0, and a
   human reviews the exported PDF once per milestone.
6. **PCB** — `kicad-cli pcb drc --schematic-parity` exits 0. Parity failure is a
   build break: the emitters disagree.
7. **Rules** — golden tests where a hand-broken design trips exactly the
   expected rule id.
8. **Reproducibility** — building the exemplar twice yields an identical
   fab-package hash.
9. **Gate** — refuses without a complete digital checklist; a release records
   approval against the hash it emitted.
10. **Neutrality** — `tests/test_agent_neutral.py`. *(shipped)*

## Definition of done

From an empty directory:

```
pcbkit new devboard --profile jlcpcb
pcbkit spec --check          # answers what it can, asks what it must
pcbkit build && pcbkit check # ERC, profile DRC, rules, render
pcbkit gate fab              # refuses until the digital loop is exhausted
```

produces a fab package one upload away from an assembled order, a schematic a
hardware engineer can review, a committed approval record naming its hash, and
the same bytes on any machine that checks out the commit.
