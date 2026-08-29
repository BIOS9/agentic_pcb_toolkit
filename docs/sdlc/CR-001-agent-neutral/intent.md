# CR-001 — pcbkit must not privilege any one agent

Raised: 2026-08-29. Status: accepted.

## Problem

The approved plan assumed Claude Code as the consuming agent. Several decisions
in it only make sense under that assumption:

- the fab-order gate was to be enforced by a Claude Code **hook**;
- the agent-facing knowledge layer was to live in `skills/pcb-design/SKILL.md`,
  a Claude Code file format;
- the conventions file was named `CLAUDE.md`;
- the MCP frontend -- the one interface a non-shell agent could use -- was
  deferred indefinitely.

None of that is visible as a problem while only one agent is used, which is
exactly why it needs writing down now. A Codex or Cursor agent, a CI script, or
a human at a terminal must get the same toolkit with the same guarantees.

The hook decision is the sharp one. Enforcement inside one agent's harness is
not enforcement: any other caller reaches `pcbkit fab` directly and the gate
never runs. That is a correctness hole, not a portability preference.

## Outcome

pcbkit works identically under any agent. Agent-specific material exists only as
*generated adapters* over a neutral source of truth, and every capability --
enforcement included -- is reachable from the CLI alone.

## Why now

The constraint is nearly free today: `pcbkit/core/` has no agent coupling, and
the CLI-plus-JSON interface already chosen is the right neutral substrate. The
only violations are two doc comments and a filename.

Adopting it at M7 instead would mean moving the gate out of a hook, rewriting
the knowledge layer as a generated artifact, and retrofitting an MCP frontend
onto code that had grown to assume a shell -- after the skill and its evals were
already written against the Claude-specific shape.

## Constraints

- Per-agent behaviour evals stay per-agent. Evaluating how an agent behaves is
  necessarily specific to that agent; pretending otherwise would produce a
  weaker test, not a more portable one.
- Claude Code remains a first-class consumer. Neutral does not mean
  lowest-common-denominator: the plugin, skill, and hooks still ship. They just
  stop being the only path to a capability.

## Scope

Cross-cutting. Touches M6 (gate placement), M7 (agent surface), the deferred v2
items, and the conventions file. Does not change M1--M5.
