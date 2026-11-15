# Design: stelow on Multica

## Where the state lives

stelow's reference backend is a file (`.stelow/state.md`). Multica can mint part
of that state itself, so this host splits it and **only delegates the half
Multica actually owns**:

| Fact | Owner on Multica | Why |
|---|---|---|
| position (which stage) | **board** — the issue's status | the board is the board; a second copy drifts |
| next step | **board** — the column's own move command | `next_status_key` is data, not an LLM decision |
| hand-off / audit trail | **board** — the issue timeline | comments are durable and visible to people |
| artifacts | **repo** — the file the stage wrote | never a manifest you could recompute |
| `intent` | **repo** (`.stelow/state.md`) | decides which columns apply; not a Multica concept |
| `review_mode` | **repo** (`.stelow/state.md`) | read by the gatekeeper; Multica cannot skip a column |
| invariants | **repo** | scopes/tasks/known-and-not-to-redo; nothing on Multica knows them |

`agents/_adapter.md` states this split to every agent. It is the one place where
host policy lives, and it is prepended to every agent's instructions by `apply`.

## Why columns instead of 18 statuses

18 columns on a board is unreadable, and stelow's own routing already groups
stages that share a phase of thought. The mapping (also in `config/columns.json`):

| Column | stelow stages | Handler |
|---|---|---|
| `intake` | triage, select | agent |
| `framing` | setup, context, shape, critique | agent |
| `product_gate` | gate | person or gatekeeper |
| `design` | scope, interface | agent |
| `interface_gate` | int-gate, selection | person or gatekeeper |
| `tech` | architecture, planning | agent |
| `tech_gate` | plan-gate | person or gatekeeper |
| `build` | execution | agent |
| `verify` | verification | agent |
| `diff_gate` | diff-gate | person or gatekeeper |
| `audit` | audit | agent |

Every stage must land in exactly one column: a stage with no column fails the
run instead of being silently dropped, and a column's `label` must slugify to
its `id`, because Multica derives the status key from the label at create time
and later updates address the key.

## Intent: one workflow per route

`--intent` selects which of `stages.yaml#routes.intents` to provision. The
stage list is read from the pinned file, never copied here, so a stelow release
that adds a stage cannot silently fall through:

| intent | columns | workflow name |
|---|---|---|
| `new-product`, `feature` | 11 | `stelow-feature[-human]` |
| `bugfix` | 6 | `stelow-bugfix[-human]` |
| `refactor` | 7 | `stelow-refactor[-human]` |
| `investigate` | 3 | `stelow-investigate[-human]` |

`-human` appears only with `--gates human`.

## What this host loses, on purpose

- **Intent is per project, not per issue.** A Multica project has one workflow.
  If a project needs both `feature` and `bugfix` chains, pick the longer one and
  let intake say so in its comment — the adapter tells intake agent to do that.
  A strict alternative is one project per intent; that is usually worse.
- **`review_mode` cannot skip a column.** With `--gates agent` the gatekeeper
  reads `review_mode` and advances (recording a receipt) or parks the issue.
  With `--gates human` every gate is a person's. Per-gate mixed modes are not
  representable; choose the variant per project.
- **No conditional `next`.** `next_status_key` is static per column. Anything
  conditional has to be a handler decision, which is why gate columns exist at
  all rather than folding gates into the stage agents.

## Why a provisioner and not a plugin

The bb host is a plugin because bb needs UI, hooks and card lifecycle. Multica
already has the board, the runs, and the timeline: the only thing missing is a
one-time (and repeatable) declaration. That is a script, and a script is
auditable in `git diff` — a plugin that reimplements the board is not.
