# CR-008 — Specification

## The flow

```
issue / intent  ->  branch  ->  PR  ->  checks + independent review  ->  main
                                          |
                                          +-- deferred check, declared and recorded
```

One branch per milestone or change request, named for it: `m5-schematic-emitter`,
`cr-008-pull-request-workflow`.

## Required to merge

1. **`checks` passes.** `nix run .#checks` — already green on the last three
   commits, so this makes required what is already true.
2. **`licences` passes.** CR-003 enforcement.
3. **An independent agent review approves.**

## The reviewer is a fresh agent, not a fork

It starts with no memory of the authoring session and is given only:

- the diff;
- the milestone or CR `intent.md` and `spec.md` it claims to implement;
- `AGENTS.md`.

It answers three questions, and its verdict is a PR review:

- Does the change do what its spec says, and nothing else?
- Does it violate any numbered rule in `AGENTS.md`?
- Is anything a regression against behaviour a test already pinned?

A shared-context reviewer would have passed both defects found this session,
because in each case the author believed the check was sound. Starting cold is
the mechanism, not a detail of it.

This is a deliberate exception to the usual restraint about spawning agents: the
repository owner has asked for it explicitly, and independence is the whole
point of the control.

**CR-001 does not apply here.** It constrains pcbkit the toolkit, not how this
repository is developed — as `docs/sdlc/README.md` already states. The review
agent may be harness-specific.

## Deferred checks, not bypasses

A check may be knowingly failing because the work is staged, not broken — the
issue's example is a schematic change whose layout follows later, so DRC fails
in between.

That is declared in the PR body and is machine-readable:

```
deferred: drc
why: schematic adds the USB-C connector; layout lands in #42
resolves: #42
```

A declaration names the check, the reason, and what clears it. A bare override
label would record that someone wanted to merge, which is not information.
Merging with an undeclared failing check stays blocked.

Every deferral is a tracked debt: `pcbkit` gains no capability here, but the
open declarations are visible in the PR list, and an unresolved one is a finding
at the fab gate (CR-002), where a deferred DRC stops being acceptable.

## For projects built with the toolkit

`pcbkit new` gains a `.github/workflows/checks.yml` that runs
`pcbkit check --strict`, and the generated README states the branch-protection
settings to enable. pcbkit cannot configure another account's repository, so it
produces the workflow and documents the rest rather than pretending.

## Repository settings

On `main`: require a pull request, require the `checks` and `licences` status
checks, require review approval, and dismiss stale approvals on new commits.
Enabling this is an account-level change to a live repository and is left to the
owner rather than done silently.

## Out of scope

- Merge queues, and multi-reviewer policies.
- Automatic branch cleanup.
- Retrofitting the eight existing commits. They are history; the rule starts now.

## Acceptance

- `main` rejects a direct push.
- A PR cannot merge with `checks` red unless a `deferred:` block names that
  check.
- A review by an agent that did not author the change is recorded on the PR.
- `pcbkit new` emits a checks workflow, and its README names the settings to
  enable.
- This CR is itself merged through the flow it describes.
