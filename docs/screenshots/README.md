# Screenshots

There are **two** surfaces here and they look nothing alike. Confusing them is
easy and was the reason this file exists: for a while the only pictures in the
repository were of the gateway, so a reader had no way to know what the product
actually looks like.

## `desktop/` — the application

The product: a Tauri 2 + React desktop workspace, forked from Buzz. This is what
`./aethrionis-studio` opens and what a person uses.

| File | Shows |
|---|---|
| `inbox.png` | The Inbox. DUM-E mentions the operator here when a step needs them |
| `commissioning.png` | A work package's candidate, reviews, verification and gate verdict |
| `agents.png` | The starter agents and agent teams |
| `dume-control.png` | `#DUM-E · control`, where the harness reports its steps |
| `dume-review.png` | `#DUM-E · review`, where the two reviewers answer |

Captured by hand from a running build, window-only, at 1850×1016. There is no
script for these: driving a desktop application reliably enough to photograph it
is a bigger piece of machinery than the pictures are worth, and a stale
screenshot is worse than an old one only if nobody can tell. Retake them when
the interface changes.

## The rest — the gateway

The files directly in this directory are the **gateway** at `127.0.0.1:8100`,
served by `studio/app.py`. It is a separate, much smaller web surface: DUM-E's
state, the membership flow, and the command bar. It is not the application.

Regenerate with `python3 scripts_visual_qa.py` while the gateway is running.
That script also holds the accessibility checks a machine can make — chiefly
that status is never carried by colour alone.

## Why both are kept

The gateway is what answers when the desktop is not running, and it is the
surface a phone reaches. Deleting its pictures would leave that half of the
system undocumented. Labelling them was the missing part, not choosing between
them.
