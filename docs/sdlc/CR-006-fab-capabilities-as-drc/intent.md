# CR-006 — Manufacturing capabilities are design constraints

Raised: 2026-08-29. Source: [#5](https://github.com/BIOS9/agentic_pcb_toolkit/issues/5).
Status: proposed.

## Problem

Every fabricator has capability limits: minimum track width and spacing,
minimum via and hole size, annular ring, silkscreen thickness, edge clearance,
slot widths. A board that violates them is either rejected, silently "optimised"
by the fab into something the designer did not specify, or manufactured wrong.

KiCad's default design rules are not any fabricator's rules. Left alone, DRC
passes on a board the chosen fab cannot build.

The usual remedy is a hand-written `.kicad_dru` per project. An existing KiCad
project on this machine has exactly that: 133 lines of JLCPCB-derived custom
rules, carrying its own header comment pointing at the vendor's capabilities
page, and three `TODO` markers for rules the author knew were missing --
NPTH pad diameters, plated slot widths, non-plated slot widths.

That artifact makes the case:

- it is **hand-maintained**, so it drifts from the vendor's published limits;
- it is **incomplete**, and knowably so;
- it is **per-project**, so every new board either copies it or starts without;
- it is written for **KiCad 7**, so it also drifts from the tool.

Its rules are split by `(layer outer)` and `(layer inner)` with different
minimums (0.127 mm vs 0.09 mm), which shows the limits are not one flat list:
they depend on layer count and copper weight.

## Outcome

Every project pcbkit creates carries design rules matching its target
fabricator's published capabilities, generated rather than transcribed, and
verified by DRC from the first build.

## Why enforcement moves earlier

The plan treated fab rules as an M6 concern, applied when producing output.
That is too late. Under CR-002, a violation caught while iterating digitally
costs seconds; the same violation caught at order time costs a respin, and
caught by the fab's own optimiser it may never be reported at all.

Manufacturing limits are not a property of the output stage. They are
constraints on the design, and they belong in the loop that shapes it.

## Scope

Cross-cutting: touches project creation, the board emitter, the checks, and the
fab layer. Interacts with CR-003, which requires that choosing a default
fabricator must not make output unportable.
