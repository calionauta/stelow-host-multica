# stelow-host-multica

Provision **stelow** onto [Multica](https://multica.ai): one workflow, the stage
agents that run it, and exactly the stelow skills each agent needs — from the
CLI, idempotently, with no clicks in the UI.

This is a **provisioner**, not a plugin. It ships no runtime, no UI, and no
daemon. Everything it does is `multica` CLI calls you could type yourself; it
exists so you do not have to, and so the mapping stays reviewable.

```
config/columns.json     the host's opinion: 18 stelow stages → board columns
config/host.json        workspace knobs: repo, ref, runtime, model, defaults
agents/*.md             agent identity + the Multica/state adapter rules
stages/columns.md       what each column asks of its handler
bin/stelow-host         sync | plan | apply | verify | status
docs/host-contract.md   the upstream contract this repo implements
tests/run.py            the mapping and idempotency suite
```

## Why this exists

Multica has three things stelow needs and no way to state them declaratively:
skills as first-class objects, a workflow of status columns with per-column
handlers and instructions, and a durable issue timeline. Getting stelow onto a
workspace by hand is ~17 skill imports, 7–8 agents, 6–11 status columns, and a
handful of handoffs, most of it easy to get subtly wrong (status keys must
slugify from the column label, or updates diverge from creation forever).

## Requirements

- `multica` on `PATH`, signed in, with a workspace selected (`multica --help`).
- `python3` (stdlib only — no pip, no npm, no jq).
- A **public** `calionauta/stelow` (skills are imported by URL, per skill).

## Quickstart

```bash
# fill multica.workspace_id, multica.runtime_id and (optionally) multica.project_id
./bin/stelow-host sync                     # pin stages.yaml + catalog + transitions
./bin/stelow-host doctor                   # environment, pin, and stage ownership
./bin/stelow-host plan --intent feature    # what would change; writes nothing
./bin/stelow-host apply --intent feature   # converge
./bin/stelow-host verify                   # exit 1 if the workspace drifted
```

`apply` is convergent: run it twice and the second run only updates. Skills are
imported once and then refreshed from source (`--refresh-skills`); agents and the
workflow are updated in place, never duplicated.

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
  ... 11 skills, 5 agents ...      # bugfix skips scope/interface/architecture
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
hands them to a gatekeeper agent that reads `review_mode` and either records the
receipt and advances, or parks the issue with a reason.

```bash
./bin/stelow-host apply --intent feature --gates human --project <project-id>
```

## Honest status

- **Verified here**: the stage/intent/catalog parser against the real
  `calionauta/stelow@main`; `doctor` end to end; the mapping, ownership and
  convergence logic against an in-process fake of the CLI (27 tests,
  `python3 tests/run.py`).
- **Not yet verified**: a live workspace. The exact CLI surface was read from
  Multica's source (`server/cmd/multica`), not from a running instance. Run
  `doctor` and `plan` against your workspace before trusting `apply`, and read
  `docs/operations.md` for the first-run checks.

## Related

- [`calionauta/stelow`](https://github.com/calionauta/stelow) — the methodology.
- `bb-plugin-stelow` — the bb host: a plugin, because bb needs UI and hooks.
  This repo needs neither, so it is a script.
