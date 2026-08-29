# CR-003 — Specification

## Testable definition

1. **Every runtime dependency carries an OSI-approved licence.** Checked over
   the resolved dependency tree, not the direct list, and enforced in CI.
2. **No build step requires a proprietary program.** KiCad, ngspice, and
   freerouting are all open source and already in use.
3. **Fab output uses published formats only** -- Gerber X2, Excellon, IPC-2581,
   ODB++, IPC-D-356. A vendor-specific package is a *layout* of these files,
   never a different format.
4. **No build fails when a vendor service is unreachable.** See below.

## Rulings on the boundary cases

**Vendor part data is an input, not a dependency.** Querying LCSC for stock and
pricing is allowed, because the alternative -- a hand-maintained parts database
-- is worse for the user and no more durable. But:

- a build must succeed offline from vendored data, so availability lookup is an
  *enrichment* step, never a build step;
- everything fetched is vendored into the repo (CR-004), so a design remains
  buildable after the service changes or disappears;
- fetched symbols, footprints, and 3D models are licence-checked before
  vendoring, and anything unclear is rejected rather than assumed permissive.

**Manufacturers are not software.** JLCPCB-first stays. What the constraint
forbids is output only JLCPCB can consume; the neutral formats above are always
emitted, and the vendor package is an arrangement of them.

**Copyright is not licence.** KiCad's own libraries are permissively licensed;
vendor-supplied models frequently are not. Absence of a stated licence is
treated as rejection.

## Current compliance

Already compliant. KiCad 10, ngspice, freerouting 2.3.0, and every Python
dependency are open source. The one item needing attention is the LCSC data
path, which is covered by the offline and vendoring rules above.

Recording it now costs nothing; discovering at M6 that a chosen router or part
database is proprietary would cost a milestone.

## Out of scope

- The operating system, and toolchains not in the requirements-to-Gerbers path.
- Requiring an open *fab*. Manufacturing is a service, and the open formats
  requirement is what preserves the ability to switch.

## Acceptance

- `pcbkit fab` output contains only published-format files, and a manifest
  naming the specification each conforms to.
- A licence check over the resolved dependency tree runs in CI and fails on any
  non-OSI licence.
- With networking disabled, building a design whose parts are vendored succeeds.
