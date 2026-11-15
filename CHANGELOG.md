# Changelog

All notable changes to this repository are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses
`0.x` versions while the host contract is still settling.

## [0.1.10] - 2026-11-15

### Fixed

- **0.1.9 was tagged and published with its own suite red.** The tests had run,
  through `| tail -2`, which reports the exit status of `tail`; the pipeline
  looked green because the last command in it was. The code it shipped is the
  code that ran against the live workspace, so the boards were real — the gate
  that was supposed to catch a regression was the thing that broke.

- **`scripts/release.sh`** runs the suite with no pipe in the way, refuses a
  dirty tree, reads the version from the changelog instead of being told twice,
  and refuses to re-tag what already exists. `--dry-run` prints the notes only.

- `resolve_project` and the board code used `Multica._rows`, which the tests
  replace, so a host command depended on a name the test double owns. They use
  the module-level `rows_of` the alias was already there for, and the fake now
  answers `project list` / `project create` — the two calls a live apply makes.

## [0.1.9] - 2026-11-15

### Fixed

- **`apply --board` applied the chain instead of the board.** The flag was wired
  into `plan` only, so `apply --board explore` re-converged the 18-stage workflow
  on the live project and said `intents=feature` while doing it. `plan` and
  `apply` now share `resolve_plan`, and a test fails if the two disagree again.
  Found by running it, which is the only way this class of bug shows up.

- **A board's project is resolved from its title.** `project workflow set` takes
  an id and a board names its project by title, so the first apply created the
  project and then failed to point it at the workflow. `resolve_project` looks the
  id up (title or id prefix) after creating it.

- **`plan --board` renders as a board.** It went through the chain renderer and
  died on `col["stages"]`, which a board column does not have.

## [0.1.8] - 2026-11-15

### Added

- **Two boards, declared and checkable**: `boards/explore.json` (14 single-shot
  `stelow-workflow-*` skills) and `boards/research.json` (21 `stelow-product-*`
  skills). Three columns, one skill per card, one gate. `stelow-host board`
  validates them and prints what would be created without touching a workspace;
  `stelow-host apply --board <name>` converges one, creating its project if it is
  missing. `docs/boards.md` says why one card carries exactly one skill.

- **The back-edge budget is enforced, not advised.** `doctor` reads each card's
  timeline and fails when a pair has spent its `policy.max_back_edges`; `--fix`
  marks the card. Advice in a prompt cannot notice from inside a single run that
  it is the fourth round.

- **A card idle past `policy.max_idle_hours` (48) fails the same check.** An
  invisible card and an idle card are the two ways a workflow stops delivering
  while every other check is green.

- **`card` no longer calls a card broken for running across a rename.**
  `config/columns.json#artifact_aliases` maps each declared name to the names it
  was attached under before the naming rule; the report lists those as `legacy`
  instead of as gaps. On the smoke card that is 16 of 18 present, not 2.

- **`bin/board-check.sh`** — the timer wrapper: rotates its own log, keeps a
  failure streak that survives restarts, and says so through
  `notify-telegram.sh` once the streak starts. `--status` prints streak, log size
  and last run.

## [0.1.7] - 2026-11-15

### Added

- **A back edge has a budget: two rounds.** The smoke card went audit to build
twice, and the second audit found two more real defects, so the loop was earning
its keep. A third round is no longer the reviewer deciding; it parks the card for
a person with the rows that remain. `config/columns.json` carries
`policy.max_back_edges`, the audit section and the adapter both say it, and a test
holds the number and the wording together.

## [0.1.6] - 2026-11-15

### Added

- **`stelow-host card <issue>`**: what a card kept, and where it stopped. It reads
  the card's attachments, compares them against the artifacts each column
  declares, and lists what is missing. A closed card missing files exits
  non-zero; an open card prints the gaps as owed rather than as failures.

  On the smoke card it reports 2 of 18 present, because the first half of that
  card ran before the naming rule existed. That is the point: the gap was
  invisible until something counted it.

## [0.1.5] - 2026-11-15

A card that waits on a person used to look exactly like a run that died. On the
second smoke run CAL-52 sat in `diff_gate` with no run, no marker and no nudge
until someone read the thread by hand.

### Added

- **`doctor` reads the board and names the invisible states.** A card in a gate
  column with no run and no marker (waiting, unmarked), a card in an agent column
  with no run and no marker (orphaned), and a marker on a card that is running
  (stale). All three fail `doctor`. The check is CLI reads only: it starts no
  agent, so it costs no tokens and can run on a timer.

- **`doctor --fix`** marks the cards that wait on a person and arms one 45-minute
  nudge on each, so a forgotten card comes back on its own.

- **`stages/columns.md` now ends every gate section the same way**: mark the card,
  arm one nudge, and let the person who rules remove the marker.

- **`docs/host-contract.md` says what a question is on this host**: a comment (the
  content), a label plus wakeup (the state), and a select property only when the
  same choice repeats. Multica has no ask-with-options call, and a question
  encoded as prose alone is the failure this release removes.

## [0.1.4] - 2026-11-15

Three rules taken from the smoke card's file list.

### Added

- **No version suffix in an artifact name.** `spec-tech_v1.md` and
  `spec-tech_v2.md` both ended up on the card, which is a diff nobody can make. A
  revision replaces the file under the same name; an earlier artifact that still
  applies is marked `carried forward: <name>` rather than attached twice.

- **The outcome comment opens with the position**: `stage 7/18 - tech`. A card
  with twenty comments and no position marker makes the reader reconstruct the
  chain before they can read the outcome.

## [0.1.3] - 2026-11-15

Second smoke run, eleven gaps, all fixed here.

### Added

- **Asking is a state, not a silence.** A card parked for a decision now carries
  the `needs-human` label and a wakeup that returns to it, and the instruction to
  do both lives in the adapter. On the smoke run a parked card sat in `build`
  with no run for forty minutes, and nothing on the board distinguished it from a
  run that had died.

- **Artifact names sort by stage, then by kind.** `<nn>-<kind>.<ext>`: a
  two-digit order, the kind word the stelow skill already uses, `.md` for prose
  and `.json` for data. The card now reads as a sequence instead of an
  alphabetical pile of `DECISION.md`, `spec-tech` and `spec-product_v2.md`.

- **`artifacts` per column** in `config/columns.json`, mirrored in
  `stages/columns.md` and checked against each other, so a column cannot claim to
  be finished while handing nothing over.

- **Requirement ids minted once.** Framing gives every product promise a stable
  `S1..Sn`, and design, tech, build and audit cite that id instead of restating
  the promise. The audit no longer has to translate between its own numbering and
  the spec's.

### Changed

- **Tests run once.** `build` runs the red-first proof and the unit tests for the
  code it touched; `verify` runs the integration, layout, type and lint gates and
  reports one line per command. The smoke run spent two forty-minute passes
  re-running what the other column had already run.

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
