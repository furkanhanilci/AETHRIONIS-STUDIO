# Buzz — DIRECT_ADAPT record

The commissioning plan permits no Buzz material to move into AETHRIONIS until
seven things are true. They are recorded here before any adaptation, because
copying source under an unread licence is the one reuse decision that deleting
the code later does not undo.

## 1. Exact upstream commit pinned

`0720f5380ce8a6c050afac159f8462c06cd51ab5` — the same revision the DUM-E
upstream lock pins and the same one the relay runs. Verified against
`git ls-remote` as current `HEAD` on 2026-08-24.

## 2. Licence read at source

Apache License 2.0, read from `LICENSE` in the clone rather than from a badge.
The repository ships **no NOTICE file**, so no upstream attribution text is
inherited; `NOTICE` in this repository is written fresh and names the source.

Apache-2.0 §4 obligations: retain the licence and copyright notices, state
significant changes, and carry the NOTICE if one existed. The first two are met
by `NOTICE` and by this document; the third is moot.

## 3. File list named

**No Buzz source file is vendored.** What is adapted is the domain model and the
interaction design, not the code:

| Adapted from | What was taken | Where it lives here |
|---|---|---|
| `crates/buzz-core/src/kind.rs` | that channels, threads and mentions are distinct event kinds | `studio/shared/contracts/messages.py` |
| `crates/buzz-core/src/nip10.rs` | thread correlation by root/reply reference | `Message.thread_ref`, `Message.in_reply_to` |
| `crates/buzz-acp/src/lib.rs:3543` | that a mention is a recipient tag, not a permission | `resolve_alias`, and the test that asserts it grants nothing |
| `desktop/src/features/*` | the feature areas a collaboration desktop needs | `studio/features/*` |
| `desktop/src-tauri/src/lib.rs` | the shape of a desktop command surface | `studio/app.py` routes |
| `docs/nips/NIP-AP.md`, `NIP-PMA.md` | persona and managed-agent separation | `contracts/identity.py` |

The Rust is not translated. Python that resembled it would inherit its
assumptions without inheriting its tests.

## 4. Characterization written before adaptation

`tests/test_studio.py` and `tests/test_contracts.py` state what the adapted
model must do *here* before it does anything: a typed message refuses to be
untyped, a mention grants nothing, an embargoed verdict is invisible to a peer,
and no card can be built from prose. Those are AETHRIONIS properties, and Buzz has
none of them — which is the point of adapting rather than depending.

## 5. Authority boundary documented

Buzz supplies transport and interaction patterns. It supplies no authority.
`contracts/authority.py` names the seven transfers that must never happen, and
the one most relevant here: **a message saying PASS does not create a
VerificationRecord.** Buzz's own model has no equivalent, because Buzz has no
verification record to protect.

## 6. Alternative path stated

If this adaptation were withdrawn, Studio would fall back to the relay's HTTP
bridge with a plain text surface — which is what it used before, and which
works. The adaptation buys interaction quality, not capability, and nothing
depends on it that could not be done without it.

## 7. SPDX and NOTICE prepared

`NOTICE` names the source, the revision and the licence. Files that carry an
adapted idea say so in their module docstring rather than in a header comment,
because a header nobody reads is not attribution.

## What was deliberately not adapted

The assimilation matrix in the architecture package classifies these, and its
classification outranks a request for feature parity:

| Buzz area | Commands | Decision | Why |
|---|---|---|---|
| Huddles, voice, media calls | 29 | `DEFER` | "V2 unless a concrete scientific need appears" |
| Approval UI as authority | — | `DEFER` | scientific approval stays on the signed Decision Service path |
| Cards / mint / payments | 2 | out of scope | belongs to Buzz the product, not to a scientific workspace |
| BuilderLab community flows | — | out of scope | Buzz's own product concept |

Everything else in the desktop surface — channels, threads, reactions, search,
identity, personas, teams, agents, runtimes, ACP, workflows, git and project
collaboration, workspaces, notifications — is in scope and is being built with
an AETHRIONIS contract underneath it.
