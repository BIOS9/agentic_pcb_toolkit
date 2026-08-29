# CR-002 — Requirements, not source code, are the entry point

Raised: 2026-08-29. Source: [#1](https://github.com/BIOS9/agentic_pcb_toolkit/issues/1).
Status: proposed.

## Problem

The approved plan makes `examples/blinky.py` the way a design begins. That
assumes the author already knows they need a 100nF bypass cap on pin 5 of the
555, a series resistor sized for the LED, and a bulk cap on the input rail.

Someone who wants a light that blinks once a second knows none of that, and
should not have to. The gap between what they want and a buildable design is
filled by expertise they do not have -- which is the actual problem this toolkit
exists to solve.

Three things follow, none of which the plan covers:

1. **The entry point is a statement of intent**, not a netlist.
2. **The toolkit must elicit what the author left out.** Prototype or product?
   What powers it? How is it programmed? Size and shape limits? Quantity? Those
   questions have a knowable, finite shape, and asking them badly (or not at
   all) is how a board gets built that cannot be used.
3. **Requirements change once the first board exists.** The first iteration
   reveals constraints nobody stated -- it does not fit, it costs too much, the
   connector faces the wrong way. That discovery must flow back into the
   requirements and go round again, not be patched into the design source.

## Outcome

An author states intent; pcbkit reports what is unanswered; the author (or an
agent on their behalf) answers; pcbkit proposes an architecture and builds it.
Findings from the built board feed back into the requirements and the loop
repeats.

The Python DSL does not go away -- it becomes the level an expert drops down to,
and the lowering target for everything above it.

## Why this is a change, not an addition

The plan explicitly deferred pcbkit's own `intent -> spec -> plan` chain to v2,
keeping v1 as a plain `build`/`check`/`fab` CLI. This issue says that chain is
not packaging around the product; it **is** the product. That reverses a
decision, so it is filed as a CR rather than a new milestone.

## Constraints

- Elicitation must live in the toolkit, not in an agent's head. A checklist that
  only exists inside one agent's prompt violates CR-001 rule 7 and cannot be
  reviewed, versioned, or tested.
- The loop must terminate. "Ask the user everything" is as bad as asking
  nothing; unanswered items need defaults and a recorded assumption.
- Dropping straight to the DSL must stay fully supported. Requirements are a
  layer above it, not a gate in front of it.

## Scope

Adds a stage ahead of M1 and reshapes M7. Pulls the deferred v2 chain into the
main roadmap. Does not change the IR, the emitters, or the checks.
