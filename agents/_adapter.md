# stelow adapter rules (Multica)

These rules are prepended to every agent's instructions. They are the host side
of the stelow state contract: Multica owns some of the state, so you must not
keep a second copy of it.

There are three agents — `plan`, `build`, `review` — and the issue's status says
which stage group is running, so nothing here needs to record position.

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

A gate column's handler is either the project lead (a person) or the reviewer
agent. If you are the reviewer: read `review_mode` from `.stelow/state.md`; when
the mode skips this gate, record the receipt in your comment and run the step's
*done* command in the same turn. When the mode does not skip it, leave the issue
in the gate column and post why — do not approve on someone else's behalf.

## Language

Everything you write on the card is English: comments, artifacts, commit
subjects, PR descriptions. The project's artifacts are English too, so a person
reading a plan and then its critique reads one language. A request may arrive in
another language; answer in English, and keep a term in its own language only
when that term is the domain's own name for the thing.

## Artifacts leave as files, not as prose

Every artifact a stage produces is attached to its outcome comment with
`--attachment <path>`; the comment carries the decision summary and the file
list, never the artifact body. A wireframe, a contrast table, a spec or a plan
pasted into a comment cannot be read as a document, cannot be downloaded, and
cannot be diffed against the next version. Two consequences:

- one comment per stage, `--attachment` repeated for each artifact it produced
- a message body that wants more than about fifteen lines is a message with an
  artifact inside it: attach the file and say what it means

The artifacts are the deliverable. A stage whose artifacts exist but were never
attached did not hand anything over — the next column cannot read them.

## Silence has a limit

Do not narrate your steps. But a stage that runs twenty minutes with nothing on
the card looks dead, and the person reading cannot tell a long render from a
hung run: post **one** interim line naming what you are producing, then keep
working. One line, not a running commentary, and one more if another ten
minutes pass.

## No command outlives your turn

Cap anything that can run long: `timeout 300 <cmd>`. A test suite, a build or a
network fetch with no ceiling holds the card open with nothing on it, and the
person reading has no way to tell work from a hang. If a command needs longer,
start it in the background, keep going, and report the result when it lands.

## One turn, one outcome

Read the issue and its comments, do the stage work, post the outcome once, then
move the issue. Do not narrate progress. If you cannot proceed, move the issue
to its blocked step, or leave it where it is and post the blocker.

## Missing input is not a rejection

Send an issue back when the work you received is wrong against the stage's exit
criteria — that is what the back edge is for.

When the work is simply not there (no product spec to critique, no plan to
implement, no way to produce the artifact from what the issue says), do **not**
send it back. A back edge re-enters a stage that will fail the same way, so the
card ping-pongs between two columns and burns a run per lap — observed on the
first smoke run, twice in ninety seconds. Comment with the one question that
unblocks you, leave the issue in its column, and stop. A person moves it.
