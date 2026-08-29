# M3 — Project scaffold and fabricator profiles

Implements [CR-006](../CR-006-fab-capabilities-as-drc/) and the scaffolding half
of [CR-005](../CR-005-no-build-artifacts/).

## Problem

KiCad's default design rules are nobody's fabricator's rules, so DRC passes on
boards the chosen fab cannot build. The usual remedy — a hand-written
`.kicad_dru` per project — was examined while raising CR-006, and it fails in
four ways at once: hand-maintained, so it drifts from the vendor; incomplete,
and knowably so; per-project, so every new board copies it or starts without;
and written against an older KiCad.

Separately, a user creating a project will not know to exclude `release/` and
`findings/` from git, and by the time the repository is unwieldy the history
already contains them.

Both are the same shape of problem: something correct that must be produced for
every project, which a human will get wrong or skip.

## Source material

The profile is derived from a real 133-line JLCPCB rule set found on this
machine, not from scraping a vendor page. That file supplies concrete limits —
0.127 mm outer track width, 0.09 mm inner, 0.075 mm annular ring, 0.5 mm
hole-to-hole across nets, 6.3 mm maximum hole — and, just as usefully, an honest
record of what its author could not pin down: NPTH pad margins, slot widths,
hole-to-edge distance, and an ambiguity in the vendor's own published figures
for minimum hole size.

Those become tracked coverage gaps rather than being lost again.

## Outcome

`pcbkit new` produces a project that is correct by construction: the right
directory layout, a `.gitignore` that excludes generated output, and design
rules generated from a dated fabricator profile rather than transcribed.

## Constraints

- The profile is **data**. A limit written into code is the bug CR-006 exists to
  prevent, and AGENTS.md rule 10 forbids it.
- Provenance must be honest. The profile records where its numbers came from and
  which limits it does not encode, because a confident-looking file with silent
  omissions is worse than one that admits them.
- Regenerating a `.kicad_dru` that differs from the one on disk is a finding,
  not a silent overwrite. That is how a stale rule set gets noticed.
