# CR-002 — Specification

## Two loops, nested

```
requirements.yaml --(gap analysis)--> questions --> answers
       |                                              |
       |  <-------------------------------------------+
       v
  architecture --> design source (.py) --> IR --> KiCad files
       ^                                            |
       |                                            v
       |    INNER LOOP (digital)          render, schematic PDF, ERC/DRC,
       |    seconds, free, unlimited      rules, dimensions, costed BOM
       |                                            |
       +--------- findings that change requirements -+
       ^                                            |
       |                                    ======= FAB GATE =======
       |                                    human reviews and approves
       |                                            |
       |    OUTER LOOP (physical)                   v
       |    weeks, real money, few         order -> assemble -> bring-up
       |                                            |
       +--------- errata, measured behaviour -------+
```

Four levels, each a lowering of the one above: **requirements -> design source
-> IR -> KiCad files**. The plan already had the bottom three; this adds the top
one and both return edges.

The two loops are not variants of one thing. A digital iteration costs seconds
and nothing; a physical one costs real money and one to several weeks and cannot
be undone. The fab gate is the boundary, and it is the only place in the toolkit
where cost changes by orders of magnitude in a single step.

## Requirements as data, not prose

`requirements.yaml` is machine-readable, because the gap analysis has to be a
program and not a vibe:

```yaml
purpose: "blink an LED once per second"
maturity: prototype          # prototype | production
power:   {source: usb_c, voltage: 5.0}
programming: null            # <- unanswered
enclosure: {max_mm: [30, 20], mounting: none}
quantity: 5
```

## Gap analysis is the testable part

`pcbkit spec --check` reports every field a build needs that the requirements do
not answer, each with why it matters and what happens by default.

```json
{"gaps": [
  {"field": "programming",
   "why": "an MCU with no programming interface cannot be flashed",
   "default": "expose SWD on a 4-pin header",
   "blocking": false},
  {"field": "power.source",
   "why": "determines connector, protection, and regulator topology",
   "blocking": true}
]}
```

`blocking: true` means no sensible default exists and a guess would be
unbuildable. Everything else has a default that is **recorded as an assumption**
in the spec, so the loop terminates and the author can see what was decided for
them.

This is the CR-001-compatible form of elicitation: the questions live in a
versioned checklist in the repo, and any agent -- or a human reading the JSON --
gets the same list.

## The inner return edge

After a build, findings that imply a requirement is wrong (board exceeds
`enclosure.max_mm`; BOM exceeds a cost target; no room for the stated connector)
are emitted with `source: "requirements"` and name the field they contradict.
That is what makes the loop a loop rather than a one-way pipeline.

## Exhausting the digital loop first

The digital loop's job is to surface everything a physical board would have
taught, before one is paid for. That is a checklist, not an aspiration, and the
gate reports which items were actually produced and seen:

| What a first board usually teaches | How it is caught digitally |
|---|---|
| connector faces the wrong way, parts collide | 3D render, top and bottom |
| does not fit the enclosure | dimension check against `enclosure.max_mm` |
| silkscreen unreadable or under a part | silkscreen-vs-mask check, render |
| wrong part, wrong footprint, wrong pinout | schematic PDF review, footprint-vs-datasheet check |
| costs more than expected | costed BOM against the stated target |
| a part is unbuyable | stock check at gate time, not design time |
| decoupling, pull-ups, trace width wrong | rule engine (M5) |

The measure of this toolkit is how few physical iterations a working board
takes. Anything routinely first discovered on a physical board is a gap in this
checklist and should become a new digital check.

## The outer return edge, and why it is different

Findings from a physical board are expensive lessons, and spending them only on
the design that produced them wastes most of their value.

They therefore feed back in two directions:

- into **this design's requirements**, like any other finding;
- into **the toolkit's rule engine**, as a candidate new rule, so no future
  board repeats the mistake.

Errata are recorded with `source: "bringup"` and are never silently discarded.
This is the Maintain stage of the SDLC chain closing back on pcbkit itself
rather than only on the project, which is the mechanism by which the toolkit
gets better at the thing it exists to do.

## Cost is stated, never implied

Before the gate, pcbkit reports the actual cost and lead time of the order it is
about to place -- from the vendor, not an estimate baked into the toolkit -- next
to the reminder that a digital iteration is free. The user must always be able
to see which loop an action puts them in.

## Decisions this changes

| Decision | Was | Becomes |
|---|---|---|
| Artifact chain as pcbkit's UX | deferred to v2 | core roadmap; it is the product |
| Entry point | `design.py` | `requirements.yaml`, with the DSL still fully supported |
| Elicitation | not in scope | versioned checklist + `pcbkit spec --check` |
| Iteration | one loop | two, split at the fab gate by cost |
| Rule engine | fixed rule set | grows from physical errata |

## Out of scope

- Automatic architecture *synthesis*. Proposing a topology from requirements is
  a separate, much harder problem. v1 proposes from a library of known-good
  reference architectures and says which one it picked and why.
- Cost and lead-time optimisation beyond reporting them.

## Acceptance

- `pcbkit spec --check` on a requirements file missing `power.source` reports it
  as blocking and exits 0 (findings are data).
- A requirements file with only `purpose` and `maturity` produces a complete
  spec with every default recorded as a visible assumption.
- A board exceeding `enclosure.max_mm` produces a finding naming that field.
- The blinky example builds from `requirements.yaml` without hand-written
  Python, and the existing DSL path still passes its tests unchanged.
- The fab gate refuses to proceed until every digital check in the table above
  has been produced, and reports the order's cost and lead time alongside them.
- An erratum recorded with `source: "bringup"` appears in the rule engine's
  candidate-rule list rather than only in the project's requirements.
