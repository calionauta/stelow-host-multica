# Changelog

All notable changes to this repository are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses
`0.x` versions while the host contract is still settling.

## [0.1.2] - 2026-11-15

### Fixed

- **A network blip read as a missing skill.** `apply` fetches each `SKILL.md`
  from the pinned upstream and treated *any* `OSError` as "not at the pinned
  path", so one dropped connection refused the first write with a message naming
  a skill that was perfectly fine. Transport errors now retry once and then say
  what happened (`cannot reach ...`), and only a real `404` counts as missing.

- **`MULTICA_BIN` did not exist.** The three ids could come from the
  environment but the CLI path could not, which forced an absolute path into
  `config/host.json` on every machine whose `multica` is not on `PATH`. The
  errors that send you there now name the variable as well as the file.

## [0.1.1] - 2026-11-15

The first end-to-end card found four things the contract left to chance.

### Fixed

- **Artifacts were pasted into comments.** A design stage shipped wireframes, a
  contrast table and a scope map as a 6,700-character comment; the next column
  and the person reviewing could neither download them nor diff the next
  version. `_adapter.md` now says artifacts leave as files (`--attachment`),
  the body carries the decision and the file list, and every gate column reads
  the attachments rather than the prose.

- **Verify ran the whole suite.** The column literally instructed it, and one
  card sat in verify for fifty minutes while a narrow run would have reported
  the same result in three. Verify now picks the tests that can catch the
  change, names the command and its result, and reaches for the full suite only
  when the change is cross-cutting.

- **No command outlived the turn.** The same run could not read the steering
  message sent to it, because it was inside one uncapped command. Every command
  is now capped (`timeout 300`), and anything longer runs in the background.

- **A long stage looked dead.** Design ran twenty-eight minutes with nothing on
  the card and the reviewer had to ask whether it was alive. One interim line
  per ten minutes is now part of the contract.

### Added

- **The card is English.** Comments, artifacts, commit subjects and PR
  descriptions. One card ended up with an English plan, an English critique and
  Portuguese gate answers.

- **Five guards in `tests/run.py`**: the attachment rule, the scoped verify, the
  English rule, the liveness line and the command cap are asserted against the
  instruction files, plus a repository-wide check that no Portuguese text comes
  back. 43 checks.

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
