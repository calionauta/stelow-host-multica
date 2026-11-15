# Proposal: a state contract for stelow hosts

Status: **proposal, not landed**. Written from implementing two hosts
(`bb-plugin-stelow`, this repo) against the same methodology.

## The problem, stated precisely

stelow already declares an **execution** contract as data, per stage:
`recipe`, `required_capabilities`, `preferred_capabilities`, `write_policy`
(`stages.yaml` + `recipes.schema.json`). A host negotiates capabilities and
refuses a stage it cannot honour. That contract works.

There is **no equivalent for state**. `state.md` is described once in
`references/state-contract.md` (265 lines) and then referenced by 31 of 32
skills, each of which asks the model to compute its own `next-candidate` and
append a `## Hand-off` block. On a host with a board, both of those duplicate
something the host already mints correctly.

## What NOT to do

1. **Do not add a "host documentation" every host implements freely.** An
   abstraction with no machine-checkable side becomes *n* dialects. stelow's
   existing pattern is the right one: canonical data (`stages.yaml`) → generated
   mirror (`transitions.md`) → validated by the helper → pinned by tests. A
   prose contract gets none of that, and the third host invents a fourth shape.
2. **Do not delegate semantics.** No host may own the stage graph, intent routes,
   `review_mode` gating rules, artifact typing, or invariants. If it does,
   portability is gone and every bug becomes a host-specific bug.
3. **Do not delete `state.md`.** The file backend is what makes stelow work in a
   bare repo with no platform. Host backends must *degrade to it*, not replace
   it.

## What to do instead

### 1. Subtract before you abstract

- `stelow-product-*` (15 skills, standalone-invoked) should carry **zero**
  workflow vocabulary: no `stage:`, no hand-off block, no `state.md` path.
- The 17 workflow skills keep *behavior* and lose *storage verbs*: no
  `cat >> state.md`, no "append the hand-off block". They call the helper or the
  host, and the host records it.
- Remove `next-candidate` from every skill. `scripts/stelow next` (or the board)
  is the only thing allowed to compute it. A worker that proposes a transition
  and a worker that appends a transition are the same bug wearing two hats.
- Move the hand-off block out of 31 SKILL.md files into **one** reference file
  and point at it in one line each.

This alone removes the noise that motivated the question, without adding any
layer. Do this first, and measure.

### 2. Finish the contract that is already half-written

Add a `state` sibling of `execution` per stage, same shape, same enforcement:

```json
"state": {
  "position": "host",      // host | file
  "handoff":  "host",      // host | file
  "artifacts": "file"      // always file: derived, never a manifest
}
```

`host` means "the host mints it and shows it"; `file` means "stelow mints it in
`.stelow/state.md`". Everything not listed stays stelow-owned and a host is not
allowed to declare it — that is the anti-fork rule, and it should be a schema
constraint, not a sentence in a doc.

Then ship the checker, not just the schema: `stelow host-check <host.json>`
asserts a host's declaration is coherent (no host claims `review_mode`;
`artifacts` is never `host`; a host that claims `position: host` also declares a
`position_source`). Tests derive cases from the schema, exactly like
`breadboard-check` does today.

### 3. Let each host implement only the delegated half

- `bb-plugin-stelow` → `position: host` (cards), `handoff: host` (inbox),
  `artifacts: file`; it already does this in `bb-workflow-adapter.ts`.
- `stelow-host-multica` → `position: host` (issue status), `handoff: host`
  (issue comments), `artifacts: file`; see `agents/_adapter.md`.
- Any CLI-only host → `position: file`, `handoff: file`, and it works today.

## What a question looks like on the board

Multica has no "ask with N options" call. What it has, and what this host uses:

| primitive | what it is good for | what it cannot do |
|---|---|---|
| comment | the question's content, the evidence, the reasoning | cannot mark state, cannot be filtered |
| label | state that a person reads at a glance (`needs-human`) | no value, no history |
| select property | a fixed choice, filterable and machine-readable (`approve`, `send-back`) | the option set is workspace-level, not per card |
| saved view | grouping: one screen for every card carrying a label | read-only projection |
| wakeup | time: run again in 45m, with an instruction | cannot read the answer for you |
| autopilot | a scheduled check, and a script one costs no tokens | not a decision |

So a question is three things, not one: the **comment** carries what is being
asked, the **label plus wakeup** carry that it is waiting and that it will come
back, and a **select property** is worth adding only when the same choice repeats
often enough that typing it in prose is the waste.

The thing this host refuses to do is encode a question as a comment alone. A card
whose only signal is prose is a card that waits until somebody scrolls past it,
which is the failure the first smoke run produced twice.

## What each host actually has to declare

Five fields. Not an interface, not a lifecycle:

| field | meaning |
|---|---|
| `position` | where "which stage am I on" is minted |
| `position_source` | how to read it (a status name, a card field, a file path) |
| `handoff` | where a stage hands off |
| `gate` | who approves a gate column: `human`, `agent`, or `unsupported` |
| `artifacts` | always `file` |

`gate: unsupported` is legitimate and important: it tells stelow to fold the gate
into the previous stage instead of pretending the review happened.

## Named risk

Every host repo will want to add "just one more thing the host can own". The
schema constraint (`state` may only name those five fields; unknown keys are a
hard error) is the only thing that stops the drift. Ship the constraint with the
schema in the same commit, or the contract becomes advisory and then decorative.
