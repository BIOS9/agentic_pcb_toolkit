# pcbkit

An agent-driven PCB design toolkit. Describe a circuit in Python; get a
human-reviewable KiCad schematic, a routed board, verification findings, and a
fab-ready manufacturing package.

```console
$ pcbkit doctor --text
$ pcbkit build examples/blinky.py
$ pcbkit check
$ pcbkit fab --vendor jlcpcb
```

## Status

Under construction. M0 (environment guard) and M1 (IR + capture DSL) are
implemented; see
`docs/sdlc/` for the milestone artifacts and the repository plan for scope.

## Requirements

- KiCad >= 10.0 with `kicad-cli` and the `pcbnew` Python module
- Python >= 3.12
- Optional: `ngspice` (simulation), `java` (freerouting autorouter)

Run `pcbkit doctor --text` to check all of the above.

## The output contract

Every command prints one JSON object to stdout, logs to stderr, and exits
nonzero only when a *tool* failed. Design violations come back as `findings`
inside a successful envelope, so an agent reads them instead of parsing a
traceback.
