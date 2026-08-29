# M4 — Parts resolver and cost model

Implements [CR-007](../CR-007-jlcpcb-assembly-default/) and the offline half of
[CR-003](../CR-003-open-source-only/).

## Problem

M1 lets an author write `Part("AMS1117-3.3", lcsc="C6186")`. Nothing yet turns
that request into something orderable. Under CR-007 the target is an *assembled*
JLCPCB board, which changes what a valid part is:

- it must exist in the assembler's library, not merely be purchasable;
- it must be in stock now, with margin to survive the delay before ordering;
- it carries a basic or extended classification, and the per-part loading fee on
  extended parts dominates cost at low volume.

A design ignoring this is unorderable, or quietly costs several times what it
should. Picking a part because it was the first search hit can add a setup fee
larger than the rest of the board.

## What the data actually supports

Probed before designing, rather than assumed. One EasyEDA component call for
`C6186` returns, in a single response: manufacturer part number, manufacturer,
LCSC number, unit price, live stock, minimum and step order quantity, package,
the symbol and footprint payloads — and `"JLCPCB Part Class": "Basic Part"`.

So classification, availability, and cost are all obtainable together. The cost
model does not need a second source.

## The constraint that shapes the design

CR-003 rules that vendor data is an **input, not a dependency**: a build must
succeed with the service unreachable. That inverts the obvious architecture.
The cache is not an optimisation over the network — the cache is the source of
truth, and the network is how it gets populated.

A part already resolved must keep resolving in three years when EasyEDA has
changed its API, which is the same argument CR-004 makes for the toolchain and
M3 makes for copying the profile into the project.

## Outcome

A part request resolves to a complete, orderable tuple or fails loudly. Where
several candidates fit, the choice is a ranked cost decision and the ranking is
reported — never a silent substitution (AGENTS.md rule 6).
