# stelow-host-multica

Provision **stelow** onto a [Multica](https://multica.ai) workspace with the
`multica` CLI.

**What this is:** a provisioner. No runtime, no daemon, no UI. Every write is a
`multica` CLI call; `bin/stelow-host plan` prints them before anything happens.

## Install it on a workspace (read this first)

Prerequisites: `python3` (stdlib only), an authenticated `multica` binary on
`PATH`, and `MULTICA_WORKSPACE_ID` + `MULTICA_RUNTIME_ID` in the environment
(`multica workspace list` / `multica runtime list`, or the `workspace_id` /
`runtime_id` keys in `config/host.json` — env wins). The runtime must be online
and the account must own the workspace.

```bash
python3 bin/stelow-host sync                  # pin stages.yaml + catalogs + transitions
python3 bin/stelow-host board                 # validate board declarations, no network
python3 bin/stelow-host doctor --offline      # environment and pin, no network
python3 bin/stelow-host plan --all-workflows   # what would change; no writes
python3 bin/stelow-host install --check        # does the live workspace match?
python3 bin/stelow-host install                # converge skills, agents, 3 workflows, projects
python3 bin/stelow-host verify --all-workflows # exit 1 on drift
```

`install` converges three workflows and binds each to its project:

| workflow | columns | project |
|---|---|---|
| `stelow` | the chain from `stages.yaml` (11 for `feature`) + `todo`/`done` | one per repository |
| `stelow-explore` | `bucket` → `doing` → `review` (+`done`) | shared **Explore**, 14 skills |
| `stelow-research` | same | shared **Research**, 21 skills |

Success looks like: `install --check` printing `OK` for every workflow and every
project, `doctor` ending in `all checks passed`, and `plan --all-workflows`
showing every stelow skill as `already present`. A lane card is created with
`ask`; a build card is a normal Multica issue moved into `intake`.

Failure modes worth knowing: a project bound to the wrong workflow (`--check`
says `expected stelow-explore`), a status key that does not slugify from its
label (`load_groups` refuses), and an agent missing a skill its columns own
(`doctor` names it).

## Commands

```bash
python3 bin/stelow-host sync                    # pin stages.yaml + catalog + transitions
python3 bin/stelow-host doctor                  # env, pin, ownership, back-edges, stalled cards
python3 bin/stelow-host plan --intent X         # intended state; no writes
python3 bin/stelow-host apply --intent X        # converge the chain (idempotent)
python3 bin/stelow-host install [--check]       # every workflow + project binding
python3 bin/stelow-host verify --all-workflows  # exit 1 on drift
python3 bin/stelow-host ask explore|research "<question>" [--skill NAME]
python3 bin/stelow-host card <issue>            # what a card kept, and where it stopped
python3 bin/stelow-host park <issue> --why "text"  # label, assignee and wakeup for a card that waits on a person
python3 bin/stelow-host human [name]           # list the workspace members, or choose who owns the gates
python3 tests/run.py                            # the suite, no network
```

`doctor --offline` skips the network and live-workspace checks.

## Rules

- **Three agents for the chain: `plan`, `build`, `review`** — plus one runner per
  lane (`explore-runner`, `research-runner`). Stages that share an author share
  an agent; only the gates get a separate one, because a gate is cross-checking
  and a reviewer must not share the instincts of whoever produced the work. Do
  not add an agent without a reason that survives that sentence.
- **Never copy the stage list, the intent routes, or the stage→skill ownership
  into this repo.** The first two come from the pinned `stages.yaml`, the third
  from the pinned `stage-catalog.json` (digests in `stelow.lock.json`). A stage
  with no column, or owned by a skill its agent does not load, must fail.
- **Every step names the skills it runs.** `build_steps` renders
  `## Skills this step runs` from `column_skills()`; a step that describes its
  work without naming the skill makes the agent search for it or improvise.
  `tests/run.py` fails when that block disappears.
- **Never invent a status key.** A column's key must slugify from its `label`
  (Multica derives one from the other at create time; a mismatch breaks every
  later update). `load_groups` enforces this.
- **Never invent a back-edge.** Where a rejected stage sends the run is in the
  pinned `transitions.md`; `flow_gaps` compares the board against it.
- **The column is the contract.** Column behavior lives in `stages/columns.md`
  and agent identity in `agents/`; do not describe stelow stages anywhere else.
  Lane behavior lives in `boards/*.json`, and a board file nobody declares in
  `config/install.json` fails the suite.
- Do not put host-specific policy into stelow skills — that is what
  `agents/_adapter.md` and `boards/*.json#instructions` are for.
- `plan` before `apply`. No dependency may be added: python3 stdlib + the
  `multica` binary only.
- **English only**, in code, docs, commit messages and agent instructions.
