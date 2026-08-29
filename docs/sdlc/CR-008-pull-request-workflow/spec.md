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

Two required status contexts on `main`:

| Context | Set by | Means |
|---|---|---|
| `checks` | `.github/workflows/checks.yml` | `nix run .#checks` and `nix run .#licences` passed |
| `agent-review` | `.github/workflows/agent-review.yml` | an independent agent posted a verdict |

`checks` was already green on the last three commits, so requiring it makes
mandatory what is already true.

### How an agent review becomes an enforceable check

GitHub does not permit an account to formally approve its own pull request, and
here the author and the reviewing agent run as the same account. An agent review
can therefore only ever be a *comment* — which this CR requires but which
nothing could enforce.

`agent-review.yml` closes that gap: a PR comment containing a `VERDICT:` line
becomes a commit status that branch protection requires.

```
VERDICT: APPROVE                  -> success
VERDICT: APPROVE WITH COMMENTS    -> success
VERDICT: REQUEST CHANGES          -> failure
```

Two properties fall out of attaching the status to the **head SHA**:

- **Stale approvals dismiss themselves.** A new commit is a new SHA with no
  status, so the required check goes missing and the merge blocks until the new
  code is reviewed. No separate dismissal rule is needed.
- **A verdict cannot be replayed** onto code it did not review.

The workflow accepts verdicts only from `OWNER`, `MEMBER`, or `COLLABORATOR`.
That guard is load-bearing, not defensive: this repository is public, so without
it any passer-by could approve their own pull request by commenting on it.

Comments with no `VERDICT:` line are ignored rather than failed, so ordinary
discussion does not disturb the status.

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

On `main`: require a pull request, and require the `checks` and `agent-review`
status contexts to be green and up to date with the base branch.

Approval count is left at zero deliberately. A required *review* approval cannot
be satisfied by an account reviewing its own pull request, so it would deadlock;
`agent-review` is the control that actually carries the review requirement.

**Ordering matters.** A workflow triggered by `issue_comment` always runs from
the default branch, so `agent-review.yml` must be merged to `main` before it can
gate anything. Enabling protection first would deadlock: the pull request that
carries the workflow would require a status that only that workflow can produce.

The sequence is therefore: review this pull request, merge it, then enable
protection. That is the one merge the rule cannot cover, and it is recorded here
rather than glossed over.

## Out of scope

- Merge queues, and multi-reviewer policies.
- Automatic branch cleanup.
- Retrofitting the eight existing commits. They are history; the rule starts now.

## Acceptance

- `main` rejects a direct push.
- A PR cannot merge with `checks` red unless a `deferred:` block names that
  check.
- A comment carrying `VERDICT: APPROVE` sets the `agent-review` status on the
  head SHA; pushing a further commit clears it.
- A verdict from an account without write access is refused.
- A review by an agent that did not author the change is recorded on the PR.
- `pcbkit new` emits a checks workflow, and its README names the settings to
  enable.
- This CR is itself merged through the flow it describes.
