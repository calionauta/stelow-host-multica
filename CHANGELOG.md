# Changelog

All notable changes to this repository are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses
`0.x` versions while the host contract is still settling.

## [0.1.0] - 2026-11-15

First release. A Multica workspace can now run the stelow workflow with nothing
installed inside stelow itself: the stage model stays upstream, and this
repository holds the half that is Multica's.

### Added

- **Three agents instead of eighteen.** `stelow-plan` carries `intake` through
  `tech_gate`, `stelow-build` carries `build` and `verify`, `stelow-review`
  carries `diff_gate` and `audit`. The column, not the agent, decides which stage
  instructions load — an agent that had all eighteen embedded could not be
  updated without a workspace rewrite.

- **`bin/stelow-host`**, the only thing the board and the agents share. `sync`
  writes the column config and agent instructions, `apply` reconciles a live
  workspace against them, `workflow` reports what the workspace actually has, and
  `state`/`advance` read and move the card's position through upstream
  `scripts/stelow`.

- **`config/columns.json`** with one entry per stage: who owns it, which stage
  instruction loads, and which recipe runs. `transitions.md` decides the edges;
  this file only says which agent picks a column up.

- **`docs/host-contract.md`**, written so a second host can be built from it
  rather than from this one's source. It names what a host must provide, what it
  must never mint, and the three questions `stelow check` answers.

- **`tests/run.py`**: 37 checks over the CLI surface, the config invariants, and
  the stage-to-column mapping. They assert on the files the tool writes, not on
  string presence, so a column that loses its stage instruction fails.

### Verified

- Against a live Multica workspace: agents created, skills installed from GitHub,
  a workflow bound to the project, and a card moved by hand through every column
  to confirm the transitions the host accepts match `transitions.md`.
