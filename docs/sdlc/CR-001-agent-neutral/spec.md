# CR-001 — Specification

## Testable definition

"Agent-neutral" means all four of these hold, and `tests/test_agent_neutral.py`
checks each:

1. **No vendor identifiers under `pcbkit/`** — no `claude`, `anthropic`,
   `codex`, `cursor`, `copilot`, `openai`, or `gemini` in code, comments, or
   strings.
2. **Every shipped capability has a CLI verb.** A capability reachable only
   through a hook, skill, or slash command does not exist for other agents.
3. **`pcbkit/core/` reads no agent environment variables.** The sole env var
   pcbkit honours is `PCBKIT_PCBNEW_PYTHON`.
4. **Generated agent adapters stay in sync with their source.** Active once
   `docs/agent/workflow.md` exists at M7; skipped before that.

## Source of truth for agent guidance

```
docs/agent/workflow.md              # canonical, plain Markdown
  -> skills/pcb-design/SKILL.md     # Claude Code adapter
  -> AGENTS.md                      # repo conventions (already canonical)
  -> MCP tool descriptions          # generated from the same source
```

`pcbkit docs sync --check` fails when an adapter drifts, the same discipline as
the golden files under `tests/golden/`.

## Decisions this reverses

| Decision | Was | Becomes |
|---|---|---|
| Fab-order gate | Claude Code hook | `pcbkit gate` in the CLI; the hook becomes a convenience wrapper over it |
| MCP frontend | Deferred indefinitely | Promoted: it is the typed frontend for agents without a shell. Still after M7. |
| Knowledge layer | `SKILL.md` is the product | `SKILL.md` is a generated adapter; `docs/agent/workflow.md` is the product |
| Conventions file | `CLAUDE.md` | `AGENTS.md`, with `CLAUDE.md` reduced to a pointer |

The gate reversal is the substantive one. It restores the plan's original
`pcbkit gate <stage>` design, which the v1 layout already anticipates: the
fixed project directory, persisted `findings/*.json`, and the `approvals` block
in `release/<v>/manifest.json` were all chosen so a CLI gate drops in cheaply.

## Explicitly out of scope

- Per-agent evals. `claude plugin eval` stays Claude-specific; other agents get
  their own harnesses. Stated here so it is a decision, not an oversight.
- Supporting every agent's config format. We publish a neutral source and the
  adapters we choose to maintain; a third party can generate others from it.

## Acceptance

- `uv run pytest tests/test_agent_neutral.py` passes.
- `AGENTS.md` rule 7 states the constraint; `CLAUDE.md` is a pointer.
- No file under `pcbkit/` names a vendor.
- The M6 and M7 specs, when written, place the gate in the CLI.
