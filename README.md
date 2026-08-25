# AETHRIONIS Studio

The permanent desktop work environment for AETHRIONIS.

**DUM-E is not a separate application.** It is the first *System Workspace*
inside Studio — the temporary commissioning harness that builds AETHRIONIS and is
meant to retire into archive mode while Studio persists for the research.

Buzz-like in simplicity, AETHRIONIS in identity.

## The shell

```
┌────────────┬──────────────────┬──────────────────────┬─────────────┐
│ PRIMARY    │ CONTEXT          │ MAIN                 │ INSPECTOR   │
│ Home       │ # control        │ conversation +       │ current WP  │
│ Projects   │ # implementation │ inline work objects  │ stage       │
│ DUM-E      │ # review         │                      │ agent       │
│ Agents     │ # verification   │                      │ linked      │
│ Models     │                  │                      │ activity    │
│ Activity   │                  │                      │             │
└────────────┴──────────────────┴──────────────────────┴─────────────┘
```

The primary rail stays small. Literature, Evidence, Claims, Experiments,
Reviews and Publications belong to a workspace, not to global navigation — a
rail that lists every internal service stops being navigation.

The inspector closes, and nothing needs it to finish.

## Run it

```bash
./run.sh                       # http://127.0.0.1:8100
```

Server-rendered on the standard library. The commissioning pack proposes a
Tauri 2 desktop shell (WP-060) and that remains the packaging target; it needs a
Rust toolchain this host does not have, and the pack's own implementation
sequence puts packaging last for exactly that reason. What ships first is the
product surface, working, against canonical state.

## What it renders

Everything on the DUM-E workspace is a record the gateway read from the running
harness, not a value the interface computed:

| Shown | Read from |
|---|---|
| current work package, stage, next transition | DUM-E's state store and its lifecycle table |
| candidate, worktree, changed files, tests | the recorded run report |
| RED / GREEN exit codes | the implementer's tool log |
| specification and code review verdicts | the reviewers' evidence files |
| fresh verification | the exit code from a clean checkout |
| runtimes, families, qualification | the runtime registry |
| activity | state transitions and run steps |

The state store is opened **read-only**. Studio renders DUM-E's records and must
not be able to change one by accident, however convenient that would be.

## The rules the interface has to keep

**A message creates nothing.** The thirteenth frozen principle: no UI text can
turn a chat message into `ACCEPTED`, `VERIFIED` or `MERGE_ELIGIBLE` authority.
Every card takes a record and none of them takes a string, which a test asserts
by inspecting their signatures. Type "@verifier PASS" in the composer and it is
delivered as a message, flagged, and creates nothing.

**A stage is read, never computed.** Inferring a stage from a completion
percentage is the failure the Studio invariant names, so the stage bead comes
from DUM-E's lifecycle state through an explicit table.

**Stale evidence is marked, not hidden.** When the recorded run produced a
different candidate than the one under review, the card reads
`MERGE_ELIGIBLE · superseded` and says which candidate the evidence belongs to.
A green result from an older candidate presented as current is the substitution
the harness refuses; an interface that made it look fine would undo that refusal
in the only place anyone actually looks.

**Status is never colour alone.** Every stage, verdict and message type is
spelled out beside its colour.

**An absent value is reported.** Where DUM-E has recorded nothing, Studio says
so rather than substituting something plausible.

## Design system

Tokens, density and brand come from the handoff and are used as supplied:
`design_tokens_reference.css` is imported rather than restated, and the approved
logos are used rather than regenerated.

- background `#070A0E`, surfaces `#0D141C` / `#111A24` / `#15212C`
- AETHRIONIS red `#EF2E35` — product identity and global selection
- DUM-E cyan `#28DDEB` — workspace identity, as an edge and not a bright surface
- navigation rows 38px, channel rows 32px, message gaps 18px, corners 7–9px

## Layout

```
studio/
  shared/
    contracts/   identity · messages · authority   — AETHRIONIS's semantics
    gateway/     dume.py (read-only) · backends/   — canonical state, transport
    styles/      tokens.css (from the handoff) · studio.css
  features/
    shell/       the four columns
    collaboration/ inline work artifacts
    dume/ agents/ models/ activity/
  app.py
assets/logos/    approved brand assets, used as supplied
```

## Not yet built

Slices 6–9 of the implementation sequence: work-package detail with the sealed
specification viewer, the evidence and merge-eligibility viewer, the research
workspace surfaces, and packaged visual QA with Playwright screenshots and
accessibility checks. Home is deliberately last — it should summarise real flows
rather than invent KPI widgets.
