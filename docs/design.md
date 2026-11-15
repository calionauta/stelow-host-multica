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
| `review_mode` | **repo** (`.stelow/state.md`) | read by the review agent; Multica cannot skip a column |
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
| `product_gate` | gate | person or `review` |
| `design` | scope, interface | agent |
| `interface_gate` | int-gate, selection | person or `review` |
| `tech` | architecture, planning | agent |
| `tech_gate` | plan-gate | person or `review` |
| `build` | execution | agent |
| `verify` | verification | agent |
| `diff_gate` | diff-gate | person or `review` |
| `audit` | audit | agent |

Every stage must land in exactly one column: a stage with no column fails the
run instead of being silently dropped, and a column's `label` must slugify to
its `id`, because Multica derives the status key from the label at create time
and later updates address the key.

## Intent: one chain, four routes

`--intent` selects which of `stages.yaml#routes.intents` to provision. The
stage list is read from the pinned file, never copied here, so a stelow release
that adds a stage cannot silently fall through:

| intent | columns |
|---|---|
| `new-product`, `feature` | 11 |
| `bugfix` | 6 |
| `refactor` | 7 |
| `investigate` | 3 |

The workflow's name does not change with the intent. It used to
(`stelow-feature-human`, `stelow-bugfix-agent`, ...), which read as one workflow
per route; but a tracker binds one workflow per project, and two projects with
different intents are two projects, not two workflows in one board. Applying a
different intent replaces the chain in place, which is what "this repository
runs the bugfix chain for now" means.

## What this host loses, on purpose

- **Intent is per project, not per issue.** A Multica project has one workflow.
  If a project needs both `feature` and `bugfix` chains, pick the longer one and
  let intake say so in its comment — the adapter tells intake agent to do that.
  A strict alternative is one project per intent; that is usually worse.
- **`review_mode` cannot skip a column.** With `--gates agent` the review agent
  reads `review_mode` and advances (recording a receipt) or parks the issue.
  With `--gates human` every gate is a person's. Per-gate mixed modes are not
  representable; choose the variant per project.
- **No conditional `next`.** `next_status_key` is static per column. Anything
  conditional has to be a handler decision, which is why gate columns exist at
  all rather than folding gates into the stage agents.

## Three agents, and why not more

The board has 11 columns; the workspace has 3 agents.

| agent | columns | stages |
|---|---|---|
| `plan` | intake, framing, design, tech | triage → planning |
| `build` | build, verify | execution, verification |
| `review` | the four gates, audit | gate, int-gate, plan-gate, diff-gate, audit |

The temptation is one agent per column, which reads as specialization and mostly
is not: those stages are sequential work on one subject. Splitting them
multiplies issue-history re-reads and hand-offs and adds no checking — the 2026
measurements are blunt about it (single agent matches or beats a multi-agent
pipeline at equal token budget; ~15x tokens for a multi-agent run; tasks per 1k
tokens 67.7 → 13.6–42.4). The one split that survives is **author versus
critic**, because a gate is explicit cross-checking and the reviewer must not
share the instincts of whoever produced the work.

Two consequences the code enforces:

- `config/columns.json` names an agent on **every** group, including the gates
  (the reviewer is the handler when `--gates agent`).
- Two columns naming the same agent get the **union** of their skills. Without
  that union the second column's stages would be owned by skills its agent never
  loaded, which is the failure `doctor` exists to catch.

## The catalog is read, not copied

`sync` pins three files: `stages.yaml` (routes and intents), the generated
`stage-catalog.json` (which skill owns each stage), and the generated
`references/transitions.md` (where each stage sends the run on reject or rework). The second one is what makes
the *ownership* check possible: `doctor` asserts that the agent handling a stage
loads that stage's skill, so a stelow release that repoints a stage fails loudly
here instead of silently dispatching the stage to an agent that never read it.

Neither file is parsed for anything this repo could keep itself. The only local
opinion is `config/columns.json`: which stages group into which board column.

## Why a provisioner and not a plugin

The bb host is a plugin because bb needs UI, hooks and card lifecycle. Multica
already has the board, the runs, and the timeline: the only thing missing is a
one-time (and repeatable) declaration. That is a script, and a script is
auditable in `git diff` — a plugin that reimplements the board is not.
