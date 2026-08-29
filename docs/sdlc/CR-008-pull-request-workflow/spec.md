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
| `gate` | `.github/workflows/checks.yml` | `checks` passed, or its failure is declared |
| `agent-review` | `.github/workflows/agent-review.yml` | an independent agent posted a verdict |

`checks` itself runs `nix run .#checks` and `nix run .#licences`, and was
already green on the last three commits. It is deliberately **not** the required
context; `gate` is, for the reason the deferral section gives.

### How an agent review becomes an enforceable check

GitHub does not permit an account to formally approve its own pull request, and
here the author and the reviewing agent run as the same account. An agent review
can therefore only ever be a *comment* — which this CR requires but which
nothing could enforce.

`agent-review.yml` closes that gap: a PR comment containing a `VERDICT:` line
becomes a commit status that branch protection requires.

The comment ends with the verdict as its **last non-empty line**, exactly one
of:

```
VERDICT: APPROVE                  -> success
VERDICT: APPROVE WITH COMMENTS    -> success
VERDICT: REQUEST CHANGES          -> failure
```

and carries, anywhere in the body, the commit it actually read — the **full
forty characters**:

```
reviewed: 7e5cd02f1a4b9c3d5e8f0a2b4c6d8e0f1a3b5c7d
```

Anchoring to the last line matters because an unanchored search lets a
postscript win: a request for changes followed by "(earlier I wrote VERDICT:
APPROVE)" would otherwise resolve to success. Fail-open, in the direction that
matters.

### Binding the verdict to a commit

The status attaches to the head SHA, and the workflow refuses to record a
verdict whose `reviewed:` line does not match it. Resolving the head at run
time and stamping it would not be enough:

- **The branch can move mid-review.** A fork pull request can be force-pushed
  between the reviewer reading the diff and the comment landing, which would
  stamp a verdict onto code nobody read. "Require branches to be up to date"
  does not help; it compares against the base, not against what was reviewed.
- **An edit would re-arm a stale approval.** The workflow fires on `edited`, so
  adding one space to an old approving comment re-runs it. Without the binding
  it would re-resolve the *current* head and stamp success there — letting an
  author un-dismiss their own stale approval with a one-character edit.

With the binding, both close. A new commit is a new SHA with no status, so the
required check goes missing and the merge blocks until the new code is reviewed;
no separate dismissal rule is needed, and a verdict cannot be replayed onto code
it did not review.

An abbreviated SHA is not accepted. Seven hex characters is 2^28, and grinding
a commit to a chosen short prefix is minutes of off-the-shelf work — enough to
reopen the same force-push replay against a crafted head. The comparison is
equality on the full hash, case-normalised.

A comment whose `reviewed:` line does not name the current head is not about
this commit, so it records nothing at all: it neither approves nor clears. Only
once the SHA matches does a later failure — a malformed verdict line, an API
error — record `error`. Without that ordering, a comment merely quoting the
syntax could wipe a legitimate approval off unchanged code.

### Who may post a verdict

The job filters on `author_association` to keep a passer-by on a public
repository from starting a runner by commenting the trigger string, and then
checks the thing that actually matters: `repos/{owner}/{repo}/collaborators/
{login}/permission`, accepting only `admin`, `write`, or `maintain`.

`author_association` alone is not authorisation. `COLLABORATOR` covers read-only
and triage invitations and `MEMBER` is org membership; neither implies the
ability to push. This repository is public, so the difference is the whole
control: without it an account trusted only to read could turn its own pull
request green.

If that endpoint is not readable by `GITHUB_TOKEN`, the guard falls back to
requiring `OWNER` — the account that owns the repository, which is the one
association that does imply control of it. Failing closed instead would leave
`main` permanently unmergeable with nothing on the page saying why, because an
`issue_comment` run does not appear in a pull request's checks list. The
fallback never accepts a weaker claim than the check it replaces.

**Smoke-test this before enabling protection.** Post a throwaway verdict comment
on an open pull request and watch the run. A guard that cannot read the endpoint
and an author who is not `OWNER` is a deadlock discovered at the worst moment.

### Failures must be visible

An `issue_comment` run does not appear in the pull request's checks list, so a
job that dies silently leaves an earlier success standing and nothing on the
page says otherwise. Once the permission guard has passed, any later failure —
a malformed verdict, a stale `reviewed:` line, an API error — records `error`
on the context instead of leaving the previous state.

Comments with no `VERDICT:` line are ignored rather than failed, so ordinary
discussion does not disturb the status.

One property is worth stating rather than discovering: commit statuses are
last-write-wins per context. A request-changes verdict can be flipped by a later
approving comment on the same unchanged SHA, including from the author. What
prevents that being a quiet self-override is that both comments are on the pull
request, permanently.

## The reviewer is a fresh agent, not a fork

It starts with no memory of the authoring session and is given only:

- the diff;
- the milestone or CR `intent.md` and `spec.md` it claims to implement;
- `AGENTS.md`.

It answers three questions, and its verdict is a PR comment:

- Does the change do what its spec says, and nothing else?
- Does it violate any numbered rule in `AGENTS.md`?
- Is anything a regression against behaviour a test already pinned?

