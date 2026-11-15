# Operations

## First run against a real workspace

```bash
export MULTICA_WORKSPACE_ID=<workspace-uuid>   # env wins over config/host.json
export MULTICA_RUNTIME_ID=<runtime-uuid>
export MULTICA_PROJECT_ID=<project-uuid>       # optional: binds the board
./bin/stelow-host sync              # network: pins stages.yaml + sha into stelow.lock.json
./bin/stelow-host plan              # no writes; read the whole output
./bin/stelow-host apply             # writes: skills → agents → workflow → project
./bin/stelow-host verify            # must exit 0
```

`plan` and `verify` read the live workspace; if `multica` is missing or the
workspace id is wrong they say so and `plan` falls back to the intended state.

Check these three things after the first `apply`:

1. `multica workflow get stelow` — the step order and handlers are
   what `plan` said.
2. `multica skill list` — the skills are there with the names stelow uses (the
   import name comes from `SKILL.md`, so it matches the directory).
3. Open one issue and move it through `intake → framing` by hand. If the issue
   will not move, the status keys differ from what `steps-file` sent: re-read the
   `label`/`id` slug rule in `docs/design.md`.

## Updating stelow after a release

```bash
./bin/stelow-host sync                   # re-pin stages.yaml
./bin/stelow-host apply --refresh-skills   # re-pull every skill from its source
./bin/stelow-host plan                    # the new mapping, if any
./bin/stelow-host apply
./bin/stelow-host verify
```

Skills keep their id and their agent assignments across a refresh; only content
is replaced. A stelow release that adds a stage will make `apply` fail with the
stage name until `config/columns.json` maps it — that is the anti-drift check
working, not a bug.

## Switching a project that already has issues

Moving a live project onto the workflow needs the old statuses mapped:

```bash
./bin/stelow-host apply --project <id> --migrate      # uses config/host.json#migrate
./bin/stelow-host apply --project <id> --migrate --map in_progress=framing
```

Or preview the server-side mapping first:

```bash
multica project workflow set <project> stelow --dry-run
```

## Rollback

```bash
multica project workflow set <project> default     # board back to built-in columns
multica workflow delete stelow-feature-human       # then remove the workflow
```

Agents and skills are inert once the project no longer points at the workflow;
delete them when you are sure (`multica agent delete`, `multica skill delete`).

## Failure modes that matter

| Symptom | Cause | Fix |
|---|---|---|
| `apply` fails naming a stage | stelow added a stage with no column | add it to `config/columns.json` |
| a column never advances | handler agent has no runtime, or the column's `next_status_key` is wrong | `verify`, then `apply` |
| skills imported but the agent ignores them | the agent was created before the skill existed | `apply` again (`agent skills set` replaces) |
| `skill import` 404 | `calionauta/stelow` is not public, or `ref` is stale | `sync --ref <tag>` |
| `verify` reports instruction drift | you edited a column in the UI | `apply` — the repo is the source of truth |

## Run `doctor` before `apply`

`doctor` is the cheapest way to find out why a run is about to fail. It checks,
in order: python, the `multica` binary on `PATH`, `workspace_id` and
`runtime_id`, that the stage model is pinned, that the stage **owners** were read
from the catalog, that every stage's owning skill is loaded by the agent that
handles that stage, that every back-edge matches the transitions table, that the
skills are publicly importable, that the CLI is authorized (`--offline` skips
the last two), that nothing on the board waits unmarked or idle, and that no run
has been reported `running` past `policy.max_run_minutes`.

The owner check is the one that catches real drift. `stage-catalog.json` says
which skill each stage dispatches to; a column's agent must load that skill, or
the stage is dispatched to an agent that has never read its instructions. Two
edits upstream trip it:

- stelow repoints a stage at a new skill (the check names the stage and the
  agent);
- stelow adds a stage the host has no column for (`plan` fails first, naming the
  stage).

When it trips, change `config/columns.json` — never the pinned cache, and never
the stage list, which is not this repo's to keep.

## The back-edge check

`transitions.md` declares, per stage, where a rejection or a rework sends the
run. `doctor` reads it and compares the result with each column's `back_to`.
This is the difference between a board that loops and a board that only moves
forward:

| rejected at | stelow sends it back to | column that must receive it |
|---|---|---|
| `gate` | `shape` | `framing` |
| `int-gate` | `interface` | `design` |
| `plan-gate` | `planning` | `tech` |
| `diff-gate` | `execution` | `build` |
| `audit` | `execution` | `build` |
| `execution` (rework) | `shape` | `framing` |

If a column's `back_to` lands one step early — pointing a rejected diff review at
`verify` instead of `build` — the rework skips the re-execution and the loop is a
forward move with extra steps. `doctor` reports it by name.

