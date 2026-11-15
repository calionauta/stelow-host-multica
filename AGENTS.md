# stelow-host-multica

Provision **stelow** onto a Multica workspace with the `multica` CLI.

**What this is:** a provisioner. No runtime, no daemon, no UI. Every write is a
`multica` CLI call; `bin/stelow-host plan` prints them before anything happens.

## Commands

```bash
python3 bin/stelow-host sync                # pin stages.yaml from calionauta/stelow
python3 bin/stelow-host plan --intent X     # intended state; no writes
python3 bin/stelow-host apply --intent X    # converge (idempotent)
python3 bin/stelow-host verify              # exit 1 on drift
python3 tests/run.py                        # the suite (18 tests, no network)
```

## Rules

- **Never copy the stage list or intent routes into this repo.** They are read
  from the pinned `stages.yaml` (`buffers` → `.stelow-cache/stages.yaml`,
  digest in `stelow.lock.json`). A stage with no column must fail the run.
- **Never invent a status key.** A column's key must slugify from its `label`
  (Multica derives one from the other at create time; a mismatch breaks every
  later update). `load_groups` enforces this.
- **The column is the contract.** Column behavior lives in `stages/columns.md`
  and agent identity in `agents/`; do not describe stelow stages anywhere else.
- Do not put host-specific policy into stelow skills — that is what
  `agents/_adapter.md` is for.
- `plan` before `apply`. No dependency may be added: python3 stdlib + the
  `multica` binary only.
