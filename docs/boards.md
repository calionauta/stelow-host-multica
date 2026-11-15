# Boards: one card, one skill, one artifact

The stage chain in `config/columns.json` carries one idea all the way to shipped
code. That is the wrong shape for most questions: "critique this diff" does not
need eighteen statuses, and "should we charge per seat" does not need a build.

So there are three workflows, not one:

| workflow | projects | statuses | who answers |
|---|---|---|---|
| `stelow` | one per repository | the eighteen stages, with three human gates | the chain |
| `stelow-explore` | one shared `Explore` | Bucket, Doing, Review, Done | one `stelow-workflow-*` skill, then a person |
| `stelow-research` | one shared `Research` | Bucket, Doing, Review, Done | one `stelow-product-*` skill, then a person |

## Why three workflows and not three tracks

A tracker binds **one workflow to a container**, and a container is usually a
repository. The first version of this repository read that as "one flow, three
tracks inside it", with the track encoded in the status key
(`explore_run`): a card picked its shape by where it entered.

It worked, and it was wrong in the way that only shows up on a real board. One
workflow meant twenty columns, an explore card sitting beside a build card on the
same board, and a person unable to see at a glance which of three subjects a
column belonged to. A status key is not a container: it can carry a name, but it
cannot carry a project, a menu, a runner or a default.

Multica gives exactly one lever here. `project workflow set` binds a workflow; no
card-level workflow exists. So the split has to be a split of containers, and the
honest question becomes which containers deserve their own flow:

- **build** edits code, so it belongs to the repository and gets a project per
  repository;
- **explore** and **research** are questions *about* repositories, so each gets one
  shared project and the card names the repository it is about.

That is N + 2 projects instead of 3N, and the triage a person does is "which lane
does this question belong to", which they can answer, instead of "which of these
twenty columns", which they could not.

State still lives in the tracker: cards, statuses, comments, attachments. This
repository holds only the declarations, and `install --check` compares the two, so
the repository cannot drift from the live board by holding a stale copy of it.

## Asking for a specific strategy

A research card is a question plus the skill that answers it. `ask` writes both
and moves the card straight to `doing`, so nothing waits for a triage step nobody
asked for (the card was already answerable: you asked it):

```bash
./bin/stelow-host ask research "what would settle the price?" --skill pricing
./bin/stelow-host ask explore "critique the review-queue diff in PR 516" --skill codebase-critique
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

The card lands in the lane's project (`Explore` or `Research`), and the body names
the repository it is about, because the lane is the container that runs it.

## What a lane is

Three columns:

```
bucket (a person)  →  doing (one agent)  →  review (a person, can send back)
```

`bucket` is where a card becomes answerable. `doing` is the only column that works,
and it loads **exactly one** skill from the menu. `review` is the only gate, and
it answers one question: does the artifact settle what the card asked?

**Which lane a card is on** is not a guess. Both lanes use `bucket`, `doing` and
`review`, so the status cannot say: the strategy the card names decides
(`stelow-product-*` is research, `stelow-workflow-*` is explore), then its project,
and a card that neither places is reported as ambiguous rather than judged against
whichever lane sorts first. That is why the `doing` column tells the runner to
write `**Strategy:** <skill>` — that line is what `card` reads back.

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
agents, creates the workspace statuses for all three workflows, and attaches
each to its projects: the chain to every repository you name, each lane to its
own shared project (`Explore`, `Research`), created if it does not exist.

## Adding a skill to a menu

Add one line to `boards/<name>.json`:

```json
{"skill": "stelow-product-pricing", "when": "a price has to be chosen and defended"}
```

Skill names are the stelow repo's directory names, and `stelow-host board` refuses
one that does not match the board's `skill_prefix`. Re-run `install` to push it.

## Adding a fourth lane

Copy a file in `boards/`, change `board`, `workflow`, `project`, `runner`,
`skill_prefix` and the menu, add `agents/<runner>.md`, and add one entry to
`config/install.json` (a `workflows` entry with `kind: loose` plus its `tracks`
entry). The three columns and their instructions are the template; nothing else
in the repo needs to know the lane exists.
