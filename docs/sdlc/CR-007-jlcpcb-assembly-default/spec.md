# CR-007 — Specification

## Assembly profile

Extends the CR-006 fabricator profile with the assembly half, same file, same
data-not-code rule:

```yaml
assembly:
  service: standard          # economic | standard
  library: jlcpcb_assembly
  fees:
    extended_part_setup: 3.00    # per distinct extended part
    currency: USD
  economic_restrictions:
    sides: 1
    packages_excluded: [BGA, QFN_fine_pitch]
```

Fee figures are dated data, not constants in the code, for the same reason
capability limits are: they change, and a stale number with a date beats a
confident wrong one.

## Part selection becomes a cost decision

The M2 resolver returns a ranked list rather than a single answer, scoring on:

1. **availability** -- in the assembly library, in stock, with margin;
2. **classification** -- basic parts preferred at low volume, where one loading
   fee can exceed the entire remaining BOM;
3. **unit price at the stated quantity**;
4. **electrical fit** -- tolerance, voltage, package, temperature.

Ranking is reported, not hidden. `pcbkit parts pick` shows why the winner won,
because a silent substitution that changes cost or availability is exactly the
failure AGENTS.md rule 6 forbids.

### Stock margin

Stock must satisfy `stock >= max(quantity x margin, floor)`, defaulting to
`margin = 10` and `floor = 500`, both overridable. A part that only just covers
the build is a part that will be gone by order time.

## Basic-part substitution: reported, not automatic

Where an odd value is extended-only, pcbkit computes whether a series or
parallel combination of basic parts is cheaper once the loading fee is counted,
and reports it:

```
R7 = 4.87k  (C123456, extended, +$3.00 setup, $0.02/ea)
  alternative: 4.7k + 169R in series, both basic, $0.004/ea
  saving at qty 5: $3.02   tolerance: 1% -> 1.4% worst case
```

**Reported, not applied.** Automatic substitution changes the schematic's
topology to save money, and it trades tolerance, board area, and part count for
that saving. Whether it is worth it is a design decision, so it is surfaced with
its consequences and left to the author -- the same line CR-002 draws around
architecture synthesis.

The tolerance consequence must always be stated. Two 1% parts in series do not
give a 1% result.

## Elicitation fields

Added to the CR-002 checklist, not to a separate confirmation flow:

| Field | Why it changes the design | Default |
|---|---|---|
| `quantity` | decides whether loading fees dominate | 5, assumption recorded |
| `assembly.service` | restricts packages, sides, processes | standard |
| `assembly.prefer_basic` | trades part-count for fee avoidance | true under qty 100 |
| `cost_target` | enables the costed-BOM finding from CR-002 | none, reported only |

## Agent-facing knowledge

The ordering process, tier differences, and what the classifications mean go in
`docs/agent/workflow.md` -- the CR-001 source of truth -- so every agent gets
the same briefing and it is reviewable. Not in one agent's prompt.

## Out of scope

- Automatic substitution (above).
- Panelisation, and assembly of anything other than SMT.
- Multi-vendor cost comparison. One default profile, switchable.

## Acceptance

- A resolved part that is extended, or whose stock is under the margin, produces
  a finding before the fab gate rather than at order time.
- `pcbkit parts pick` reports the ranking and why the winner won.
- An extended-only odd resistor value produces a basic-substitution suggestion
  including its worst-case tolerance.
- Switching to a non-JLCPCB profile still emits complete, valid fab output.
