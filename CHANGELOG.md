# Changelog

All notable changes to this repository are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses
`0.x` versions while the host contract is still settling.

## [0.6.0] - 2026-11-15

### Fixed

- **A human gate now assigns the card to the person it belongs to.** The step handler
  was `project_lead`, and the tracker's `project_lead` assigns nobody: a probe card
  moved into `diff_gate` came out with `assignee: null`, so CAL-57 sat at the gate
  twice with no owner and no notification. Gates now hand off to a **member**
  (`MULTICA_MEMBER_ID` / `human.member_id`), which the API does assign. `creator` is
  not a valid handler — the CLI help lists it, the API rejects it — so a card opened
  by an agent still needs `park`.
- `build_steps` refuses to build a human gate without a member: a gate with nobody to
  hand it to is the bug, not a configuration.

### Added

- `doctor` gained **"every gate names the person who owns it"**, and `--fix` re-points
  a drifted gate with `workflow handoff set`, preserving its next/back/instructions.

## [0.5.0] - 2026-11-15

### Added

- **Gate columns say who acts: `Your call · product | interface | tech | diff`.**
  "Diff gate" read like one more agent stage, so a card waiting on a person looked
  like a card in progress. `columns.json` declares `board_name`, `apply` puts it on the
  workspace status (`issue-status update --name` — the key never moves, so no card is
  migrated), and `doctor` fails when a gate status has drifted back.

### Changed

- `doctor --fix` renames drifted gate statuses along with the rest of its repairs.

## [0.4.0] - 2026-11-15

### Added

- **A card that waits on a person is now handed to that person.** `stelow-host park
  <issue>` adds `needs-human`, assigns the card to whoever opened it (falling back to
  `config/host.json#human.member_id`), comments what is owed and re-arms the wakeup —
  the four steps as one, because in practice they drifted apart.

### Changed

- `doctor` gained **"every waiting card is assigned to a person"**, and `--fix` now
  assigns as well as labels. A `needs-human` marker with an agent as assignee reads as
  "someone is on it" to every reader and every check.
- `agents/_adapter.md` parking protocol now includes the assignment and the reason: on
  CAL-57 the diff gate was reached with no marker and an owner that was still the agent
  that wrote the code, so the person who asked was never told it was their turn.

## [0.3.9] - 2026-11-15

### Fixed

- **A queued run that never starts is now visible.** It counts as active, so the
  card is no orphan; it has no `started_at`, so it is no zombie either. A daemon
  restart left one holding a card in `verify` with nothing to see. `doctor` compares
  a queued run's `created_at` against `policy.max_queue_minutes` (10).
- **A queued run could hide a long-running one.** The zombie check took `min()` over
  raw `started_at` values, so a blank from the queued run won and the card was
  skipped.

## [0.3.8] - 2026-11-15

### Fixed

- **A passing check printed a sentence about a card that was not there.**
  `doctor` rendered `run ended, nothing queued: ` on a healthy board, because the
  detail string was assembled before the list was known to be empty. A warning that
  appears when nothing is wrong teaches people to skip the warnings.

## [0.3.7] - 2026-11-15

### Documentation

- The README links **stelow** (and the skills tree) instead of naming it bare: a
  reader arriving from a search hit has no way to tell the provisioner from the
  methodology it provisions.

## [0.3.6] - 2026-11-15

### Documentation

- `docs/operations.md` named `stelow-feature-human` in two commands. That workflow
  no longer exists: the chain is called `stelow`, and the intent changes its columns.

## [0.3.5] - 2026-11-15

### Fixed

- **`verify` reported every lane as drift.** It passed the project's *title* to
  `project workflow get`, which answers about a project id, so `Explore` and
  `Research` read as "does not use the workflow" on a converged workspace. A check
  nobody can satisfy is a check nobody runs.

### Documentation

- `docs/operations.md` records the four things splitting the board found, each with
  the mechanism that stops it: a lane card judged against the chain's artifacts, a
  research card reported as explore, a working column with no menu, and a run that
  stayed `running` after its process died.

## [0.3.4] - 2026-11-15

### Added

- **A run that has been "running" too long is now visible.** A tracker reports a run
  as running until something ends it, so a run whose process died looks exactly like
  a slow one: the card holds a run, has no comment and no marker, and every check
  called it healthy. `doctor` now compares each active run's `started_at` against
  `policy.max_run_minutes` (90 by default) and, with `--fix`, marks the card and
  re-arms it. This is the third shape of the same failure: a card that waits with
  nothing saying so.

## [0.3.3] - 2026-11-15

### Fixed

