# M3 spike — can `kicad-sch-api` write KiCad 10 schematics?

**Decision: yes, use it. Do not write our own S-expression writer.**

## The question

`kicad-sch-api` 0.5.x was released 2025-11-19, which predates the KiCad 10
schematic format (`20260306`). The plan flagged this as the project's
highest-risk unknown: if the library cannot produce files KiCad 10 accepts, the
schematic emitter has to be built from scratch on `sexpdata`.

## What was tested

Against KiCad 10.0.5 and `kicad-sch-api` 0.5.5.

**1. Round-tripping an existing KiCad 10 schematic.** Took the shipped
`STM32_Nucleo-64_Morpho` template, upgraded it to `20260306`, loaded and re-saved
it through the library.

- Loads and saves without error; 16 components preserved.
- `kicad-cli sch erc` on the result: exit 0.
- **Netlists are identical** — 72 nets, same name and same node membership.
- The 1425-line textual diff is formatting only: key ordering inside
  `stroke`/`pts` blocks, `(hide yes)` normalization, and dropped
  `(in_pos_files yes)` / `(body_style 1)` defaults.

**2. Generating a schematic from scratch.** This is the actual M3 use case.

- Components with `lib_id`, reference, value, and footprint: works.
- `get_component_pin_position`, `add_wire_between_pins`: works.
- `add_label`, `add_hierarchical_label`: works, and both serialize correctly.
- `add_sheet`: works. `add_sheet_pin(sheet, name, edge, position_along_edge)`
  needs the edge and offset explicitly — our placer supplies both anyway.
- Netlist export from the generated file resolves refs and footprints correctly.

## The one real catch

Generation emits the **KiCad 9 format** (`version 20250114`,
`generator_version "9.0"`), not `20260306`.

KiCad 10 reads it anyway — ERC and netlist export both succeed on the raw
output. But the emitter must not leave it there, because the rest of the toolkit
pins `20260306`.

**Required step:** run `kicad-cli sch upgrade` on every generated schematic.
Verified: exit 0, header becomes `20260306` / `10.0`, ERC still clean, and the
netlist is unchanged across the upgrade.

## Consequences for M3

- Depend on `kicad-sch-api>=0.5.5`.
- The emitter's last step is a mandatory `kicad-cli sch upgrade` pass, followed
  by a format-version assertion so a library change cannot silently regress it.
- We still own placement and wire routing entirely; the library is a writer, not
  a layout engine. The readability acceptance gate is unchanged.
- `Schematic.get_statistics()` under-reports labels it has actually stored.
  Do not use it for verification -- assert against the written file.
