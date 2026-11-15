# stelow adapter rules (Multica)

These rules are prepended to every agent's instructions. They are the host side
of the stelow state contract: Multica owns some of the state, so you must not
keep a second copy of it.

## What the board owns — never duplicate it

- **Position.** The issue's status *is* the current stelow stage group. Never
  write a `current_stage` / `current_phase` field into a file. If you need to
  know where you are, read the issue.
- **The next step.** It is the status the step's *done* command moves the issue
  to. Never compute a `next-candidate` yourself and never invent a stage
  transition.
- **Hand-offs.** Your hand-off is the final comment on the issue. There is no
  hand-off block to append to a file. Post the outcome once, then move the
  issue.

## What the worker owns — nothing else knows it

Keep a single `.stelow/state.md` in the repository working tree, and keep only
these in it:

- `intent` (new-product | feature | bugfix | refactor | investigate)
- `review_mode` (which gates a human actually sees)
- `artifacts` — written by the stage that produced them; never a mirror of a
  file listing you could recompute
- `invariants` — scopes, tasks, and what was discovered and not to be redone

Do not store position, status, assignee, or hand-off history there. The issue
timeline is the audit trail.

## Gates

A gate column's handler is either the project lead (a person) or the
gatekeeper agent. If you are the gatekeeper: read `review_mode` from
`.stelow/state.md`; when the mode skips this gate, record the receipt in your
comment and run the step's *done* command in the same turn. When the mode does
not skip it, leave the issue in the gate column and post why — do not approve
on someone else's behalf.

## One turn, one outcome

Read the issue and its comments, do the stage work, post the outcome once, then
move the issue. Do not narrate progress. If you cannot proceed, move the issue
to its blocked step, or leave it where it is and post the blocker.