- **The lane's working column carried no menu.** `build_steps` pushed the board's
  column text as written, and the menu was only assembled by a helper the doctor
  used. Live, `doing` was 733 characters ending in "load exactly one skill from the
  menu" with no menu: it only worked because `ask` writes the strategy onto the
  card. The plan now appends the menu, so a hand-typed card has one too.
- **`doctor` could not see a lane card.** Its set of known statuses came from the
  same helper, which prefixes keys (`explore_bucket`) while the live workflow uses
  `bucket`. Every lane card was invisible to the stalled and queued checks.

### Changed

- `AGENTS.md` is now the install runbook — prerequisites, environment variables,
  command order, what success and failure look like — plus the rules. `llms.txt`
  indexes the same material for a reader that starts outside GitHub.
- `apply`/`install` help no longer describe one workflow carrying every track, and
  `docs/design.md` states that the intent changes the columns, not the workflow's
  name.
- `tests/run.py` now fails when a pushed step loses its skills block, when a board
  file is not declared in `config/install.json`, and when two workflows claim the
  same project.

## [0.3.2] - 2026-11-15

### Changed

- **The `doing` column names the line the board reads.** It asked the runner to say
  which skill it picked, and `card` parses `**Strategy:** <skill>`; the instruction
  now spells that line out, so a run cannot satisfy the column and still leave the
  card unplaceable.

## [0.3.1] - 2026-11-15

### Fixed

- **`card` read a lane card against the build chain.** An Explore card was told it
  owed `01-spec-product.md` through `18-audit-table.md`, which is true of no card
  on that board. A lane card now owes one artifact and `card` says which lane and
  which strategy it judged it against.
- **A research card was reported as `lane: explore`.** Both lanes use `bucket`,
  `doing` and `review`, and the first board alphabetically answered. The strategy
  the card names decides, then its project, and a card that neither places is
  refused as ambiguous instead of guessed.

## [0.3.0] - 2026-11-15

The board had three subjects and twenty columns. Now it is three workflows, and
every step names the skills it runs.

### Changed

- **One workflow became three: `stelow`, `stelow-explore`, `stelow-research`.**
  A tracker binds one workflow to a container, and the previous version read that
  as "one flow, three tracks inside it", with the track encoded in the status key
  (`explore_run`) and the card picking its shape by where it entered. It worked
  and it was wrong in the way that only shows on a real board: an explore card sat
  beside a build card, a column could not say which of three subjects it belonged
  to, and a status key cannot carry a menu, a runner or a default. Build edits
  code, so it keeps a project per repository; explore and research are questions
  about repositories, so each owns one shared project (`Explore`, `Research`) and
  the card names the repository it is about — N + 2 projects instead of 3N.
- **The lanes use the tracker's own vocabulary**: `Bucket` (a person makes the
  card answerable), `Doing` (one agent, one skill), `Review` (a person, can send
  back), then `Done`. `Review` stays a column of its own instead of hiding inside
  `Doing`, because that gate is the only thing standing between an artifact and
  someone acting on it.
- **The chain's workflow name is declared, not derived.** `stelow-feature-human`
  and friends are gone: what varies with the intent is the columns, not the name.
  `--intent bugfix` converges the same `stelow` workflow with the bugfix columns.

### Added

- **Every step names the skills it runs.** A column's skills are the ones its
  stages declare (`stages.yaml` into `data/stage-skills.json`) plus the support
  skills the host adds for it, rendered into the step's own instructions. Before
  this, a column described its work for six hundred characters and never named the
  skill carrying the method, so the agent searched for it or improvised one.
- **`--all-workflows`** on `plan`, `apply`, `verify` and `status`, and
  `--workflow <id>` to address one. `install` always means all three.

### Fixed

- **`install --check` looks at every workflow and every project.** It reported
  green for a workspace where the `Explore` project ran the build chain, which is
  the one mistake that puts an explore card through eighteen stages.

## [0.2.1] - 2026-11-15

Three findings from the canary card that proved the tracks (CAL-54), none of which
the declaration could see.

### Fixed

- **The step that says "pick from the menu" now carries the menu.** The menu lived
  only in `boards/<name>.json`, so the runner had to search the filesystem for it —
  which it did, and reported that it had, and named the divergence: twenty-one
  skills on the agent, eight in the brief, and the one the card named missing from
  both lists. `menu_block` renders every `skill` with its `when` into the step, so
  the rule and the brief are the same object.

- **Agent names no longer double their prefix.** Boards named their runner
  `stelow-research-runner`, which `agent_name` prefixed again into
  `stelow-stelow-research-runner`. The boards name `research-runner` now, the two
  stale agents are archived, and `board` refuses a runner that already carries the
  prefix.

### Removed

