# Operations

## First run against a real workspace

```bash
./bin/stelow-host sync              # network: pins stages.yaml + sha into stelow.lock.json
./bin/stelow-host plan              # no writes; read the whole output
./bin/stelow-host apply             # writes: skills → agents → workflow → project
./bin/stelow-host verify            # must exit 0
```

`plan` and `verify` read the live workspace; if `multica` is missing or the
workspace id is wrong they say so and `plan` falls back to the intended state.

Check these three things after the first `apply`:

1. `multica workflow get stelow-feature-human` — the step order and handlers are
   what `plan` said.
2. `multica skill list` — the skills are there with the names stelow uses (the
   import name comes from `SKILL.md`, so it matches the directory).
3. Open one issue and move it through `intake → framing` by hand. If the issue
   will not move, the status keys differ from what `steps-file` sent: re-read the
   `label`/`id` slug rule in `docs/design.md`.

## Updating stelow after a release

```bash
./bin/stelow-host sync --refresh-skills   # re-pin stages.yaml, re-pull every skill
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
multica project workflow set <project> stelow-feature-human --dry-run
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