A shared-context reviewer would have passed both defects found this session,
because in each case the author believed the check was sound. Starting cold is
the mechanism, not a detail of it.

### The tree must be still while it reads

The reviewer reads the diff from the pull request but the repository from disk,
so the author must not be editing during a review. The first review run under
this CR proved the point: work in progress in the author's tree was read as
already merged and reported as an acceptance item satisfied, when `git show
main:` showed it did not exist. The finding was wrong in the direction that
matters — it excused a gap.

The `reviewed:` line is what makes this checkable rather than trusted: it names
a commit, and a verdict against a moving tree will not match one. Where the
review can be run against a clean checkout of the head commit, it should be.

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
deferred: checks
why: schematic adds the USB-C connector; layout lands in #42
resolves: #42
```

A declaration names the check, the reason, and what clears it. A bare override
label would record that someone wanted to merge, which is not information. All
three lines are required, in any order: an incomplete declaration fails the gate
rather than passing it, so a half-written deferral cannot succeed by looking
like one. `resolves:` must name a real issue — `#0` tracks nothing.

### A mention is not a declaration

Each line must start at the beginning of a line, and a block inside a **code
fence** or an **HTML comment** does not count.

Both exclusions are load-bearing rather than tidy. The three-line block appears
inside a fence in this specification and in the README `pcbkit new` emits, so
without the first, a pull request that quoted its own documentation would defer
its own checks. And without the second, a deferral could be hidden in an HTML
comment: the rendered body would show an ordinary description and no deferral at
all, which is exactly the override taken quietly that `intent.md` rejects. The
declaration has to be visible to the person reading the pull request, or it is
not a record.

### Why `gate` is the required context and `checks` is not

A required status context in GitHub is all-or-nothing. Requiring `checks`
directly would leave an admin bypass as the only way past a knowingly-red check
— precisely the quiet override this CR rejects, and the same argument CR-005
makes about the fab gate.

So `checks.yml` carries a second job, `gate`, which is what branch protection
requires. It runs after `checks` with `if: always()`, reads the pull request
body, and passes when `checks` is green **or** when the body declares the
failure. The deferral is evaluated in the same workflow that produced the
failure, which is what avoids mapping a `workflow_run` back to a pull request.

`checks` still runs and is still visible; it simply is not the thing that
blocks. The workflow triggers on `edited` as well as `synchronize`, so adding a
declaration to the body re-evaluates the gate rather than requiring an empty
commit.

Every deferral is a tracked debt: `pcbkit` gains no capability here, but the
open declarations are visible in the PR list, and an unresolved one is a finding
at the fab gate (CR-002), where a deferred DRC stops being acceptable.

The gate names the failing job, so its granularity is the job. Splitting
`checks` into finer jobs — ERC, DRC, rules — makes deferrals correspondingly
finer without changing the mechanism.

## For projects built with the toolkit

`pcbkit new` emits `.github/workflows/checks.yml` and a README naming the
branch-protection settings to enable. pcbkit cannot configure another account's
repository, so it produces the workflow and documents the rest rather than
pretending.

The generated workflow runs the verbs that exist, each with the flag that makes
it a gate — `pcbkit doctor --strict`, `pcbkit profile regenerate`, and
`pcbkit build <design> --strict`. `pcbkit check --strict` joins them when M7
lands the check layer; naming it now would emit a workflow that cannot run,
which is the defect this CR was raised over, one stage earlier. The step list is
data in `pcbkit/core/scaffold.py` and a test parses each command against the
real CLI, so a workflow naming a verb that does not exist fails here rather than
in a user's repository.

It runs inside the KiCad container: KiCad 10 and its `pcbnew` module are not on
a hosted runner image, and a workflow whose first step cannot pass is not a
gate. pcbkit itself is pinned at the version that generated the project, for the
reason CR-004 gives.

The `gate` job is shared verbatim between this repository's workflow and every
generated one, pinned by a test. Two copies of a rule are two rules, and the one
nobody looks at is the one that rots.

## Repository settings

On `main`: require a pull request, and require the `gate` and `agent-review`
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
- `gate` fails when `checks` is red and nothing declares it, and passes when a
  complete `deferred:` block names it, in either field order. An incomplete
  block fails, and a block inside a code fence or an HTML comment does not
  declare anything.
- A comment whose last line is `VERDICT: APPROVE` and which names the head
  commit sets the `agent-review` status on that SHA; pushing a further commit
  clears it, and editing the old comment does not restore it.
- A verdict naming a commit that is no longer head is refused, and records
  nothing against the head it did not review. An abbreviated SHA is refused.
- A verdict from an account without push permission is refused — checked
  against the repository's collaborator permission, not `author_association`.
- A verdict *for the current head* that fails to record leaves `error` on the
  context rather than an earlier success. A comment that merely mentions the
  syntax leaves the context untouched.
- A review by an agent that did not author the change is recorded on the PR.
- `pcbkit new` emits a checks workflow whose every command is a real CLI verb,
  and a README naming the settings to enable and how to declare a deferral.
- This CR is itself merged through the flow it describes.
