# CR-006 — Specification

## Capabilities are data, not code

A fabricator profile is a versioned data file, not logic embedded in the
emitter:

```yaml
# profiles/jlcpcb.yaml
vendor: JLCPCB
source: https://jlcpcb.com/capabilities/pcb-capabilities
retrieved: 2026-08-29
process:
  layers: 2
  copper_oz: 1.0
limits:
  track_width_mm:    {outer: 0.127, inner: 0.09}
  track_spacing_mm:  {outer: 0.127, inner: 0.09}
  via_diameter_mm:   0.45
  via_drill_mm:      0.3
  annular_ring_mm:   0.075
  silk_thickness_mm: 0.15
  silk_height_mm:    1.0
  pad_to_silk_mm:    0.15
  edge_clearance_mm: 0.3
  npth_pad_margin_mm: 0.4
  slot_width_mm:     {plated: 0.5, unplated: 1.0}
```

Keying limits by layer count and copper weight is required, not a refinement:
the observed real-world rules already differ between outer and inner copper.

This is also what satisfies CR-003. JLCPCB is the **default profile**, not a
hardcoded assumption. Another fabricator is another file, and the neutral output
formats stay unchanged, so choosing a default never locks a design to one vendor.

## Generation, not transcription

`pcbkit new` writes `<project>.kicad_dru` from the active profile, with a header
naming the profile, its `retrieved` date, and the pcbkit version. The file is a
**generated output** under CR-005 and is therefore not committed by the user;
it is reproduced from the profile, which is.

Regenerating a `.kicad_dru` that differs from the one on disk is a finding, not
a silent overwrite -- that is how a stale rule set gets noticed.

## Verification from the first build

`pcbkit check` runs `kicad-cli pcb drc` against the generated rules on every
build, not at fab time. Violations are findings like any other, carrying the
limit, the measured value, and the profile that set it:

```json
{"source": "drc", "code": "fab.track_width",
 "message": "track 0.10mm is below JLCPCB minimum 0.127mm for outer layers",
 "nets": ["VBUS"], "location_mm": [31.2, 14.8],
 "fix": "widen to at least 0.127mm, or move to an inner layer"}
```

`pcbkit fab` refuses to emit a package while any `fab.*` violation stands. That
is the one place the check is a gate rather than a report, because past it the
cost is real.

## Completeness is tracked, not assumed

The observed hand-written file was incomplete and knew it. A profile therefore
declares which limits it covers, and `pcbkit doctor --profile` lists limits the
vendor publishes that the profile does not yet encode. An unencoded limit is a
known gap rather than a silent omission.

## Out of scope

- Scraping vendor capability pages. Profiles are hand-authored from published
  documentation and dated; automatic retrieval is a separate problem, and a
  wrong scrape is worse than a stale file with a date on it.
- Panelisation and assembly-side rules. Those belong to CR-007.

## Acceptance

- `pcbkit new` produces a project whose `.kicad_dru` derives from the profile,
  and whose DRC uses it rather than KiCad defaults.
- A board with a 0.10 mm track produces a `fab.track_width` finding naming the
  0.127 mm limit and the profile.
- `pcbkit fab` refuses to emit while a `fab.*` violation stands.
- Regenerating a stale `.kicad_dru` reports a finding rather than overwriting.
- Switching profiles changes the rules and the findings, with no code change.
