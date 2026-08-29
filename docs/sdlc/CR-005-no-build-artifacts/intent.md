# CR-005 — Build artifacts do not belong in git

Raised: 2026-08-29. Source: [#4](https://github.com/BIOS9/agentic_pcb_toolkit/issues/4).
Status: **accepted** 2026-08-29.

## Problem

Gerbers, drill files, schematic PDFs, SVGs, 3D renders, and Nix build results
are all regenerable. Committing them makes a repository large and cluttered,
and muddies what the repository is actually for: a Gerber in git invites the
question of whether it or the design is authoritative.

The rule applies in two places, and the second is the one that needs work:

1. **This repository.** Currently compliant -- nothing regenerable is tracked
   and `.git` is under a megabyte.
2. **Every project built with pcbkit.** A user will not know to exclude
   `release/` and `findings/`, and by the time the repo is unwieldy the history
   already contains the artifacts. The toolkit has to get this right on their
   behalf, at project creation.

## Why this is a change, not just a rule

Two approved decisions conflict with it.

The plan fixes a project layout of `src/`, `findings/`, and `release/<version>/`
"from day one", and has checks persist findings to `findings/*.json` as the
substrate a future gate reads. Both directories hold generated output, so both
must be excluded -- which is fine for the gate, since it reads them within a
single run.

Harder: the plan puts an `approvals` block inside
`release/<v>/manifest.json`, and CR-004 adds a checked-in hash of the fab
package. An approval is a durable decision that must outlive the run; a
manifest sitting in an ignored directory cannot carry one.

## The distinction that has to be written down

Three things look alike and are not:

- **Generated outputs** -- Gerbers, PDFs, renders, Nix results. Regenerable from
  the repository. Never committed.
- **Vendored inputs** -- fetched LCSC symbols and footprints, the freerouting
  jar. *Not* regenerable from the repository; that is precisely why CR-004
  vendors them. They are inputs that happen to have been downloaded, and they
  are committed.
- **Fingerprints of outputs** -- the fab-package hash from CR-004. Not the
  artifact, and the thing that makes committing the artifact unnecessary.

Deciding question: **can this be regenerated deterministically from what is in
the repository?** Yes means it does not belong in git. No means it is an input.

## Outcome

Nothing regenerable is tracked, in this repository or in any project pcbkit
creates. Run outputs go to CI artifact storage; released outputs go to GitHub
Releases. Decisions about those outputs stay in the repository, separated from
the outputs themselves.

## Scope

Cross-cutting and permanent. Changes the plan's project layout and the v2
approvals design, and adds a scaffolding responsibility to `pcbkit new`.
Depends on CR-004: "regenerable" is only a safe standard if regeneration is
actually deterministic.
