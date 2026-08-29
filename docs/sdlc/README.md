# SDLC artifacts

How work enters this repo and becomes a decision record. Follows Anthropic's
[AI-Native SDLC playbook](https://claude.com/blog/the-ai-native-sdlc-playbook):
every stage commits a versioned artifact, and the next stage reads what the
previous one produced.

## The chain

```
intent.md  ->  spec.md  ->  plan.md  ->  diff  ->  review findings  ->  intent.md
```

**Append-only.** Superseded decisions are recorded as superseded, never edited
away. An approved artifact that gets quietly rewritten destroys the audit trail
that makes the chain worth keeping.

## Two kinds of artifact

| | Milestone (`M0/`, `M1/`, ...) | Change request (`CR-001/`, ...) |
|---|---|---|
| Shape | Scoped, sequential, finishes | Cross-cutting, permanent |
| Example | "add ODB++ export" | "must work under any agent" |

Deciding question: **does it change decisions already made elsewhere?**
Yes -> CR. No, but it is new work -> milestone. No, it is a defect in existing
work -> just a commit, no artifact.

Manufacturing an `intent.md` for a one-line fix is bureaucracy, and it devalues
the ones that matter.

## GitHub issues are input, not record

File an issue with the problem, why it matters, and what breaks without it.
Not a spec -- structuring it is the point of the intake step.

Traceability runs **one way**: the artifact cites the issue (`Source: #12`), the
commit closes it. The issue never holds the requirement. Anything else gives two
sources of truth and they diverge.

A useful property: turning an issue into an artifact is a lossy translation, and
a misreading shows up as a wrong `intent.md` -- a reviewable diff. Disagreement
gets settled on the artifact rather than in issue comments.

## Note on CR-001

CR-001 constrains **pcbkit the toolkit** -- what any agent can do with it. It
does not constrain how this repository is developed. Tooling used to build
pcbkit may be agent-specific; pcbkit itself may not be.

## Index

| Artifact | Status | Subject |
|---|---|---|
| [M0](M0/) | shipped | Environment guard, CLI output contract |
| [M1](M1/) | shipped | Circuit IR and capture DSL |
| [M3](M3/spike.md) | spike done | `kicad-sch-api` writes KiCad 10 schematics |
| [CR-001](CR-001-agent-neutral/) | accepted | No agent may be privileged |
| [CR-002](CR-002-iterative-intent/) | proposed | Requirements are the entry point ([#1](https://github.com/BIOS9/agentic_pcb_toolkit/issues/1)) |
| [CR-003](CR-003-open-source-only/) | proposed | Open-source toolchain only ([#2](https://github.com/BIOS9/agentic_pcb_toolkit/issues/2)) |
| [CR-004](CR-004-reproducible-builds/) | proposed | Hermetic, reproducible builds ([#3](https://github.com/BIOS9/agentic_pcb_toolkit/issues/3)) |

The approved implementation plan for M0-M7 lives outside the repo at
`~/.claude/plans/i-want-to-build-zany-firefly.md`. CR-002 and CR-004 both change
it; see their spec files for what they supersede.
