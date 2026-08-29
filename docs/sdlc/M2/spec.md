# M2 — Specification

## Deliverables

| Item | Responsibility |
|---|---|
| `flake.nix` / `flake.lock` | Pin KiCad, ngspice, JRE, freerouting, Python, uv by revision |
| `pcbkit/core/toolchain.py` | Resolve every external tool and library path through one place |
| `core/kicad.py` | Stop hardcoding `/usr/share/kicad` and bare `PATH` lookups |
| `core/env.py` | `doctor` reports provenance and asserts the pin |
| `tests/test_toolchain.py` | No `/usr/` literals; resolution order is honoured |
| `.github/workflows/checks.yml` | Runs `nix run .#checks`, nothing else |

## Resolution order

Every tool and library path resolves through `toolchain.py`, in this order:

1. an explicit `PCBKIT_*` environment variable;
2. the flake-provided value (`PCBKIT_TOOLCHAIN=nix` plus the injected paths);
3. `PATH` / the historical `/usr/share/kicad` constants, as fallback.

The fallback stays because locking a user out for not running Nix would be a
worse failure than being unpinned. What changes is that pcbkit knows which
happened and says so.

## `doctor` inverts

It stops warning about drift and starts reporting provenance. Each check gains
the source that supplied it, and a summary states whether the environment is
`pinned` or `unpinned`. The format-version check keeps working; inside a flake
it is a guard against a broken pin rather than an expected condition.

`pcbkit doctor --require-pinned` exits nonzero outside a pinned environment, for
CI use.

## CI

One workflow step: `nix run .#checks`. A developer runs the same command. A
second definition of the same steps in YAML is a second source of truth and
will diverge, which is the failure CR-004 names explicitly.

## Licence check (CR-003)

`nix run .#licences` walks the resolved dependency tree and fails on any
non-OSI licence. Absence of a stated licence is a failure, not a pass.

## Out of scope

- Packaging `kicad-sch-api` for nixpkgs. See the gap in `intent.md`.
- `SOURCE_DATE_EPOCH` normalisation of fab output — that is M9, since there is
  no fab output yet.
- Vendoring content. `vendor/` is established with its hash-recording
  convention; what goes in it arrives with M4.

## Acceptance

- `nix flake check` passes, and `flake.lock` pins nixpkgs by revision.
- Inside `nix develop`, `pcbkit doctor` reports `pinned` and names the store
  paths it used.
- Outside it, `pcbkit doctor` still passes and reports `unpinned`.
- `pcbkit doctor --require-pinned` exits 1 outside a flake shell.
- A test asserts no `/usr/` literal outside `toolchain.py`'s fallback table.
- `nix run .#checks` runs the same suite CI runs.
