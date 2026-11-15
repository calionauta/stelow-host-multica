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
critique). Finish when `plans/spec-product-*.md` and the critique report exist
and the proposal survives the critique. Stop before any interface or tech
decision.

## product_gate

Approval of the proposal. Read the spec and the critique report, then approve
with its *done* command or send it back to framing with the reason.

## design

Produce the scope map and the interface alternatives with their breadboard
maps. Finish when both artifacts exist and are attached. Do not pick the
interface when the mode has a person pick it.

## interface_gate

Approval of the interface. Read the alternatives and the contrast, record the
chosen interface and its breadboard map, then finish. A pick with no map is not
a pick.

## tech

Choose the construction direction and write the technical plan with typed,
sequenced scopes. The plan must cite the selected interface.

## tech_gate

Approval of the technical plan. Check that every scope can be executed without
a further question, then finish or send it back to tech.

## build

Implement the approved scopes. Split into sub-issues per scope when there is
more than one, and use stages so scope N+1 starts only when N is done. Finish
when every scope is implemented, tested, and its changes are on the branch.

## verify

Run the full test suite, the code review, and the UI audit against the
implemented scopes. Finish when every finding is either fixed, accepted with a
reason, or sent back to build.

## diff_gate

Approval of the code change itself. Read the entity-level diff, then finish or
send it back to verify.

## audit

Walk the proposal's requirements against what shipped, with evidence per
requirement. Finish the issue, or send it back with the gaps.
