"""The AETHRIONIS Studio shell.

Four columns, as the design freeze fixes them: a small primary rail that does
not change, a context rail that does, the work itself, and an inspector that can
close without stopping anything.

The rule that shapes most of what follows is the thirteenth frozen principle:
*no UI text can turn a chat message into ACCEPTED / VERIFIED / MERGE_ELIGIBLE
authority*. So every card here renders a record the gateway read from DUM-E, and
a message that merely says "PASS" produces a flag, not a card.
"""
from __future__ import annotations

import html
from pathlib import Path

ASSETS = "/assets"

# Primary rail. Small on purpose — Literature, Evidence, Claims, Experiments and
# the rest belong to a workspace, not to global navigation.
PRIMARY = [
    ("home", "Home", "⌂"),
    ("projects", "Projects", "▦"),
    ("dume", "DUM-E", "◈"),
    ("agents", "Agents", "◉"),
    ("models", "Models", "▤"),
    ("activity", "Activity", "≋"),
    (None, None, None),
    ("search", "Search", "⌕"),
    ("settings", "Settings", "⚙"),
]

TONE = {"success": "var(--success)", "warning": "var(--warning)",
        "failure": "var(--failure)", "info": "var(--info)",
        "review": "var(--review)", "neutral": "var(--text-muted)",
        "dume": "var(--dume-cyan)", "brand": "var(--aethrionis-red)"}


def e(text) -> str:
    return html.escape(str(text if text is not None else ""))


def page(*, section: str, context: str, main: str, inspector: str = "",
         title: str = "AETHRIONIS Studio") -> str:
    shell_class = "shell" if inspector else "shell no-inspector"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<link rel="icon" href="{ASSETS}/logos/aethrion_appmark_64.png">
<link rel="stylesheet" href="/static/tokens.css">
<link rel="stylesheet" href="/static/studio.css">
</head><body><div class="{shell_class}">
{primary_rail(section)}
{context}
{main}
{inspector}
</div></body></html>"""


def primary_rail(section: str) -> str:
    rows = []
    for key, label, glyph in PRIMARY:
        if key is None:
            rows.append('<div class="sep"></div>')
            continue
        classes = "active" if key == section else ""
        if key == "dume" and key == section:
            classes += " dume"
        rows.append(
            f'<a href="/{key if key != "home" else ""}" class="{classes}" '
            f'aria-current="{"page" if key == section else "false"}">'
            f'<span class="glyph" aria-hidden="true">{glyph}</span>{e(label)}</a>')
    return f"""<nav class="rail-primary" aria-label="Primary">
  <div class="brand">
    <img src="{ASSETS}/logos/aethrion_appmark_64.png" alt="">
    <span class="name">AETHRIONIS <em>Studio</em></span>
  </div>
  <div class="nav">{''.join(rows)}</div>
  <div class="spacer"></div>
  <div class="me"><span class="dot"></span>
    <span class="who">Furkan Hanilçi<small>Online</small></span></div>
</nav>"""


def context_rail(groups: list[tuple[str, list[dict]]], org: str = "Default Research Org") -> str:
    """`groups` is [(heading, [{href,label,active,hash,dume}])]."""
    blocks = []
    for heading, items in groups:
        rows = []
        for item in items:
            classes = "active" if item.get("active") else ""
            if item.get("dume"):
                classes += " dume"
            hash_mark = '<span class="hash">#</span>' if item.get("hash") else ""
            glyph = f'<span class="hash" aria-hidden="true">{e(item["glyph"])}</span>' \
                if item.get("glyph") else ""
            badge = (f'<span class="badge-unread">{int(item["badge"])}</span>'
                     if item.get("badge") else "")
            rows.append(f'<a href="{e(item["href"])}" class="{classes}">'
                        f'{hash_mark}{glyph}{e(item["label"])}{badge}</a>')
        if not rows:
            continue
        blocks.append(f'<div class="group"><h3>{e(heading)}</h3>{"".join(rows)}</div>')
    return f"""<nav class="rail-context" aria-label="Context">
  <div class="org">▦ {e(org)}</div>
  {''.join(blocks)}
