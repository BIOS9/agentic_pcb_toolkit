"""pcbkit command line.

Thin argv shell over pcbkit.core. Each verb builds an Envelope and emits it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pcbkit import __version__
from pcbkit.core.build import build
from pcbkit.core.env import Status, doctor
from pcbkit.core.licences import audit
from pcbkit.core.scaffold import (
    check_design_rules,
    new_project,
    regenerate_design_rules,
)
from pcbkit.profile import DEFAULT_PROFILE, ProfileError, available, load
from pcbkit.profile.dru import render
from pcbkit.core.result import Envelope


def _render_text(envelope: Envelope) -> None:
    """Human-readable rendering. The JSON on stdout stays the machine contract."""
    checks = envelope.data.get("checks", [])
    glyph = {Status.OK.value: "ok  ", Status.WARN.value: "warn", Status.FAIL.value: "FAIL"}
    for check in checks:
        line = f"[{glyph[check['status']]}] {check['id']:<12} {check['detail']}"
        if check.get("remedy"):
            line += f"\n              -> {check['remedy']}"
        print(line)
    healthy = envelope.data.get("healthy")
    print(f"\n{'environment ready' if healthy else 'environment NOT ready'}")


def cmd_doctor(args: argparse.Namespace) -> int:
    envelope = doctor()
    if args.text:
        _render_text(envelope)
    else:
        print(envelope.to_json())
    # Default exit is 0 even with findings -- violations are data. --strict
    # opts into a CI-style gate, mirroring kicad-cli --exit-code-violations.
    if args.strict and not envelope.data.get("healthy", False):
        return 1
    if args.require_pinned and not envelope.data.get("pinned", False):
        return 1
    return 0 if envelope.ok else 1


def cmd_build(args: argparse.Namespace) -> int:
    envelope = build(
        args.file,
        design_name=args.design,
        outdir=args.outdir,
        include_ir=args.print_ir,
    )
    print(envelope.to_json())
    if args.strict and envelope.error_count:
        return 1
    return 0 if envelope.ok else 1


def cmd_licences(args: argparse.Namespace) -> int:
    envelope = audit()
    if args.text:
        for finding in envelope.findings:
            print(finding.one_line())
        print(f"\n{envelope.data['count']} packages, {envelope.error_count} problems")
    else:
        print(envelope.to_json())
    if args.strict and envelope.error_count:
        return 1
    return 0 if envelope.ok else 1


def cmd_new(args: argparse.Namespace) -> int:
    envelope = new_project(
        args.directory,
        name=args.name,
        profile_name=args.profile,
        layers=args.layers,
        process_id=args.process,
    )
    print(envelope.to_json())
    return 0 if envelope.ok else 1


def cmd_profile(args: argparse.Namespace) -> int:
    if args.action == "check":
        envelope = check_design_rules(args.project)
    elif args.action == "regenerate":
        envelope = regenerate_design_rules(args.project)
    else:
        try:
            profile = load(args.profile, project=args.project)
            process = profile.process(args.process, layers=None if args.process else args.layers)
        except (ProfileError, KeyError) as exc:
            print(Envelope(command=f"profile {args.action}", ok=False,
                           errors=[str(exc)]).to_json())
            return 1
        if args.action == "gaps":
            data = {
                "profile": profile.provenance(),
                "gaps": [g.model_dump(mode="json") for g in profile.unencoded_gaps()],
            }
        elif args.action == "rules":
            data = {"kicad_dru": render(profile, process)}
        else:  # show
            data = {
                "profile": profile.provenance(),
                "available": available(args.project),
                "process": process.model_dump(mode="json"),
            }
        envelope = Envelope(command=f"profile {args.action}", data=data)

    print(envelope.to_json())
    if args.strict and envelope.error_count:
        return 1
    return 0 if envelope.ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pcbkit",
        description="Design production-ready PCBs from Python.",
    )
    parser.add_argument("--version", action="version", version=f"pcbkit {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor_parser = sub.add_parser(
        "doctor", help="verify the KiCad toolchain and supporting tools"
    )
    doctor_parser.add_argument(
        "--strict", action="store_true", help="exit 1 if any check fails"
    )
    doctor_parser.add_argument(
        "--text", action="store_true", help="human-readable output instead of JSON"
    )
    doctor_parser.add_argument(
        "--require-pinned",
        action="store_true",
        help="exit 1 unless the toolchain is pinned (for CI)",
    )
    doctor_parser.set_defaults(func=cmd_doctor)

    build_parser_ = sub.add_parser(
        "build", help="load a design file and emit its intermediate representation"
    )
    build_parser_.add_argument("file", type=Path, help="Python design file")
    build_parser_.add_argument(
        "--design", help="which design to build, if the file defines several"
    )
    build_parser_.add_argument(
        "-o",
        "--outdir",
        type=Path,
        default=Path("build"),
        help="output directory (default: build/)",
    )
    build_parser_.add_argument(
        "--print-ir", action="store_true", help="inline the full IR in the output"
    )
    build_parser_.add_argument(
        "--strict", action="store_true", help="exit 1 if there are error findings"
    )
    build_parser_.set_defaults(func=cmd_build)

    licences_parser = sub.add_parser(
        "licences", help="audit the dependency tree for non-open-source licences"
    )
    licences_parser.add_argument(
        "--strict", action="store_true", help="exit 1 if any licence is unacceptable"
    )
    licences_parser.add_argument(
        "--text", action="store_true", help="human-readable output instead of JSON"
    )
    licences_parser.set_defaults(func=cmd_licences)

    new_parser = sub.add_parser("new", help="scaffold a project")
    new_parser.add_argument("directory", type=Path)
    new_parser.add_argument("--name", help="project name (default: directory name)")
    new_parser.add_argument("--profile", default=DEFAULT_PROFILE)
    new_parser.add_argument("--layers", type=int, default=2)
    new_parser.add_argument("--process", help="select a process by id instead of layer count")
    new_parser.set_defaults(func=cmd_new)

    profile_parser = sub.add_parser(
        "profile", help="inspect fabricator profiles and generated design rules"
    )
    profile_parser.add_argument(
        "action", choices=["show", "gaps", "rules", "check", "regenerate"]
    )
    profile_parser.add_argument(
        "project", nargs="?", type=Path, default=None, help="project directory"
    )
    profile_parser.add_argument("--profile", default=DEFAULT_PROFILE)
    profile_parser.add_argument("--layers", type=int, default=2)
    profile_parser.add_argument("--process")
    profile_parser.add_argument(
        "--strict", action="store_true", help="exit 1 if there are error findings"
    )
    profile_parser.set_defaults(func=cmd_profile)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
