# M1 — IR and capture DSL

## Problem

Every later layer needs one shared model of "what circuit is this". Without it,
the parts resolver, the emitters, the rule engine, and the placer each invent
their own, and a change in one silently disagrees with the others.

Agents also need to write circuits without a KiCad library present, and to see a
readable diff when they change one.

## Outcome

A typed IR that JSON round-trips losslessly, and a Python DSL thin enough that
capture records intent and resolves nothing.

## Constraints

- Capture must not require a symbol library. A missing part is the resolver's
  problem to report, not a reason the file will not load.
- Refdes assignment must be order-independent, or every unrelated edit renumbers
  a sheet and destroys diff review.
- Reusing a module must not short its internals together.
