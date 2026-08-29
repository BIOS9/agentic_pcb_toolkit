# CR-008 — Changes land through reviewed pull requests

Raised: 2026-08-29. Source: [#7](https://github.com/BIOS9/agentic_pcb_toolkit/issues/7).
Status: proposed.

## Problem

Everything in this repository so far was committed straight to `main` — eight
commits across M0 to M4, including two that fixed defects in earlier ones. The
branch has no protection, and nothing has been reviewed by anything other than
the process that wrote it.

That fails in three ways:

1. **Concurrency.** Several developers, or several agents, cannot work without
   colliding on one branch.
2. **Review.** There is no artifact to review against, and no moment at which
   review happens. Defects found later in this session were found by accident,
   not by a gate.
3. **Self-assessment.** The process that wrote a change is the worst judge of
   it. Twice this session a mistake survived because the same context that made
   it also checked it: a doctor test that silently stopped exercising the
   condition it named, and a CI invocation that could not fail on a broken
   toolchain.

The rule applies to projects built with the toolkit too, where the stakes are
higher: an unreviewed board change becomes an unreviewed order.

## What already works

Not starting from nothing. The `checks` workflow runs `nix run .#checks` on
every push and has passed on the last three commits, so the automated half of
enforcement exists and is proven in CI — it just is not required for anything.

## The reviewer must not be the author

The issue asks for "a completely separate agent" and that word is load-bearing.
A reviewer sharing the author's context inherits its assumptions and will
confirm them; both defects above would have survived such a review, because in
each case the author believed the check was sound. The reviewer must start cold,
read the spec and the diff, and have no memory of why the author thought it was
right.

## Enforcement needs an escape hatch that leaves a trail

The issue names a real case: a schematic changes, the board layout will not
catch up until later, and DRC legitimately fails in between. Blocking that is
wrong; silently bypassing it is worse.

This is the same argument CR-005 makes about the fab gate. An override that can
be taken quietly is not a gate — it is a formality that erodes. So an override
must name *which* check, *why*, and *what resolves it*.

## Outcome

Changes reach `main` only through a pull request that passed its checks and was
reviewed by an agent that did not write it. Exceptions are possible, explicit,
and recorded.
