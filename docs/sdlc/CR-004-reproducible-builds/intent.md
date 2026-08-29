# CR-004 — Hermetic, reproducible builds

Raised: 2026-08-29. Source: [#3](https://github.com/BIOS9/agentic_pcb_toolkit/issues/3).
Status: proposed.

## Problem

pcbkit currently pins its Python dependencies with a `uv.lock` and takes
everything else from whatever is installed on the machine: KiCad, its symbol and
footprint libraries, ngspice, java. `pcbkit/core/kicad.py` hardcodes
`/usr/share/kicad/{symbols,footprints,3dmodels,template}` and resolves
`kicad-cli`, `ngspice`, and `java` off `PATH`.

That makes a design's output a function of the machine that built it. Concretely:

- A developer on KiCad 9 and CI on KiCad 10 can produce different boards from
  the same source. The failure mode is not a clean error -- it is a board that
  builds and is subtly wrong.
- A design revisited in three years may be unbuildable, because the library it
  referenced moved, changed, or vanished.
- Two developers cannot reliably reproduce each other's results.

M0's format-drift check is the tell. `pcbkit doctor` detects that the installed
KiCad writes a different file format than pcbkit targets -- a warning about a
problem that should not be possible. Detecting drift is a symptom of an
unpinned environment; the fix is to make drift unrepresentable.

## Evidence

Verified on this machine, KiCad 10.0.5:

- Plotting the same board twice produces Gerbers that differ, because each plot
  stamps `%TF.CreationDate` with the wall clock.
- Every Gerber embeds `%TF.GenerationSoftware,KiCad,Pcbnew,10.0.5-1-g226df246f3`
  -- the exact build. Good provenance, and proof that output is a function of
  the toolchain version.

So even with a pinned toolchain, identical output needs the timestamp
normalised. Both halves are required.

## Outcome

A given design and a given commit produce the same fab output on any machine,
today or in three years. CI runs the same tools a developer runs, because they
are the same closure -- not a parallel definition that drifts.

## Approach

Nix flakes for hard version locking of everything: KiCad, its libraries,
ngspice, java, freerouting, Python and its packages. Vendoring in-repo for
resources Nix cannot durably track -- fetched LCSC symbols and footprints,
the freerouting jar, anything from a service that can disappear (see CR-003).

CI invokes flake apps (`nix run .#checks`), never a GitHub-Actions-specific
reimplementation of the same steps in YAML. A parallel CI definition is a second
source of truth and will diverge.

## Scope

Cross-cutting and permanent. Restructures how M0 verifies the environment,
changes the library path handling in `core/kicad.py`, and adds a determinism
requirement to M6's fab output. Does not change the IR, the DSL, or the checks.
