# M3 — Specification

## Deliverables

| Item | Responsibility |
|---|---|
| `pcbkit/profile/models.py` | `Profile`, `Process`, `Limits`, `Gap` |
| `pcbkit/profile/loader.py` | Load and validate a profile by name or path |
| `pcbkit/profile/dru.py` | Generate `.kicad_dru` from a selected process |
| `profiles/jlcpcb.yaml` | The default profile, dated and sourced |
| `pcbkit/core/scaffold.py` | `pcbkit new` |
| CLI | `pcbkit new`, `pcbkit profile` |

## Profile shape

Limits are keyed by process — layer count and copper weight — because the
observed rules already differ between outer copper (0.127 mm) and inner
(0.09 mm). A flat list would be wrong on any board that is not two layers.

Every profile carries `source`, `retrieved`, and `derived_from`, plus an
explicit `gaps` list. A gap names what is not encoded and why, so an omission is
tracked rather than silent.

## Generated project

```
myboard/
  src/                  design source                     committed
  profiles/             pinned copy of the profile used   committed
  myboard.kicad_dru     generated from the profile        ignored
  findings/             check output                      ignored
  release/              fab packages                      ignored
  .gitignore            excludes the three above
```

The profile is **copied into the project**, not referenced. A board built two
years from now must regenerate the same rules, which means the profile travels
with it — the same argument CR-004 makes for the toolchain.

## Commands

- `pcbkit new NAME [--profile jlcpcb] [--layers 2]` — scaffold a project.
- `pcbkit profile show [--profile P]` — the resolved limits for a process.
- `pcbkit profile check PROJECT` — regenerate and compare; a difference is a
  finding naming what changed.
- `pcbkit profile gaps` — limits the profile does not encode.

## Out of scope

- Assembly-side data. That is CR-007 and arrives with M4.
- Running DRC against the generated rules — there is no board emitter until M6.
  M3 produces the rules; M6 enforces them.
- Scraping vendor capability pages. Profiles are hand-authored and dated; a
  wrong scrape is worse than a stale file that says when it was written.

## Acceptance

- `pcbkit new demo` produces the layout above, and its `.gitignore` excludes
  `findings/`, `release/`, and the generated `.kicad_dru`.
- The generated `.kicad_dru` carries a header naming the profile, its
  `retrieved` date, and the pcbkit version.
- `pcbkit profile check` reports a finding when the file on disk is stale, and
  does not overwrite it.
- `pcbkit profile gaps` lists the limits carried over as unencoded.
- A test asserts no limit value appears in Python source (AGENTS.md rule 10).
