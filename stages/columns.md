# Column instructions

One section per workflow column, keyed by the group `id` in
`config/columns.json`. These are the instructions the *step* carries — they are
what the handler's run is told to do in this column, and they are separate from
the agent's identity in `agents/`.

`## ` sections are required: provisioning fails when a column in the workflow has
no section here. Wording is yours; keep it about what the step produces and how
it ends.

Each section names the artifacts it must attach. Artifacts are named
`<nn>-<kind>.<ext>` — the two-digit order of the column, the kind word the
stelow skill uses, `.md` for prose and `.json` for data — so the card's
attachments sort in the order the work happened and prose separates from data at
a glance. The list lives in `config/columns.json` under each column's
`artifacts`; the two files are checked against each other.

While a column waits on a person, the card carries the `needs-human` label and a
wakeup that returns to it. A parked card with no marker reads as a dead run.

## intake

Triage the request and select the item. Classify intent. Finish by moving the
issue on; if the request is noise, say so and leave it here.

## framing

Run the stelow stages of this column in order (setup → context → shape →
critique). Mint the requirement ids here: every product promise the proposal
makes gets a stable id (`S1`, `S2`, …) in the spec, and every later artifact —
design, tech, build, audit — cites that id instead of describing the promise
again. A stage that invents its own numbering makes the audit a translation
exercise, and a requirement with two names is a requirement nobody can trace.

Finish when `01-spec-product.md` and `02-critique-report.md` exist, **both
attached to the outcome comment**, and the proposal survives the critique. Stop
before any interface or tech decision.

## product_gate

Approval of the proposal. Read the attached `01-spec-product.md` and `02-critique-report.md`, then approve
and attach `03-product-decision.md` with the ruling and the reason, or send it
back to framing with the reason.

## design

Produce `04-scope-map.json`, `05-interfaces.md`, `06-contrast.json`,
`07-alternatives.md`, `08-selected-interface.md` and `09-breadboard.json`.
Finish when they are attached. Do not pick the interface when the mode has a
person pick it.

## interface_gate

Approval of the interface. Read the attached `07-alternatives.md` and `06-contrast.json`, record the chosen
interface and its breadboard map in `10-interface-decision.md`, then finish. A
pick with no map is not a pick.

## tech

Choose the construction direction and write `11-spec-tech.md` with typed,
sequenced scopes, `12-decision.md` and `13-testing-strategy.md`. The plan must
cite the selected interface by its requirement ids.

## tech_gate

Approval of the technical plan. Check that every scope can be executed without
a further question; attach `14-tech-decision.md`, then finish or send it back to
tech.

## build

Implement the approved scopes. Split into sub-issues per scope when there is
more than one, and use stages so scope N+1 starts only when N is done. Finish
when every scope is implemented and tested, the branch or PR is on the card, and
`15-execution-report.md` is attached — `git diff --stat`, the commands you ran,
what each returned, and the PR link.

## verify

Run the tests that can catch *this* change, then the code review and the UI
audit against the implemented scopes.

The full suite is CI's job, not this column's: it takes tens of minutes here and
reports the same red the narrow run already reported. Pick the tests that touch
the modules you changed, plus any contract test those modules appear in, and say
which command you ran and what it returned. Reach for the whole suite only when
the change is cross-cutting, and say so before you start it.

Cap every command: `timeout 300 <cmd>`. A command that can outlive your turn
freezes the card, and the person reading cannot tell a long test run from a
hung one. If something genuinely needs longer, run it in the background, move
on with the rest of the stage, and post its result when it lands.

Finish when every finding is either fixed, accepted with a reason, or sent back
to build, and `16-verification-report.md` is attached with one line per command.

## diff_gate

Approval of the code change itself. Read the entity-level diff; attach `17-diff-review.md` with the approved
conditions and any nit carried forward, then finish or send it back to verify.

## audit

Walk the proposal's requirements against what shipped, with evidence per
requirement — **the diff and the spec rows you are judging, not the repository
around them.** Re-deriving what the artifacts already cite is how an audit pass
costs more than the build it checks (CAL-52: four audit runs, ~12M tokens). Open
a file only to check a row you are about to reject or sign off. If this is the **third** pass through build (two back-edges
already spent), stop and park for a person with the rows that remain instead of
opening another round: a fourth round is the loop deciding, not the reviewer. Cite the spec's ids; a requirement you cannot cite is a requirement
nobody shipped. Attach `18-audit-table.md`, then finish the issue, or send it
back with the gaps.

## When the card waits on a person

Every gate section ends the same way: mark the card and arm one nudge, because a
card waiting on a ruling and a run that died look identical on the board.

    multica issue label add <this issue> needs-human
    multica issue wakeup create <this issue> --after 45m --instruction "Say in one line who owes what, or close the loop."

The person who rules removes the marker. `stelow-host doctor` fails when a card
sits in a gate column with no marker, or on an agent column with no run and no
marker, and `doctor --fix` marks the first case.

## Artifacts by column

| column | artifacts (attached to the outcome comment) |
|---|---|
| intake | — (the card is the artifact) |
| framing | `01-spec-product.md`, `02-critique-report.md` |
| product_gate | `03-product-decision.md` |
| design | `04-scope-map.json`, `05-interfaces.md`, `06-contrast.json`, `07-alternatives.md`, `08-selected-interface.md`, `09-breadboard.json` |
| interface_gate | `10-interface-decision.md` |
| tech | `11-spec-tech.md`, `12-decision.md`, `13-testing-strategy.md` |
| tech_gate | `14-tech-decision.md` |
| build | `15-execution-report.md` |
| verify | `16-verification-report.md` |
| diff_gate | `17-diff-review.md` |
| audit | `18-audit-table.md` |
