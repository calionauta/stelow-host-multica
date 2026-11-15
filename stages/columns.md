# Column instructions

One section per workflow column, keyed by the group `id` in
`config/columns.json`. These are the instructions the *step* carries — they are
what the handler's run is told to do in this column, and they are separate from
the agent's identity in `agents/`.

`## ` sections are required: provisioning fails when a column in the workflow has
no section here. Wording is yours; keep it about what the step produces and how
it ends.

## intake

Triage the request and select the item. Classify intent. Finish by moving the
issue on; if the request is noise, say so and leave it here.

## framing

Run the stelow stages of this column in order (setup → context → shape →
critique). Finish when `plans/spec-product-*.md` and the critique report exist,
**both attached to the outcome comment**, and the proposal survives the
critique. Stop before any interface or tech decision.

## product_gate

Approval of the proposal. Read the attached spec and critique report, then
approve with its *done* command or send it back to framing with the reason.

## design

Produce the scope map and the interface alternatives with their breadboard
maps. Finish when both artifacts exist and are attached. Do not pick the
interface when the mode has a person pick it.

## interface_gate

Approval of the interface. Read the attached alternatives and contrast, record
the chosen interface and its breadboard map, then finish. A pick with no map is
not a pick.

## tech

Choose the construction direction and write the technical plan with typed,
sequenced scopes. The plan must cite the selected interface.

## tech_gate

Approval of the technical plan. Check that every scope can be executed without
a further question, then finish or send it back to tech.

## build

Implement the approved scopes. Split into sub-issues per scope when there is
more than one, and use stages so scope N+1 starts only when N is done. Finish
when every scope is implemented and tested, the branch or PR is on the card, and
the change report is attached — `git diff --stat`, the commands you ran, what
each returned.

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
to build, and the execution report is attached.

## diff_gate

Approval of the code change itself. Read the entity-level diff, then finish or
send it back to verify.

## audit

Walk the proposal's requirements against what shipped, with evidence per
requirement. Attach the audit table, then finish the issue, or send it back with
the gaps.
