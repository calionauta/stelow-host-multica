# stelow-host-multica

Provision **stelow** onto [Multica](https://multica.ai): one workflow, the stage
agents that run it, and exactly the stelow skills each agent needs — from the
CLI, idempotently, with no clicks in the UI.

This is a **provisioner**, not a plugin. It ships no runtime, no UI, and no
daemon. Everything it does is `multica` CLI calls you could type yourself; it
exists so you do not have to, and so the mapping stays reviewable.

```
config/columns.json     the host's opinion: 18 stelow stages → board columns → 3 agents
config/host.json        workspace knobs: repo, ref, runtime, model, defaults
agents/*.md             agent identity (plan, build, review) + the Multica/state adapter
stages/columns.md       what each column asks of its handler
bin/stelow-host         sync | plan | apply | verify | status | doctor
docs/host-contract.md   the upstream contract this repo implements
tests/run.py            the mapping, ownership, back-edge and idempotency suite
```

## Why this exists

Multica has three things stelow needs and no way to state them declaratively:
skills as first-class objects, a workflow of status columns with per-column
handlers and instructions, and a durable issue timeline. Getting stelow onto a
workspace by hand is up to 19 skill imports, 3 agents, 6–11 status columns, and
a handful of handoffs, most of it easy to get subtly wrong (status keys must
slugify from the column label, or updates diverge from creation forever).

## Two shapes: the chain, and the boards

The chain carries one idea to shipped code. Most questions are not that, so
`boards/` declares two loose boards instead: **explore** (one `stelow-workflow-*`
stage skill applied to something that exists) and **research** (one
`stelow-product-*` skill on one decision). Three columns, one skill per card:

```bash
./bin/stelow-host board                 # validate the declarations, no network
./bin/stelow-host apply --board research
```

[`docs/boards.md`](docs/boards.md) explains why one card carries exactly one
skill, and how to add a third board.

## Watching a board that is not moving

```bash
./bin/stelow-host card <issue>     # what a card kept, and what it still owes
./bin/stelow-host doctor --fix     # mark the cards that wait on a person
./bin/board-check.sh               # the above on a timer: rotates its log, counts failures
```

`doctor` reads the board with CLI calls only — it starts no agent, so running it
every fifteen minutes costs no tokens. It fails on a card waiting in a gate with
nothing marking it, a card whose run ended with nothing queued, a marker on a
card that is running, a card past its back-edge budget, and a card nobody has
touched in two days.

## Three agents, not one per column

The mapping is deliberate: **`plan`** (triage → planning), **`build`
(execution → verification), **`review`** (the four gates + audit).

One agent per column looks like role specialization and mostly is not: the
stages it would separate are sequential work on one subject, and splitting them
multiplies issue-history re-reads and hand-offs while adding no checking. The
2026 evidence is consistent on this — under an equal token budget a single
agent matches or beats a multi-agent pipeline, multi-agent runs cost ~15x a
plain chat, and the win per 1k tokens drops from 67.7 to 13.6–42.4. What *does*
justify a separate agent is **explicit cross-checking**, which is exactly what a
stelow gate is: a reviewer that did not produce the work it judges.

So the split follows the only line in the methodology that resists merging —
author versus critic. Each agent's brief (`agents/plan.md`, `agents/build.md`,
`agents/review.md`) states its columns, what it produces, and the boundaries it
must not cross (never approve your own work, never widen scope silently, never
claim a check you did not run).

If you want the fine-grained version anyway, give separate agents distinct
names in `config/columns.json`; two columns naming the same agent get the union
of their skills, which is what makes merging safe.

## Requirements

- `multica` on `PATH`, signed in, with a workspace selected (`multica --help`).
- `python3` (stdlib only — no pip, no npm, no jq).
- A **public** `calionauta/stelow` (skills are imported by URL, per skill).

## Quickstart

```bash
# ids: export MULTICA_WORKSPACE_ID / MULTICA_RUNTIME_ID / MULTICA_PROJECT_ID
# (or fill them in config/host.json — the env wins)
./bin/stelow-host sync                     # pin stages.yaml + catalog + transitions
./bin/stelow-host doctor                   # environment, pin, and stage ownership
./bin/stelow-host plan --intent feature    # what would change; writes nothing
./bin/stelow-host apply --intent feature   # converge
./bin/stelow-host verify                   # exit 1 if the workspace drifted
```

`apply` is convergent: run it twice and the second run only updates. Skills are
imported once and then refreshed from source (`--refresh-skills`); agents and the
workflow are updated in place, never duplicated.

### Keeping the skills current

Skills are imported with `skill import --url https://github.com/<repo>/tree/<ref>/skills/<slug>`,
so Multica keeps the **source reference** on each one. That means updating is a
command, not a re-import:

```bash
./bin/stelow-host apply --refresh-skills    # multica skill refresh per skill
```

`skill refresh` re-downloads the skill from its source and replaces it in place,
keeping its id, its agent assignments and its labels — so agents pick up the new
version without being touched. Point `stelow.ref` at a tag if you want to
control when; leave it at `main` to track the repo. Nothing runs on a schedule:
make it a cron if you want it unattended.

`doctor` is the check to run first: it verifies python, the `multica` binary,
the workspace ids, the pin, that the skills are publicly importable, and the two
that matter: **every stage's owning skill is loaded by the agent that handles
that stage**, and **every back-edge points at the column stelow actually sends
the run back to** (a rejected diff review returns to execution, not to
verification). `--offline` skips the network and live-workspace checks.

## The mapping

`config/columns.json` collapses the 18 stelow stages into board columns. The
stage list itself is **never copied here** — it is read from the pinned
`stages.yaml`, so a stelow release that adds a stage either maps to a column or
fails the run loudly:

```bash
$ ./bin/stelow-host plan --intent bugfix
  ... 11 skills, 3 agents ...      # bugfix skips scope/interface/architecture
```

Intents come from `stages.yaml#routes.intents`, so the four chains you can
provision are the four chains stelow defines:

| intent | columns |
|---|---|
| `new-product`, `feature` | 11 (all) |
| `bugfix` | 6 — intake, framing, product_gate, build, verify, audit |
| `refactor` | 7 — intake, framing, tech, tech_gate, build, verify, audit |
| `investigate` | 3 — intake, framing, audit |

**Gates** are the four human review points (`gate`, `int-gate`, `plan-gate`,
`diff-gate`). `--gates human` hands them to the project lead; `--gates agent`
hands them to the `review` agent, which reads `review_mode` and either records
the receipt and advances, or parks the issue with a reason.

```bash
./bin/stelow-host apply --intent feature --gates human --project <project-id>
```

## Honest status

- **Verified**: the stage/intent/catalog parser against the real
  `calionauta/stelow@main`; ownership and back-edges against the pinned
  `stage-catalog.json` and `transitions.md`; `doctor` end to end; the mapping,
  convergence and gate wiring against an in-process fake of the CLI (78 tests,
  `python3 tests/run.py`).
- **Not verified**: a board taken from `board` to `apply --board` and then run
  end to end on a live workspace. The chain is; the boards are new.
- **Run against a live workspace** before trusting `apply` on yours: `doctor`,
  then `plan`, then `apply` on a fresh project. `docs/operations.md` lists what
  to check and what a failed run looks like.

## Related

- [`docs/boards.md`](docs/boards.md) — the loose boards, and the one-skill rule.
- [`calionauta/stelow`](https://github.com/calionauta/stelow) — the methodology.
- `bb-plugin-stelow` — the bb host: a plugin, because bb needs UI and hooks.
  This repo needs neither, so it is a script.
