# CR-005 — Specification

## The rule

If it can be regenerated deterministically from what is in the repository, it is
not committed. Otherwise it is an input, and it is.

| Category | Examples | Committed |
|---|---|---|
| Generated output | Gerbers, drill, CPL, PDF, SVG, 3D render, STEP, Nix results, `findings/`, `release/` | no |
| Vendored input | fetched LCSC symbols/footprints, freerouting jar, drawing sheets | yes |
| Fingerprint | fab-package hash, lockfiles | yes |
| Decision record | SDLC artifacts, approval records | yes |

Lockfiles and hashes are not outputs. They are the statements that make the
outputs reproducible, and dropping them would defeat CR-004.

## Where outputs go instead

- **Per-run**: CI artifact storage, retained by policy, referenced by run id.
- **Per-release**: a GitHub Release, holding the fab package and its hash.
- **Locally**: `build/`, `findings/`, and `release/` in the working tree,
  ignored.

## Splitting the approval record from its payload

The plan put an `approvals` block inside `release/<v>/manifest.json`. Under this
rule that file is generated and ignored, so an approval written there would not
survive.

Split it:

- `docs/releases/<version>.md` -- **committed**. Who approved, when, against
  which fab-package hash, and what they reviewed (schematic PDF, 3D render).
  This is a decision record and belongs beside the SDLC chain.
- The fab package itself -- **a GitHub Release asset**, identified by the hash
  the record cites.

The approval therefore references its payload by content, and the payload lives
where large binaries belong. A future `pcbkit gate fab` checks that a record
exists naming the hash of the package it is about to emit, which is a stronger
check than an inline block: it cannot be satisfied by regenerating the manifest.

## Scaffolding for user projects

The rule applies to projects built with the toolkit, and a user will not know
to apply it. `pcbkit new` writes a `.gitignore` covering `build/`, `findings/`,
`release/`, and the local cache, alongside the project layout.

`pcbkit fab` warns when it writes into a directory that is tracked by git and
not ignored -- catching the case where the project predates the scaffold.

## This repository

Already compliant; nothing regenerable is tracked. Two additions:

- `.gitignore` gains `findings/` and `release/` before either directory exists,
  since the cheapest moment to exclude a path is before anything writes to it.
- A test asserts no tracked file has a generated-output extension, so compliance
  does not depend on remembering.

## Out of scope

- Rewriting history. Nothing regenerable has ever been committed here.
- Retention policy for CI artifacts.
- Whether vendored inputs live in-tree or in git-lfs. Revisit if vendored data
  gets large; premature now.

## Acceptance

- A test fails if any tracked file is a generated output.
- `pcbkit new` produces a project whose `.gitignore` excludes `build/`,
  `findings/`, and `release/`.
- `pcbkit fab` warns when its output directory is tracked and not ignored.
- A release records approval in `docs/releases/<version>.md` citing a fab-package
  hash, with the package attached to a GitHub Release rather than committed.
