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

## Artifact names sort by stage, then by kind

Name every artifact `<nn>-<kind>.<ext>`: a two-digit stage order, the kind word
the stelow skill already uses, and `.md` for prose or `.json` for data. The
prefix is what makes the card readable — attachments then sort in the order the
work happened, prose and data separate by extension, and a reviewer sees at a
glance which stage produced which file. Your column lists the artifacts it
expects; produce those names, not your own. Never put a version suffix in the
name: a revision replaces the file under the same name, because `spec-tech_v2.md`
sitting beside `spec-tech_v1.md` on a card is a diff nobody can make. Attach only
what this stage produced; when an earlier artifact still applies, say
`carried forward: <name>` in one line instead of attaching it again.

## Tests run once

A verification pass that repeats what the previous column already ran costs the
card ten minutes and buys nothing. `build` runs the red-first proof and the unit
tests for the code it touched; `verify` runs the integration, layout, type and
lint gates once, and reports one line per command with its result. If you re-run
something, say which finding made you re-run it.

## No command outlives your turn

Cap anything that can run long: `timeout 300 <cmd>`. A test suite, a build or a
network fetch with no ceiling holds the card open with nothing on it, and the
person reading has no way to tell work from a hang. If a command needs longer,
start it in the background, keep going, and report the result when it lands.

## One turn, one outcome

Read the issue and its comments, do the stage work, post the outcome once, then
move the issue. Open that comment with where the card is, one line, in the same
shape every time: `stage 7/18 - tech`. A card with twenty comments and no
position marker makes the reader reconstruct the chain before they can read the
outcome. Do not narrate progress. If you cannot proceed, move the issue
to its blocked step, or leave it where it is and post the blocker.

## A back edge has a budget

Two rounds back to the same column is what the loop is for. A third one is
the loop deciding instead of a person: park the card, marked and nudged, with
the rows that remain, and let someone rule on shipping with them.

## Missing input is not a rejection

Send an issue back when the work you received is wrong against the stage's exit
criteria — that is what the back edge is for.

When the work is simply not there (no product spec to critique, no plan to
implement, no way to produce the artifact from what the issue says), do **not**
send it back. A back edge re-enters a stage that will fail the same way, so the
card ping-pongs between two columns and burns a run per lap — observed on the
first smoke run, twice in ninety seconds. Comment with the one question that
unblocks you, then mark the card as parked — see below — and stop.

## Asking is a state, not a silence

A card parked for a decision must look parked. Left in its column with no run, it
is indistinguishable from a run that died, and nothing on the card says who owes
the answer: on the second smoke run a parked card sat idle for forty minutes
while the person reading assumed the agent was still working. So when you park:

```
multica issue label add <this issue> needs-human
multica issue update <this issue> --assignee-id <the card's creator_id>
multica issue wakeup create --after 45m \
  --instruction "Still parked: check for an answer. If there is none, say in one line what is owed and re-arm."
```

`creator_id` is in `multica issue get <this issue> --output json` (assign it only
when `creator_type` is `member`; if an agent opened the card, leave the assignee
alone and say so in your one line). The label says what is happening; the assignee
says who owes the answer. A card with the first and not the second stayed invisible
on CAL-57 for twenty-five minutes: the person who asked had no notification and the
assignee still pointed at the agent that wrote the code.

```
stelow-host park <issue> --why "one line on what is owed" --wake 45m
```

does the three steps in one command when you have this repository checked out.

and say in one line who owes what. When the answer arrives, remove the label
(`multica issue label remove <this issue> needs-human`) and carry on.

Park only when the answer changes what ships. A finding you can close by reading
the code is yours to close: parking on one of those hands the human engineering
work and stops the card. If a finding needs a product ruling, say which promise
it trades against — that is the ruling, and it is theirs.
