# CR-004 — Specification

## Testable definition

1. **`nix flake check` passes**, and the flake pins KiCad, KiCad libraries,
   ngspice, java, freerouting, Python, and all Python packages.
2. **No system paths in the package.** `/usr/share/kicad/...` and bare `PATH`
   lookups are replaced by values injected from the environment the flake
   constructs. Enforced by a test, alongside the CR-001 scans.
3. **Fab output is byte-identical across runs and machines** for the same
   commit, given `SOURCE_DATE_EPOCH`.
4. **CI runs flake apps.** No step in a workflow file reimplements what a
   developer runs locally.
5. **Externally fetched resources are vendored** with a recorded hash.

## Determinism of fab output

Byte-identical output needs both halves:

- **Pinned toolchain** -- the flake. Gerbers embed
  `%TF.GenerationSoftware,KiCad,Pcbnew,<exact build>`, so a KiCad change is a
  fab-output change by construction.
- **Normalised timestamps** -- `%TF.CreationDate` is the wall clock and differs
  between two plots seconds apart. pcbkit sets `SOURCE_DATE_EPOCH` from the
  commit and rewrites the field, the same convention reproducible-builds tooling
  uses elsewhere.

The acceptance test is a hash of the fab package, checked into the repo and
compared in CI. That single check subsumes most of this CR: it cannot pass if
the toolchain is unpinned or the timestamps float.

## Code changes required

`pcbkit/core/kicad.py` currently hardcodes four library paths and resolves three
executables off `PATH`. These become resolved values with the current constants
as fallback, so a non-Nix user is not locked out -- but the flake supplies them,
and `pcbkit doctor` reports which source was used.

`PCBKIT_PCBNEW_PYTHON` already exists and is exactly the seam the flake needs
for the pcbnew interpreter, which is the awkward one. The other paths follow the
same pattern.

## What happens to `pcbkit doctor`

Its role inverts: from *warning that the environment drifted* to *asserting the
pinned environment is active*. Inside a flake shell, the format-drift check
becomes a guard against a broken pin rather than an expected condition. Outside
one, doctor keeps working exactly as it does now -- the fallback path is
supported, just not reproducible, and doctor says so.

## Relationship to CR-003

Two halves of the same durability argument. CR-003 says the toolchain must be
software anyone can keep running; CR-004 says a specific version of it must be
recoverable years later. Vendoring serves both: CR-003 needs a build that works
with vendor services unreachable, CR-004 needs one that works after they change.

## Out of scope

- Requiring Nix to *use* pcbkit. `uv` and a system KiCad stay supported; they
  are simply not the reproducible path, and doctor reports the difference.
- Reproducing the 3D render or PDF exports bit-for-bit. Gerbers, drill files,
  BOM, and CPL are what get manufactured and what the hash covers.

## Acceptance

- `nix run .#checks` runs the same suite CI runs, from a clean checkout.
- Building the blinky example twice produces an identical fab-package hash.
- A test asserts no `/usr/` literals remain in `pcbkit/`.
- With networking disabled inside the flake shell, the example still builds.
