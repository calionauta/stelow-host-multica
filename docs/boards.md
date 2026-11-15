# Boards: one card, one skill, one artifact

The stage chain in `config/columns.json` exists to carry one idea all the way to
shipped code. That is the wrong shape for most questions. "Critique this diff"
does not need eighteen stages, and "should we charge per seat" does not need a
build. A chain that long is a tax on every question that is not a feature.

So there are two loose boards, declared in `boards/`:

| board | workflow | project | menu |
|---|---|---|---|
| `explore` | `stelow-explore` | Explore | the 14 single-shot `stelow-workflow-*` skills |
| `research` | `stelow-research` | Research | the 21 `stelow-product-*` skills |

Both are three columns:

```
open (a person)  →  run (one agent)  →  review (a person, can send back)
```

`open` is where a card becomes answerable. `run` is the only column that works,
and it loads **exactly one** skill from the menu. `review` is the only gate, and
it answers one question: does the artifact settle what the card asked?

## Why a board and not a chat

A card names three things a chat message does not: which skill ran, what artifact
came out, and who read it. That is what makes a research answer auditable a month
later, and it is why this is a board with one gate instead of a conversation.

## The rule that keeps it short

**One card, one skill.** Not for tidiness: a card that runs two skills produces
two half artifacts, no review, and nobody able to say what was decided. When the
runner sees a card that needs a second skill, it parks the card and names the
cards it should become. A person splits it, because splitting is a decision.

The corollary is that a menu entry needs a `when`. A runner choosing between
twenty-one skill names is guessing; choosing on "the price has to be defended"
is deciding.

## Checking a board before it touches a workspace

```bash
./bin/stelow-host board              # every file in boards/
./bin/stelow-host board research     # one of them
```

That validates the declaration and prints exactly what would be created: columns,
who owns each, how many skills the menu carries. It makes no network call. The
rules it enforces are the ones whose absence produces a silent failure on a real
card — two working columns (a chain pretending to be a board), a menu entry with
no reason, a send-back pointing at a status that does not exist, a runner with no
`agents/<name>.md` (an empty prompt that runs and says nothing).

## Applying one

```bash
./bin/stelow-host apply --board research
```

That imports the menu's skills at the pinned stelow ref, creates the runner
agent, creates the workflow, creates the project if it does not exist yet, and
points the project at the workflow. Cards then move through three columns instead
of eleven.

## Adding a skill to a menu

Add one line to `boards/<name>.json`:

```json
{"skill": "stelow-product-pricing", "when": "a price has to be chosen and defended"}
```

Skill names are the stelow repo's directory names, and `stelow-host board` refuses
one that does not match the board's `skill_prefix`. Re-run `apply --board` to push
it.

## Adding a third board

Copy a file in `boards/`, change `board`, `workflow`, `project`, `runner`,
`skill_prefix` and the menu, and add `agents/<runner>.md`. The three columns and
their instructions are the template; nothing else in the repo needs to know the
board exists.
