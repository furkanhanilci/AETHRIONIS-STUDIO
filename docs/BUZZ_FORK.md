# The Buzz fork

AETHRIONIS Studio is a fork of [Buzz](https://github.com/block/buzz) at commit
`0720f5380ce8a6c050afac159f8462c06cd51ab5`, Apache-2.0.

## Why a fork and not a rewrite

The earlier attempt hand-wrote a collaboration surface against AETHRIONIS's
contracts. It worked in the narrow sense — messages posted, threads held, the
gate stayed authoritative — and it was still the wrong artefact. Buzz already
has channels, threads, reactions, search, notifications, deep links, presence,
agents, personas, ACP runtimes, workflows, projects, moderation and a relay
that speaks Nostr, all of it exercised by a test suite and a shipping product.
Reimplementing that is years of work whose only distinguishing feature would be
that it is younger and less tested.

So the collaboration client is Buzz's, and what AETHRIONIS adds is the part Buzz
was never trying to have.

## What was taken, verbatim

| Path | Upstream | Notes |
|---|---|---|
| `app/` | `desktop/` | Tauri 2 + React 19 client, 1535 TS/TSX files |
| `crates/` | `crates/` | relay, core, agent, acp, workflow, persona, sdk, voice, media |
| `migrations/`, `schema/` | same | the relay's data model |
| `patches/virtua@0.49.3.patch` | same | kept; the reason upstream gives still holds |
| `preview-features.json`, `scripts/model-capabilities.json` | same | build inputs |

The `isomorphic-git` patch was dropped: it applies to `web/`, which this fork
does not carry.

## What was changed, and why

1. **Product identity** — `productName`, bundle identifier `org.aethrionis.studio`,
   deep-link scheme `aethrionis` added alongside `buzz` so existing invite links
   still resolve.
2. **`externalBin` removed from the bundle.** Upstream ships sidecars
   (`buzz-acp`, `buzz-agent`, `git-credential-nostr`, …) built from the same
   workspace. Declaring them without shipping them fails the bundle. They come
   back with the agent runtime, which is the only thing that needs them.
3. **Nothing else yet.** Every further change is an addition on top rather than
   an edit inside, so the fork can still take upstream changes.

## What AETHRIONIS adds on top

Buzz's model is that a channel is where people talk. AETHRIONIS's constraint is
that *nothing said in a channel can constitute a review, a verification or an
acceptance* — those are records, produced by a deterministic gate, and a
message that looks like one is still only a message. The seven prohibited
authority transfers are the long form of that.

That constraint has no equivalent upstream and no reason to. It is layered as:

- typed messages (ten classes) carried in event tags, not inferred from text;
- DUM-E's canonical state read directly from its own store, never from the
  relay, and rendered as cards that are visually distinct from messages;
- the gate verdict shown as a record with its inputs, never as a status.

## Out of scope, deliberately

Huddles, voice and media capture; cards and payments; BuilderLab. These are
carried in the fork because removing them is a large edit for no benefit, and
they are simply not surfaced. The assimilation matrix outranks feature parity.

## Building

The Rust shell needs ALSA, PulseAudio and Opus development headers, because
upstream's voice module is compiled even when unused. Either install them:

    sudo apt-get install -y libasound2-dev libpulse-dev libopus-dev

or use the checked-in local sysroot, which needs no root:

    PKG_CONFIG_PATH=.sysroot/usr/lib/x86_64-linux-gnu/pkgconfig cargo build --release