</nav>"""


def channel_head(name: str, subtitle: str = "", members: str = "",
                 dume: bool = False) -> str:
    mark = (f'<img src="{ASSETS}/logos/dume_workspace_mark_64.png" alt="" '
            'style="width:19px;height:19px;vertical-align:-3px">') if dume else ""
    count = f'<span class="count">{e(members)}</span>' if members else ""
    return (f'<div class="channel-head"><h1><span class="hash">#</span> '
            f'{e(name)} {mark}</h1>{count}'
            + (f'<div class="sub">{e(subtitle)}</div>' if subtitle else "")
            + "</div>")


def message(*, who: str, when: str, text: str, avatar: str | None = None,
            initials: str = "", message_type: str | None = None,
            card: str = "", flag: str = "", message_id: str | None = None,
            reactions: dict | None = None, replies: int = 0,
            channel: str | None = None, pinned: bool = False,
            edited: bool = False, unanswered: bool = False,
            recipients: list | None = None, refs: list | None = None) -> str:
    face = (f'<img src="{avatar}" alt="">' if avatar else e(initials or who[:2].upper()))
    type_chip = ""
    if message_type and message_type != "STATUS":
        colour = {"CHALLENGE": "var(--failure)", "EVIDENCE": "var(--success)",
                  "PROPOSAL": "var(--info)", "CORRECTION": "var(--review)",
                  "BLOCKER": "var(--failure)", "REQUEST": "var(--warning)",
                  "DISAGREEMENT": "var(--aethrionis-red)",
                  "CONSENSUS_CANDIDATE": "var(--success)",
                  "ABSTAIN": "var(--text-muted)"}.get(message_type, "var(--text-muted)")
        type_chip = f'<span class="type" style="--c:{colour}">{e(message_type)}</span>'
    flag_html = f'<div class="flag">{e(flag)}</div>' if flag else ""

    meta_bits = []
    if pinned:
        meta_bits.append('<span class="vis">pinned</span>')
    if edited:
        meta_bits.append('<span class="vis">edited</span>')
    if unanswered:
        meta_bits.append('<span class="vis open">unanswered</span>')
    for actor in (recipients or [])[:3]:
        meta_bits.append(f'<span class="vis">to {e(actor.split(":")[-1])}</span>')

    refs_html = ('<div class="refs">re: ' + " · ".join(e(r) for r in refs) + "</div>"
                 if refs else "")

    # Reactions and the reply affordance sit under the message rather than in a
    # hover menu: a control that appears only on hover is a control a keyboard
    # user cannot find.
    actions = ""
    if message_id and channel:
        chips = "".join(
            f'<form method="post" action="/react" class="inline">'
            f'<input type="hidden" name="message" value="{e(message_id)}">'
            f'<input type="hidden" name="channel" value="{e(channel)}">'
            f'<input type="hidden" name="glyph" value="{e(glyph)}">'
            f'<button class="reaction" type="submit">{e(glyph)} {count}</button>'
            "</form>" for glyph, count in (reactions or {}).items())
        for glyph in ("👍", "✓", "?"):
            if glyph not in (reactions or {}):
                chips += (f'<form method="post" action="/react" class="inline">'
                          f'<input type="hidden" name="message" value="{e(message_id)}">'
                          f'<input type="hidden" name="channel" value="{e(channel)}">'
                          f'<input type="hidden" name="glyph" value="{e(glyph)}">'
                          f'<button class="reaction quiet" type="submit" '
                          f'aria-label="react {e(glyph)}">{e(glyph)}</button></form>')
        thread_label = (f"{replies} repl{'y' if replies == 1 else 'ies'}"
                        if replies else "Reply in thread")
        chips += (f'<a class="reaction quiet" '
                  f'href="?channel={e(channel)}&thread={e(message_id)}">'
                  f'{e(thread_label)}</a>')
        actions = f'<div class="actions">{chips}</div>'

    return f"""<div class="msg">
  <div class="avatar">{face}</div>
  <div>
    <div class="head"><span class="who">{e(who)}</span>
      <time>{e(when)}</time>{type_chip}{''.join(meta_bits)}</div>
    <div class="text">{_linkify(text)}</div>
    {refs_html}{card}{flag_html}{actions}
  </div>
</div>"""


def _linkify(text: str) -> str:
    out = []
    for token in e(text).split(" "):
        if token.startswith("@") and len(token) > 1:
            out.append(f'<span class="mention">{token}</span>')
        else:
            out.append(token)
    return " ".join(out)


def inspector(title: str, blocks: list[str], *, dume: bool = False) -> str:
    mark = (f'<img src="{ASSETS}/logos/dume_workspace_mark_64.png" alt="">'
            if dume else f'<img src="{ASSETS}/logos/aethrion_appmark_64.png" alt="">')
    return (f'<aside class="inspector" aria-label="Inspector">'
            f'<div class="head">{mark}<b>{e(title)}</b>'
            f'<span class="close" aria-hidden="true">✕</span></div>'
            + "".join(blocks) + "</aside>")


def block(heading: str, body: str) -> str:
    return f'<div class="block"><h4>{e(heading)}</h4>{body}</div>'


def kv(pairs: list[tuple[str, str, str]]) -> str:
    """pairs of (key, value, css class)."""
    rows = "".join(f'<dt>{e(k)}</dt><dd class="{cls}">{e(v)}</dd>'
                   for k, v, cls in pairs)
    return f'<dl class="kv">{rows}</dl>'


def checks(items: list[tuple[str, str]]) -> str:
    glyph = {"ok": ('<span class="g">✔</span>', "g"),
             "warn": ('<span class="w">▲</span>', "w"),
             "fail": ('<span class="f">✕</span>', "f"),
             "info": ('<span style="color:var(--text-muted)">◦</span>', "")}
    return "".join(f'<div class="check">{glyph.get(state, glyph["info"])[0]}'
                   f'<span>{e(label)}</span></div>' for label, state in items)


def linked(items: list[tuple[str, str, int]]) -> str:
    return "".join(
        f'<div class="linked"><span style="color:{TONE.get(tone,"var(--text-muted)")}"'
        f' aria-hidden="true">◆</span><span>{e(label)}</span>'
        f'<span class="n">{n}</span></div>' for label, tone, n in items)


def events(items: list[dict], limit: int = 6) -> str:
    rows = []
    for item in items[:limit]:
        colour = TONE.get(item.get("tone", "neutral"), "var(--text-muted)")
        when = (item.get("at") or "")[11:16]
        rows.append(f'<div class="evt"><span class="d" style="--c:{colour}"></span>'
                    f'<span>{e(item["title"])}'
                    + (f'<span class="sub">{e(item["detail"][:70])}</span>'
                       if item.get("detail") else "")
                    + f'</span><time>{e(when)}</time></div>')
    return "".join(rows) or '<div class="check">nothing recorded yet</div>'
