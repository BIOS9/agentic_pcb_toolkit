# M4 — Specification

## Modules

| Module | Responsibility |
|---|---|
| `parts/models.py` | `PartRequest`, `Candidate`, `Sourcing`, `Classification` |
| `parts/index.py` | Local KiCad symbol and footprint index. No network. |
| `parts/cache.py` | Vendored part data. The source of truth. |
| `parts/lcsc.py` | EasyEDA client. Populates the cache; never on the build path. |
| `parts/cost.py` | Ranking, stock margin, loading fees, substitution suggestions |
| `parts/resolver.py` | Request in, complete tuple or loud failure out |

## Offline is the default, not a mode

```
resolve(request)
  -> cache hit?            yes -> done, no network touched
  -> offline or no network -> findings: what is missing and how to fetch it
  -> fetch, validate, write to cache, done
```

`pcbkit parts fetch` is the only command that requires the network. `build` and
`check` never do. A cache miss during a build is a *finding* naming the part and
the command to run, not a stall on a socket.

## Completeness or nothing

A resolved part yields `(symbol, footprint, model_3d, lcsc, stock, price,
classification)`. A missing element fails loudly with a finding. Guessing a
footprint produces a board that fails at assembly, after the money is spent
(AGENTS.md rule 6).

## Ranking

Candidates are scored, and the score is reported:

1. **availability** — in the assembly library, in stock above margin
2. **classification** — basic preferred below the volume where the loading fee
   stops dominating
3. **unit price** at the stated quantity
4. **electrical fit** — tolerance, voltage, package

Stock margin: `stock >= max(quantity x margin, floor)`, defaulting to
`margin = 10`, `floor = 500`. A part that only just covers the build will be
gone by order time.

## Basic-part substitution: reported, never applied

Where an odd value is extended-only, the cost of a series or parallel
combination of basic parts is computed against the single part plus its loading
fee, and reported with its **worst-case tolerance**:

```
R7 = 4.87k  (C123456, extended, +$3.00 setup, $0.02/ea)
  alternative: 4.7k + 169R in series, both basic
  saving at qty 5: $3.02      tolerance: 1% -> 1.4% worst case
```

Never applied automatically. Substitution changes schematic topology to save
money, trading tolerance, board area, and part count — a design decision, the
same line CR-002 draws around architecture synthesis. Two 1% parts in series do
not give a 1% result, and the spec requires that consequence always be stated.

## Commands

- `pcbkit parts pick QUERY` — ranked candidates with the reasoning shown.
- `pcbkit parts fetch LCSC...` — populate the cache. The only networked verb.
- `pcbkit parts resolve DESIGN` — resolve every part in a design; report gaps.
- `pcbkit parts index` — what the local KiCad libraries contain.

## Out of scope

- Automatic substitution (above).
- Multi-vendor comparison. One default profile, switchable, per CR-003.
- Symbol and footprint *generation* from EasyEDA payloads. M4 records that the
  payload exists and caches it; converting it to KiCad format is M5/M6 work,
  where there is something to place it into.

## Acceptance

- A design whose parts are cached builds with networking disabled.
- A cache miss produces a finding naming the part and the fetch command, not a
  network call during `build`.
- An extended part, or stock below margin, produces a finding before the gate.
- `pcbkit parts pick` reports why the winner won.
- An extended-only odd resistor value produces a substitution suggestion
  including worst-case tolerance.
- No part resolves partially: incomplete is a failure, not a warning.
