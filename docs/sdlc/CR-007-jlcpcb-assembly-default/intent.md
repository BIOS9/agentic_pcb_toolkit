# CR-007 — Assembled JLCPCB order is the default target

Raised: 2026-08-29. Source: [#6](https://github.com/BIOS9/agentic_pcb_toolkit/issues/6).
Status: **accepted** 2026-08-29.

## Problem

The plan chose JLCPCB-first for fab output, but left the *assembly* assumption
implicit. That gap matters more than it sounds, because assembly changes what
counts as a valid design:

- a part must exist in the assembler's own library, not merely be purchasable;
- it must be in stock now, with enough margin to survive the delay between
  design and order;
- it carries a **basic or extended** classification, and extended parts add a
  per-part loading fee that dominates cost at low volume;
- the service tier (economic vs standard) restricts which parts and processes
  are available at all.

A design that ignores this is not slightly suboptimal -- it is unorderable, or
it quietly costs several times what it should. Choosing a 0.1% resistor because
it was the first hit can add a loading fee larger than the rest of the board.

The cost structure also creates an option that has no analogue in hand design:
when an odd value is only available as an extended part, two or three basic
parts in series or parallel can be **cheaper than the single correct part**.
That is a real trade the toolkit is well placed to spot and a human rarely
bothers to.

## Outcome

pcbkit designs for an assembled JLCPCB order by default: parts come from the
assembly library, stock is checked with margin, and basic/extended
classification and loading fees are first-class inputs to part selection rather
than discovered at checkout.

## What must be asked, not assumed

Volume, service tier, and cost sensitivity change which design is correct, and
none of them are inferable from a schematic. They are elicitation fields under
CR-002 -- not a separate confirmation mechanism invented here. One place where
the toolkit asks the user things, not two.

## The boundary this must respect

CR-003 permits a default fabricator but forbids output only that fabricator can
read. "Assume JLCPCB" therefore means **default profile**, not hardcoded vendor.
A design must remain buildable elsewhere, with a worse part-selection experience
but no data loss.

## Scope

Cross-cutting: shapes M2 part resolution, adds fields to CR-002's elicitation
checklist, and extends the fab layer. Depends on CR-006 for the profile
mechanism.