- The three pre-consolidation workflows in the live workspace, which had no
  projects attached and whose status keys invited a provisioning script to
  re-adopt the old shape.

## [0.2.0] - 2026-11-15

**Breaking, deliberately.** Three projects named Build/Explore/Research was the
wrong answer to the right question. A tracker binds one flow to a container, and a
container is a repository, so three boards meant three containers per repository
and a triage step before anything ran.

### Changed

- **One workflow, three tracks.** `config/install.json` declares the workflow
  `stelow` and the tracks `build` / `explore` / `research`; `install` converges one
  flow whose status keys carry the track (`explore_run`), and attaches it to the
  projects you name — `install --all-projects` for one project per repository. A
  card picks its track by the status it enters, and `ask` moves it there.

- **`ask` lands in the container you are working in**: `--project`, else the
  configured project, else the track's own. The container is the repository, not
  the track.

- **Statuses are created before the workflow that wires them.** A step pointing at
  a status created in the same request is rejected, and a replaced workflow used to
  drop a column a card was sitting in. `ensure_statuses` fixes both, and status keys
  use underscores because keys only admit lowercase letters, digits and `_`.

- **`install --check` compares steps, not just names**: every declared status must
  be in the live workflow, and every named project must point at it.

### Fixed

- The chain's last column handed off to the first loose column, because the linear
  default does not know where a track ends. It ends at `done` now.

- `IdMap` stands in for an agent id that does not exist yet, so a check can compare
  steps on a workspace mid-install instead of raising.

### Removed

- `config/projects.json` and the per-board install path. `apply --board` still
  converges a single board for a workspace that genuinely wants a separate
  container; it is no longer the recommended shape.

## [0.1.13] - 2026-11-15

### Fixed

- **The orphan check reported every finished card.** `done` has no run and no
marker, which is correct, so adding terminal statuses to the known set made both
closed cards on the board read as abandoned. `TERMINAL_STATUSES` excludes them in
both checks, with a test that says why. The five-minute timer caught this within
minutes of the release that introduced it, which is the closest thing to a
regression test for a regression test.

## [0.1.12] - 2026-11-15

Everything here came out of reading the first real card's timeline end to end and
asking, for each stop, whether a mechanism prevents it or whether it needed a
person to notice. Two of the six stops needed a person.

### Added

- **`doctor --fix` restarts a stage that stopped.** An agent column with no run is
a stage whose run ended without moving the card; it gets a wakeup with
`policy.stall_minutes` (5) and an instruction to finish one of two ways rather
than start over. On the smoke card that was 27 minutes in `design` and 45 in
`verify`, both ended by a human mention.

- **A card in `todo` is an orphan, not invisible.** `todo` is the entry status
every workflow starts from and it has no handler, so a card left there does
nothing while looking alive. It is not a group in `columns.json`, which is why
the first version of the check could not see the eight minutes the smoke card
spent there.

- **`ask build "<title>"`** opens a card on the eighteen-status chain, in the
first column rather than in `todo`.

### Fixed

- **`install --check` failed on three correct projects.** `project workflow get`
returns the whole workflow object, not `{"workflow": name}`; `workflow_name_of`
now reads both shapes, and a name collision with the chain's own `workflow_name`
is why it is spelled that way.

- **`install` could not create the chain's project**, only a board's. Creation is
one path now, gated on `create_project`/`_board` so a mistyped `--project` still
fails loudly instead of creating something.

- The timer runs every five minutes, not fifteen. It starts no agent, so the
interval is free, and five minutes is the difference between a stage that looks
stopped and one that is.

## [0.1.11] - 2026-11-15

### Added

- **`install` converges the whole workspace: three boards, three projects.**
  `config/projects.json` declares **Build** (the eighteen-status chain),
  **Explore** and **Research**; `install` runs them in order and `install --check`
  verifies each project still points at its declared workflow, writing nothing.
  They are projects because a card belongs to a project and a project has one
  workflow — three column sets cannot share one.

- **`ask <board> "<question>" --skill <name>`** writes a card, fills in the
  strategy line and moves it to `run`, so nothing waits in `open` for a triage
  nobody asked for. The skill may be the tail (`pricing`) or the full name; an
  unknown one is refused with the menu instead of quietly becoming "the runner
  picks". `--dry-run` prints and writes nothing.

- `docs/boards.md` answers where the state lives (Multica, not this repo) and how
to name a strategy by hand, in one line.

### Fixed

- The test harness now mirrors `boards/` into its temporary root, which is what
  let three of the new tests find real bugs instead of passing: `--dry-run`
  created the card anyway, and the fake CLI did not answer the two calls `ask`
  makes.

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
