# Boards: one card, one skill, one artifact

The stage chain in `config/columns.json` carries one idea all the way to shipped
code. That is the wrong shape for most questions: "critique this diff" does not
need eighteen statuses, and "should we charge per seat" does not need a build.

So the same workflow carries three **tracks**, and a card picks one by the status
it enters.

| track | first status | statuses | who answers |
|---|---|---|---|
| build | `intake` | eighteen | the chain, with three human gates |
| explore | `explore_run` | `explore_open`, `explore_run`, `explore_review` | one `stelow-workflow-*` skill, then a person |
| research | `research_run` | `research_open`, `research_run`, `research_review` | one `stelow-product-*` skill, then a person |

## Why one workflow and not three boards

A tracker binds **one flow to a container**, and a container is usually a
repository. That rules out the obvious design: three boards would mean three
containers per repository — the repository itself, plus two that are not
repositories at all. Every question would need a person to decide which container
it belongs in before anything ran, which is the triage the boards exist to remove.

With one flow and three tracks, the repository stays the container and the
question stays where the work is. The status key carries the track name
(`explore_run`), with an underscore because tracker status keys only admit
lowercase letters, digits and underscores. A card's status therefore says which
shape it is walking, and no two tracks can collide on `review`.

State lives in the tracker: cards, statuses, comments, attachments. This
repository holds only the declarations, and `install --check` compares the two, so
the repository cannot drift from the live board by holding a stale copy of it.

## Asking for a specific strategy

A research card is a question plus the skill that answers it. `ask` writes both
and moves the card straight to `run`, so nothing waits for a triage step nobody
asked for:

```bash
./bin/stelow-host ask research "is R$97/mo defensible for a solo consultant?" --skill pricing
./bin/stelow-host ask explore "critique the review-queue diff in PR 516" --skill diff-review
./bin/stelow-host ask build "cards must not stall"
```

`--skill` takes the tail (`pricing`) or the full name. An unknown name is refused
with the menu, because a typo that silently becomes "the runner picks" is a card
that answers a different question than the one asked. Without `--skill` the card
says so on purpose, and the runner must name its choice in one line.

By hand, the same thing is one line in the description:

```
**Strategy:** stelow-product-pricing
```

That line wins over the runner's own choice; it is the first rule the `run`
column gives the agent.

The card lands in the project you name, else the configured one, else the track's
own — because the container is the repository you are working in, not the track.

## What a loose track is

Three columns:

```
open (a person)  →  run (one agent)  →  review (a person, can send back)
```

`open` is where a card becomes answerable. `run` is the only column that works,
and it loads **exactly one** skill from the menu. `review` is the only gate, and
it answers one question: does the artifact settle what the card asked?

## Why a board and not a chat

A card names three things a chat message does not: which skill ran, what artifact
came out, and who read it. That is what makes an answer auditable a month later,
and it is why this is a board with one gate instead of a conversation.

## The rule that keeps it short

**One card, one skill.** Not for tidiness: a card that runs two skills produces
two half artifacts, no review, and nobody able to say what was decided. When the
runner sees a card that needs a second skill, it parks the card and names the
cards it should become. A person splits it, because splitting is a decision.

The corollary is that a menu entry needs a `when`. A runner choosing between
twenty-one skill names is guessing; choosing on "the price has to be defended" is
deciding.

## Checking before it touches a workspace

```bash
./bin/stelow-host board              # every file in boards/
./bin/stelow-host board research     # one of them
./bin/stelow-host install --check    # does the live workspace match the declaration?
```

`board` validates a declaration and prints exactly what would be created: columns,
who owns each, how many skills the menu carries. It makes no network call. The
rules it enforces are the ones whose absence produces a silent failure on a real
card — two working columns, a menu entry with no reason, a send-back pointing at a
status that does not exist, a runner with no `agents/<name>.md` (an empty prompt
that runs and says nothing).

## Installing

```bash
./bin/stelow-host install --all-projects   # one project per repository
./bin/stelow-host install --project stelow # or just this one
```

That imports every menu's skills at the pinned stelow ref, creates the runner
agents, creates the workspace statuses, converges the one workflow, and attaches
it to the projects you name.

## Adding a skill to a menu

Add one line to `boards/<name>.json`:

```json
{"skill": "stelow-product-pricing", "when": "a price has to be chosen and defended"}
```

Skill names are the stelow repo's directory names, and `stelow-host board` refuses
one that does not match the board's `skill_prefix`. Re-run `install` to push it.

## Adding a fourth track

Copy a file in `boards/`, change `board`, `workflow`, `project`, `runner`,
`skill_prefix` and the menu, add `agents/<runner>.md`, and add one entry to
`config/install.json`. The three columns and their instructions are the template;
nothing else in the repo needs to know the track exists.
