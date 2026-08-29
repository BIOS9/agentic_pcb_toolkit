# M0 — Specification

## Deliverables

| Module | Responsibility |
|---|---|
| `pcbkit/core/kicad.py` | Pinned format versions, `run()`, `run_pcbnew()`, interpreter resolution |
| `pcbkit/core/result.py` | `Envelope` and `Finding` — the CLI output contract |
| `pcbkit/core/env.py` | The `doctor()` checks |
| `pcbkit/cli.py` | `pcbkit doctor [--strict] [--text]` |

## Checks

`python`, `kicad-cli` (>= 10.0.0), `pcbnew`, `symbols`, `footprints`,
`3dmodels`, `pcb-format`, `ngspice`, `java`, `freerouting`.

The last three are warnings, not failures: they are needed at M5/M6, and
blocking M1 work on them would be wrong.

`pcb-format` asks `pcbnew` to write a probe board and compares its version
token against the pin — that is what catches a KiCad upgrade before it breaks an
emitter three milestones downstream.

## Findings schema

One shape for ERC, DRC, the rule engine, and the simulator:

```
{source, code, severity, message, refs[], nets[], location_mm, layer, fix}
```

`fix` is what makes a finding actionable for an agent rather than merely true.

## Verified environment (KiCad 10.0.5 on this machine)

| File | Version | Generator |
|---|---|---|
| `.kicad_pcb` | `20260206` | `pcbnew` / `10.0` |
| `.kicad_sch` | `20260306` | `eeschema` / `10.0` |
| `.kicad_sym` | `20251024` | — |
| `.kicad_mod` | `20260206` | — |

Copper layer ids: `F.Cu = 0`, `B.Cu = 2` (renumbered in KiCad 10).

Libraries: 223 symbol libs, 155 `.pretty` footprint libs, 105 3D model dirs
under `/usr/share/kicad`.

## Consequence for M3

`kicad-sch-api` 0.5.6 was released 2025-11-19, which predates the `20260306`
schematic format. The M3 spike must therefore round-trip a KiCad 10 schematic
before we commit to that library; `kicad-cli sch upgrade` is the fallback path
if we emit an older format we understand well.

## Acceptance

- `uv run pcbkit doctor --text` reports a ready environment.
- `uv run pcbkit doctor` emits exactly one parseable JSON object.
- A broken environment exits 0 without `--strict` and 1 with it.
- `uv run pytest` is green.
