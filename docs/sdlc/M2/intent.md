# M2 — Hermetic environment

Implements [CR-004](../CR-004-reproducible-builds/) and the enforcement half of
[CR-003](../CR-003-open-source-only/).

## Problem

pcbkit pins its Python dependencies and takes everything else from the machine.
`core/kicad.py` hardcodes four `/usr/share/kicad` paths and resolves
`kicad-cli`, `ngspice`, and `java` off `PATH`, so a design's output is a
function of the machine that built it.

## Evidence found while scoping

Two probes, both confirming the problem is live rather than theoretical:

- The nixpkgs **flake** provides KiCad `10.0.5`; the nixpkgs **channel**
  (`<nixpkgs>`) on this same machine provides `9.0.7`. Two references that both
  look like "nixpkgs" already disagree by a major version. Pinning must be by
  revision, not by name.
- KiCad 10.0.5 in nixpkgs matches the system version exactly, so the format
  versions in `core/kicad.py` hold and no emitter work is invalidated. Had it
  been 9.0.7, `.kicad_sch` would have been `20250114` rather than `20260306`.

## Outcome

A developer and CI run byte-identical tools, obtained from a locked revision.
The fallback path -- system KiCad, no Nix -- keeps working, but reports itself
as unpinned rather than pretending otherwise.

## Why first

M2 produces nothing visible, and goes first anyway. It is the only milestone
that gets strictly more expensive with every milestone after it: four hardcoded
paths today, a retrofit through three emitters later.

## Known gap, stated rather than hidden

CR-004 says the flake pins "Python and its packages". `kicad-sch-api` is not in
nixpkgs, so Python packages stay locked by `uv.lock` -- hashed and exact, but
resolved from PyPI rather than the Nix store. The toolchain half is fully
hermetic; the Python half is pinned but not offline-installable.

This is a deliberate deviation from an accepted CR, recorded here rather than
silently taken. Closing it means either packaging `kicad-sch-api` as a
derivation or adopting a uv-to-Nix bridge, and neither should block M2.
