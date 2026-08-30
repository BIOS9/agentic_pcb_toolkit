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

Both exclusions are decided **within the line**, not by a rule per line. Each
of the three defects found here was a line that did two things at once, and a
per-line rule cannot see the second one.

The fence is matched by **delimiter and run length**, and closes only on a line
carrying the delimiter and nothing else. Quoting a document that already
contains a fence needs a longer outer fence, so a parity toggle would read the
inner one as a close and the quoted example would declare after all. A `~~~`
line likewise does not close a ``` fence. And CommonMark permits an info string
on the *opening* fence only, so a ```` ```js ```` line inside a ``` block is
content: closing on it read the rest of a quoted document as live declarations,
and a body pasting a chunk of markdown is precisely the case this exists for.

HTML comments are scanned in order across the line, because a single line can
close one comment and open another. Two independent line-level rules see only
that the line contains both `<!--` and `-->`, and conclude the comment ended —
so `<!-- note --> <!--` left everything below it live. That body renders as
nothing at all: a pull request whose visible description is empty, deferring its
own checks with a warning in a log nobody reads.

What survives that scan is what a reader sees, which is the actual rule. A
declaration after a closed comment on the same line — `<!-- note -->deferred:
checks` — *does* declare, because it renders. The one place the rule is
enumerated rather than derived is `<details>`: a declaration inside one is taken,
and it renders inside a collapsed disclosure. That is deliberate. A disclosure
triangle is visible, the reader can open it, and the text is in the body
permanently; a comment is none of those things.

An unbalanced fence, or a literal `<!--` with no closing `-->`, hides everything
after it. That fails closed — the declaration below is not seen and the gate
blocks — and the gate's error message names the cause, because "no deferral
declares it" is a confusing thing to read next to a deferral you can see.

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
commit — and carries a `concurrency` group for the same reason `agent-review`
does. Each run reads the body as it was when its event fired, so two quick
edits race, and without superseding the older run a deferral could be added,
edited straight back out, and the first run's green be the one that survives.

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
gate. The container tag derives from `CONFIRMED_KICAD_VERSION`, the single
constant AGENTS.md rule 4's format numbers are pinned against, and was checked
against the registry rather than assumed.

The container job runs as root. The image's own default user is `kicad`, uid
1000, while a hosted runner owns the mounted workspace as uid 1001 — so
`actions/checkout` cannot write it and the job dies before the first verb runs.
That is the same class as the ref that did not resolve: a gate that cannot pass,
found by reading the image config rather than by assuming it.

**pcbkit's own ref is the one place this milestone does not achieve CR-004, and
it says so.** Pinning to `v<version>` would be correct, but pcbkit publishes no
tags, so that ref does not resolve and every generated project's first CI run
would die before pcbkit was installed. A gate that cannot pass is the same
failure as one that cannot fail. So the default is the default branch, which
resolves; `pcbkit new --pcbkit-ref <tag-or-commit>` pins it; and the generated
README states plainly that with the default, the project's CI result can change
without the project changing. A documented limitation, not a silent one — and it
closes the moment pcbkit tags a release.

The ref is validated before it is written. It lands in a `run:` line, so a value
that is not a ref would put a command in a workflow step that nobody wrote as
one, in CI holding that project's secrets. `pcbkit new --pcbkit-ref 'main; curl
…'` is refused and nothing is written — as an `errors[]` entry rather than a
`findings[]` one, matching the pre-existing name check: a malformed argument is
a usage error, not something observed about a board (rule 3).

The project name is validated the same way and for the same reason, since this
change is what first routes it into a `run:` line.

Both are matched with `re.fullmatch`. An anchored `re.match` is not equivalent:
in Python `$` matches at the end of the string *or immediately before a trailing
newline*, so `--pcbkit-ref $'main\n'` passed a pattern written to keep exactly
that out. The newline landed in the workflow as a continuation at column 1,
`pcbkit new` reported success, and the emitted file was one GitHub Actions
cannot parse — a generated gate that can never report.

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
  declare anything — including a fence whose inner line carries an info string,
  and a line that closes one comment and opens another.
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
- `pcbkit new` emits a checks workflow whose every command is a real CLI verb
  and whose container and pcbkit refs both resolve, and a README naming the
  settings to enable, how to declare a deferral, and which of its pins is not
  one.
- The generated workflow's gating step fails a project broken in a way the
  build layer can see, and passes the scaffold as generated. Asserted by
  running it, not by reading its comment.
- This CR is itself merged through the flow it describes.
