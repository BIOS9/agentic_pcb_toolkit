# M1 — Specification

## Modules

| Module | Responsibility |
|---|---|
| `pcbkit/ir/models.py` | `Design`, `Component`, `Net`, `NetClass`, `Constraint`, `ModuleInfo`, `Board` |
| `pcbkit/dsl/capture.py` | Capture state and the author-facing handles |
| `pcbkit/dsl/__init__.py` | `@design`, `@module`, `Net`/`Power`/`Gnd`, `Part`/`R`/`C`/..., `rule` |
| `pcbkit/core/loader.py` | Import a design file, find its `Design` objects |
| `pcbkit/core/build.py` | Structural validation, IR emission |

## Design decisions

**Flat collections, path-tagged.** Emitters, the rule engine, and the placer
iterate components and nets globally far more often than they walk a hierarchy.
`path` preserves the hierarchy for the passes that need it (schematic sheets,
placement clusters) without forcing a tree traversal on the ones that do not.

**`uid` and `ref` are separate.** `uid` is assigned at capture and never
changes; `ref` comes from the annotation pass, which sorts by
`(path, prefix, uid)` rather than capture order. Re-annotating therefore cannot
rewire a design, and an edit in one module cannot renumber another.

**Power and ground are global by construction.** `Net._power_and_ground_are_global`
forces it. Threading rails through every module port is the largest source of
noise in code-defined schematics.

**Local net names are scope-qualified on collision.** Two instances of the same
module both declaring `Net("MID")` get separate nets, the second qualified as
`stage_2/MID`. Silently merging them would short two sheets together.

**Capture resolves nothing.** `part`, `lcsc`, and `mpn` are requests. The
resolver turns them into a symbol/footprint/3D triple or fails loudly
(AGENTS.md #6).

## Structural validation

Only what is wrong regardless of circuit intent: `ir.unconnected_component`,
`ir.single_node_net`, `ir.empty_net`, `ir.duplicate_refdes`, `ir.unannotated`,
`ir.dangling_reference`. Electrical judgement is the M5 rule engine's job.

## Acceptance

- `Design` JSON round-trip is identity, and re-dumping is stable.
- Two instances of one module share rails but not local nets.
- `uv run pcbkit build examples/blinky.py` reports 10 components, 8 nets, no findings.
- A broken design still exits 0; `--strict` exits 1.