## First run on a live workspace

1. `multica login` (browser, or `--token`), then `multica workspace list`.
2. `multica runtime list` — pick the row whose **provider** you want *and* whose
   **status is online**. A daemon registers one runtime per provider it finds,
   and an older daemon's rows linger as `offline` under the same name; binding
   agents to one of those makes every card sit still while `apply` reports
   success. If nothing is online, run `multica daemon start` on the machine that
   has the agent CLI signed in.
3. Export the ids instead of committing them: `MULTICA_WORKSPACE_ID`,
   `MULTICA_RUNTIME_ID`, `MULTICA_PROJECT_ID`.
4. `./bin/stelow-host install` — it creates the three projects (**Build**,
   **Explore**, **Research**) with `--title`, sets each workflow, and is idempotent.
   `install --check` afterwards must print three `OK` lines.
5. `sync`, `doctor`, `plan`, `install`, `verify`.

A healthy first apply prints one `+ skill` line per skill, one `+ agent` per
agent, one `+ workflow`, and `= project <id> → <workflow>`. A second apply
prints only `=` lines. `verify` must exit 0, and `doctor` must end with
`all checks passed`.

## Every stall the first real card hit, and what stops it now

The first card through the chain (eighteen statuses, two back-edges, three audit
passes) took five hours and stopped six times. Each stop is a defect in this host
if it needed a person to restart it, so each one now has a mechanism:

| when | what happened | what prevents it now |
|---|---|---|
| 13:47 | framing refused the card: the request could not produce its artifacts | `intake` asks for the decision, the known facts and the deadline before it forwards; a send-back is the loop working |
| 13:48 | the card sat in `todo`, the entry status, for 8 minutes | `todo` is in the check's known set, so a card there is an orphan; `ask build` opens on the first column, never in `todo` |
| 14:38 | `design` sat 27 minutes with no run | `doctor --fix` restarts an agent column with no run (wakeup, `policy.stall_minutes`) |
| 15:20 | `verify` sat 45 minutes with no run | same restart, on the same timer |
| 17:12 | `build` finished and parked with one ruling needed, unmarked | a parked run marks `needs-human` and arms one 45-minute nudge |
| 18:19 | audit sent the card back: two requirements short | the back edge, with a budget of two, then a person |

The two stalls that needed a human mention to restart are the ones that matter:
the workflow hands the card forward correctly and the next stage simply does not
begin. Nothing inside a run can notice that, because the run is over. Only a
reader of the board can, and the reader is the timer.

## What splitting the chain into three workflows found (2026-11-15)

The board used to hold every shape in one graph, as tracks. Splitting it into
three workflows found four things a single board had been hiding, all of them by
running cards rather than by reading code:

| symptom | cause | what prevents it now |
|---|---|---|
| an Explore card was told it owed `01-spec-product.md` … `18-audit-table.md` | `card` compared every card against the chain's artifact list | a lane card owes one artifact; `card` names the lane and the strategy it judged it against |
| a Research card reported `lane: explore` | both lanes use `bucket`/`doing`/`review`, and the first board alphabetically answered | the strategy decides, then the project; a card neither places is refused as ambiguous |
| `doing` said "load exactly one skill from the menu" and carried no menu | the working column's text was pushed without the menu block, and only a helper the doctor used assembled it | `board_plan` appends the menu; the step is 2696 characters on the research lane |
| a run sat `running` for half an hour after its process died | a tracker reports a run as running until something ends it | `doctor` compares `started_at` with `policy.max_run_minutes`; `--fix` marks and re-arms |

The lesson repeats the one above: a card that waits with nothing saying so is the
failure mode of every tracker, and only a reader of the board catches it.

Run it every five minutes, not every fifteen: it starts no agent, so a shorter
interval costs nothing, and five minutes is the difference between a stage that
looks stopped and one that is.

## Smoke test after provisioning

The point is not that the workflow exists; it is that a card moves and comes
back. Two runs, one card:

```bash
# 1. a card in the first column is handed to the first agent and starts a run
multica issue create --project <id> --status intake --title "Smoke: intake hands off" \
  --description-file smoke.md
multica issue runs <issue-id>            # a run appears, then completes
multica issue timeline <issue-id>        # comment + "intake → framing" by the agent

# 2. the gate: with --gates agent the step hands to the reviewer; a rejection
#    must land on the column transitions.md names (/bin/stelow plan shows it)
multica issue status <issue-id> product_gate
multica issue timeline <issue-id>        # product_gate → framing, not design
```

`multica issue usage <issue-id>` reports input, output and cache-read tokens per
run — useful for sizing a stage before running it on real work.

If the card does not move, check in this order: `multica daemon status`,
`runtime list` (online?), `issue runs` (a run at all?), then `daemon logs`.
