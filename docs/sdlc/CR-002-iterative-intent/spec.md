# CR-002 — Specification

## The loop

```
requirements.yaml  --(gap analysis)-->  questions for the author
       |                                        |
       |  <-------------- answers --------------+
       v
  architecture proposal  -->  design source (.py)  -->  IR  -->  KiCad
       ^                                                          |
       |                                                          v
       +---------------- findings that change requirements <-- built board
```

Four levels, each a lowering of the one above: **requirements -> design source
-> IR -> KiCad files**. The plan already had the bottom three; this adds the top
one and the return edge.

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

## The return edge

After a build, findings that imply a requirement is wrong (board exceeds
`enclosure.max_mm`; BOM exceeds a cost target; no room for the stated connector)
are emitted with `source: "requirements"` and name the field they contradict.
That is what makes the loop a loop rather than a one-way pipeline.

## Decisions this changes

| Decision | Was | Becomes |
|---|---|---|
| Artifact chain as pcbkit's UX | deferred to v2 | core roadmap; it is the product |
| Entry point | `design.py` | `requirements.yaml`, with the DSL still fully supported |
| Elicitation | not in scope | versioned checklist + `pcbkit spec --check` |

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
