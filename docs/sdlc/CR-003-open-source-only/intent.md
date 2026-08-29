# CR-003 — Open-source toolchain only

Raised: 2026-08-29. Source: [#2](https://github.com/BIOS9/agentic_pcb_toolkit/issues/2).
Status: proposed.

## Problem

A board is a long-lived artifact. It gets revised years after it is designed,
often by someone else. If any step between requirements and Gerbers depends on
software that can be discontinued, relicensed, or priced out of reach, the
design stops being maintainable at that moment -- and the failure is silent
until someone tries to open it.

KiCad is the sustainable choice: open, widely used, and with an active
ecosystem. The toolkit already builds on it, so this CR is mostly about writing
the constraint down before something proprietary creeps in, and about settling
the boundary cases that will otherwise be decided ad hoc.

## Outcome

Every piece of software in the path from requirements to fab output is
open source. A user can build, modify, and re-manufacture a pcbkit design
indefinitely without a licence.

## The boundary cases

The principle is easy; its edges are where it actually bites, and leaving them
undecided means they get decided by whoever hits them first:

- **Vendor part data.** `easyeda2kicad` is open source, but the LCSC/EasyEDA
  service it reads is proprietary and can change or vanish. The software is
  compliant; the dependency is not durable.
- **Fab houses.** JLCPCB is a manufacturer, not software. Choosing it does not
  make the toolchain proprietary -- but emitting output only it can read would.
- **Output formats.** Gerber X2, Excellon, IPC-2581, and ODB++ are published
  specifications. Depending on a vendor's undocumented format would not be.
- **Symbols, footprints, 3D models** fetched from vendor sites carry their own
  licences, which are frequently not open.

## Scope

Cross-cutting and permanent. Constrains M2 (parts), M6 (routing and fab), and
every future dependency choice. Interacts closely with CR-004, which supplies
the mechanism for the durability half of this.
