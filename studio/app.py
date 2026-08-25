"""AETHRIONIS Studio — the application.

Server-rendered, standard library only. The commissioning pack proposes a Tauri
2 desktop shell (WP-060) and that remains the packaging target; it needs a Rust
toolchain this host does not have, and the pack's own implementation sequence
puts packaging last for exactly this reason. What ships first is the product
surface, working, against canonical state.

Every screen here reads. Nothing in Studio computes acceptance, a stage or a
verdict — it renders what DUM-E recorded, and where DUM-E recorded nothing it
says so rather than inventing a plausible value.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .features.collaboration import cards
from .features.dume import detail
from .features.shell import render as R
from .features.shell.render import block, checks, e, events, kv, linked
from .shared.gateway.dume import DumeGateway
from .shared.gateway.seed import OPERATOR, ensure
from .shared.gateway.workspace import Message

ROOT = Path(__file__).resolve().parent
STORE = Path.home() / ".aethrionis" / "studio.db"
# The harness this gateway reads. Its collaboration package carries the
# membership flow; importing it here rather than duplicating it keeps one
# implementation of who is admitted.
DUME_REPO = Path("/home/otonom/Desktop/FH/DUM-E")

# Put the harness on the path once, here, rather than inside whichever handler
# happens to run first. It was inside one of them, and `/api/command` imported
# from `dume` before the handler that did the inserting had ever been called —
# so the first request crashed and the second worked. An order-dependent import
# is a bug that hides behind whatever you happen to try first.
if str(DUME_REPO) not in sys.path:
    sys.path.insert(0, str(DUME_REPO))
ASSETS = ROOT.parent / "assets"
STYLES = ROOT / "shared" / "styles"

CHANNELS = [
    ("general", "general", False),
    ("dume", "dume", True),
    ("mobile-llm", "mobile-llm", False),
    ("verification", "verification", False),
]

WORKSPACES = ["LLM Safety & Alignment", "Runtime Engineering",
              "Evidence & Verification", "Agent Platform", "Research Ops"]


class Studio:
    def __init__(self, gateway: DumeGateway | None = None,
                 store: Path | None = None):
        self.dume = gateway or DumeGateway()
        path = Path(store or STORE)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.workspace = ensure(path)
        self.me = OPERATOR

    # ---- context rail ----------------------------------------------------

    def _collab_context(self, active: str) -> str:
        return R.context_rail([
            ("Channels", [{"href": f"/?channel={c}", "label": label,
                           "hash": True, "active": c == active, "dume": is_dume}
                          for c, label, is_dume in CHANNELS]),
            ("Direct", [
                {"href": "/?channel=mobile-llm", "label": "Mobile LLM Quantization",
                 "glyph": "◉"},
                {"href": "/dume", "label": "DUM-E Commissioning", "glyph": "◈",
                 "dume": True}]),
            ("Workspaces", [{"href": "#", "label": w, "glyph": "▢"}
                            for w in WORKSPACES]),
        ])

    def _dume_context(self, active: str) -> str:
        """Channels come from the store, each carrying its own unread count.

        Per-channel and per-actor, because that is the only form in which the
        count means anything: one global badge says something happened
        somewhere, which is the same as saying nothing."""
        items = []
        for row in self.workspace.channels("space:dume"):
            name = row["name"]
            unread = self.workspace.unread(row["channel_id"], self.me)
            items.append({"href": f"/dume?channel={name}", "label": name,
                          "hash": True, "active": name == active, "dume": True,
                          "badge": unread or None})
        open_items = self.workspace.open_items("space:dume")
        needs = ([{"href": f"/dume?channel={active}&filter=open",
                   "label": f"{len(open_items)} unanswered", "glyph": "◈",
                   "dume": True}] if open_items else [])
        return R.context_rail([
            ("Channels", items),
            ("Needs an answer", needs),
            ("Spaces", [{"href": "/space/" + sp["space_id"].split(":")[1],
                         "label": sp["name"], "glyph": "▢"}
                        for sp in self.workspace.spaces()
                        if sp["space_id"] != "space:dume"]),
        ])

    def _dume_inspector(self) -> str:
        package = self.dume.current()
        if package is None:
            return R.inspector("DUM-E", [block(
                "Current work package",
                '<div class="check">DUM-E has recorded no active package.</div>')],
                dume=True)

        cohort = self.dume.cohort()
        agent = next((b["runtime_id"] for role, b in cohort.items()
                      if role.startswith("implementer")), "—")
        blocks = [
            block("Current work package", kv([
                ("WP", f"{package.wp_id}  {package.title[:34]}", ""),
                ("Stage", package.state.replace("_", " ").title(), ""),
                ("Agent", agent, "cyan"),
                ("Candidate", (package.candidate or "—")[:12], "mono"),
                ("Next", package.next_stage(), ""),
            ])),
        ]

        runtimes = self.dume.runtimes()
        usable = [r for r in runtimes if r["status"] == "AVAILABLE"]
        qualified = [r for r in runtimes if r["qualified"]]
        report = self.dume.last_run()
        blocks.append(block("Status", checks([
            (f"{len(usable)} runtime(s) available", "ok" if usable else "fail"),
            (f"{len(qualified)} qualified for a role", "ok" if qualified else "warn"),
            (f"last run: {report.get('verdict')}" if report else "no run recorded",
             "ok" if report and report.get("verdict") == "MERGE_ELIGIBLE" else "warn"),
            (f"{len(package.waiting_on)} unmet dependency"
             if package.waiting_on else "dependencies satisfied",
             "warn" if package.waiting_on else "ok"),
        ])))

        reviews = self.dume.review_records(package.wp_id)
        verification = self.dume.verification(package.wp_id)
        blocks.append(block("Linked items", linked([
            ("Review", "review", len(reviews)),
            ("Verification", "success", 1 if verification else 0),
            ("Candidate", "info", 1 if package.candidate else 0),
            ("Evidence", "neutral",
             len(list((self.dume.evidence / "live" / package.wp_id).glob("*")))
             if (self.dume.evidence / "live" / package.wp_id).is_dir() else 0),
        ])))
        blocks.append(block("Recent activity", events(self.dume.activity(), 5)))
        return R.inspector("DUM-E", blocks, dume=True)

    # ---- screens ---------------------------------------------------------

    def dume_channel(self, channel: str = "control", thread: str = "",
                     query: str = "", mode: str = "") -> str:
        """The #dume conversation: real messages from the store, and the real
        DUM-E records attached where they belong.

        The two are deliberately not the same kind of thing. A message is
        something somebody said. A card is something DUM-E recorded. They share
        a stream because that is how the work is actually followed, and they are
        rendered differently because confusing them is the failure this whole
        design exists to prevent."""
        channel_id = f"ch:dume:{channel}"
        package = self.dume.current()
        stream = []
        head_extra = ""

        if query:
            rows = self.workspace.search(query, space_id="space:dume")
            head_extra = (f'<div class="thread-head">{len(rows)} result'
                          f'{"" if len(rows) == 1 else "s"} for "{e(query)}" '
                          f'<a href="/dume?channel={e(channel)}">Back to #{e(channel)}</a></div>')
        elif thread:
            root = self.workspace.message(thread)
            rows = self.workspace.read(channel_id, thread_root=thread)
            head_extra = ('<div class="thread-head">Thread'
                          + (f' on {e(root["message_type"])}' if root else "")
                          + f' <a href="/dume?channel={e(channel)}">'
                            f'Back to #{e(channel)}</a></div>')
        else:
            rows = self.workspace.read(channel_id, limit=120)
            if mode == "open":
                open_ids = {m["message_id"]
                            for m in self.workspace.open_items("space:dume")}
                rows = [r for r in rows if r["message_id"] in open_ids]
                head_extra = ('<div class="thread-head">Messages nobody has '
                              f'answered <a href="/dume?channel={e(channel)}">'
                              f'Back to #{e(channel)}</a></div>')
            stream.extend(self._dume_records(package, channel))

        for row in rows:
            actor = self.workspace.actor(row["sender_actor_id"]) or {}
            name = actor.get("display_name") or row["sender_actor_id"].split(":")[-1]
            stream.append(R.message(
                who=name, when=row["created_at"][11:16],
                initials="".join(w[0] for w in name.split()[:2]).upper(),
                message_type=row["message_type"], text=row["body"],
                message_id=row["message_id"], channel=channel,
                reactions=row.get("reactions"), replies=row.get("reply_count", 0),
                pinned=bool(row.get("pinned")), edited=bool(row.get("edited_at")),
                unanswered=(row["message_type"] in ("CHALLENGE", "REQUEST",
                                                    "BLOCKER", "DISAGREEMENT")
                            and not row.get("reply_count")),
                recipients=row.get("recipients") or [],
                refs=row.get("artifact_refs") or []))

        if not stream:
            stream.append('<div class="empty">'
                          '<img src="/assets/logos/dume_master_logo_transparent.png" alt="">'
                          'Nothing here yet.</div>')

        pin_strip = ""
        pinned = self.workspace.pinned(channel_id)
        if pinned and not thread and not query:
            pin_strip = ('<div class="thread-head">Pinned: '
                         + " · ".join(e(m["body"][:60]) for m in pinned[:3])
                         + "</div>")

        search = ('<div class="searchbar"><form method="get" action="/dume">'
                  f'<input type="hidden" name="channel" value="{e(channel)}">'
                  f'<input name="q" value="{e(query)}" placeholder="Search this space…"'
                  ' aria-label="Search messages">'
                  '<button class="reaction" type="submit">Search</button>'
                  '</form></div>')

        main = ('<main>'
                + R.channel_head(channel, self._channel_purpose(channel_id), "",
                                 dume=True)
                + search + pin_strip + head_extra
                + f'<div class="stream">{"".join(stream)}</div>'
                + self._composer(channel, thread) + '</main>')
        self.workspace.mark_read(channel_id, self.me)
        return R.page(section="dume", context=self._dume_context(channel),
                      main=main, inspector=self._dume_inspector(),
                      title=f"#{channel} · DUM-E · AETHRIONIS Studio")

    def _channel_purpose(self, channel_id: str) -> str:
        for row in self.workspace.channels("space:dume"):
            if row["channel_id"] == channel_id:
                return row["purpose"] or ""
        return ""

    def _dume_records(self, package, channel: str) -> list:
        """The DUM-E records that belong in this channel, as cards."""
        if package is None:
            return []
        out = [R.message(
            who="Orchestrator", when="—",
            avatar="/assets/logos/aethrion_appmark_64.png",
            text=f"{package.wp_id} is at {package.state.replace('_',' ').lower()}. "
                 f"The next permitted transition is {package.next_stage()}.",
            card=cards.wp_card(
                wp_id=package.wp_id, title=package.title, bead=package.bead(),
                stage_label=package.state.replace("_", " ").title(),
                next_stage=package.next_stage(), tone=package.tone()))]

        candidate = self.dume.candidate_card(package.wp_id, package.candidate)
        if candidate and channel in ("control", "implementation"):
            out.append(R.message(
                who="Implementer", when="—", initials="QW",
                text="Candidate produced under test-first discipline. "
                     "The red and green exit codes are recorded.",
                card=cards.candidate_card(candidate)))

        if channel in ("control", "review"):
            for record in self.dume.review_records(package.wp_id):
                out.append(R.message(
                    who=f"{record['kind']} reviewer", when="—", initials="MS",
                    text=record["reason"], card=cards.review_card(record)))

        if channel in ("control", "verification"):
            verification = self.dume.verification(package.wp_id)
            if verification:
                out.append(R.message(
                    who="Verifier", when="—", initials="MS",
                    text="Suite re-run from a fresh checkout in a directory "
                         "the implementer never touched.",
                    card=cards.verification_card(verification)))
        return out

    def _composer(self, channel: str, thread: str = "") -> str:
        draft = self.workspace.draft(f"ch:dume:{channel}", self.me) or ""
        where = "this thread" if thread else f"#{e(channel)}"
        types = "".join(f"<option>{t}</option>" for t in (
            "STATUS", "PROPOSAL", "CHALLENGE", "EVIDENCE", "REQUEST",
            "CORRECTION", "DISAGREEMENT", "CONSENSUS_CANDIDATE", "ABSTAIN",
            "BLOCKER"))
        return ('<div class="composer"><form method="post" action="/say">'
                f'<input type="hidden" name="channel" value="{e(channel)}">'
                f'<input type="hidden" name="thread" value="{e(thread)}">'
                f'<select name="type" aria-label="Message type">{types}</select>'
                f'<input name="body" value="{e(draft)}" '
                f'placeholder="Message {where}…" autocomplete="off">'
                '<button type="submit">Send</button></form>'
                '<div class="hint">A message is a message. Nothing said here '
                'creates a review, a verification or an acceptance — those are '
                'records, and they come from DUM-E. Address someone with @role; '
                'an unresolved mention is recorded as unresolved rather than '
                'dropped.</div></div>')

    def work_packages(self) -> str:
        rows = []
        for package in self.dume.work_packages():
            rows.append(cards.wp_card(
                wp_id=package.wp_id, title=package.title, bead=package.bead(),
                stage_label=package.state.replace("_", " ").title(),
                next_stage=package.next_stage(), tone=package.tone())
                .replace('<div class="card">',
                         f'<a href="/dume/wp?id={package.wp_id}" class="card" '
                         'style="display:block">', 1)
                .replace("</div>\n</div>", "</div>\n</a>", 1))
        counts = self.dume.counts()
        summary = " · ".join(f"{n} {state.replace('_',' ').lower()}"
                             for state, n in sorted(counts.items(),
                                                    key=lambda kv: -kv[1]))
        body = "".join(rows) or '<div class="empty">No package has started.</div>'
        main = (f'<main>{R.channel_head("work packages", summary)}'
                f'<div class="stream">{body}</div></main>')
        return R.page(section="dume", context=self._dume_context("wp"), main=main,
                      inspector=self._dume_inspector(),
                      title="Work packages · DUM-E · AETHRIONIS Studio")

    def work_package(self, wp_id: str, tab: str = "specification") -> str:
        package = next((p for p in self.dume.work_packages(active_only=False)
                        if p.wp_id == wp_id), None)
        if package is None:
            main = ('<main><div class="stream"><div class="empty">'
                    f'{e(wp_id)} is not in the commissioning plan.</div></div></main>')
            return R.page(section="dume", context=self._dume_context("wp"), main=main)

        tabs = [("specification", "Sealed specification"), ("evidence", "Evidence"),
                ("gate", "Gate"), ("history", "History")]
        tab_html = '<div class="tabs">' + "".join(
            f'<a href="/dume/wp?id={e(wp_id)}&tab={key}" '
            f'class="{"active" if key == tab else ""}">{e(label)}</a>'
            for key, label in tabs) + "</div>"

        if tab == "evidence":
            body = detail.evidence_list(self.dume.evidence_files(wp_id))
        elif tab == "gate":
            body = detail.gate_record(self.dume.gate(wp_id))
        elif tab == "history":
            body = ('<div class="card">'
                    + detail.history_list(self.dume.history(wp_id))
                    + "</div><div class=\"card\">"
                    + detail.findings_list(self.dume.findings(wp_id)) + "</div>")
        else:
            body = detail.sealed_specification(self.dume.sealed_sections(wp_id))

        head = R.channel_head(
            package.wp_id,
            f"{package.title} · {package.state.replace('_',' ').lower()}"
            + (f" · waiting on {', '.join(package.waiting_on)}"
               if package.waiting_on else ""),
            dume=True)
        main = f'<main>{head}{tab_html}<div class="stream">{body}</div></main>'
        return R.page(section="dume", context=self._dume_context("wp"), main=main,
                      inspector=self._dume_inspector(),
                      title=f"{wp_id} · DUM-E · AETHRIONIS Studio")

    def home(self) -> str:
        """Built last, on purpose.

        The design system says Home should summarise actual flows rather than
        invent KPI widgets, so every tile below is a real object: the package
        that is furthest through the pipeline, the runtimes that are actually
        qualified, the last run's verdict, and what is waiting. Nothing here is
        a metric computed for the sake of having one.
        """
        package = self.dume.current()
        report = self.dume.last_run()
        runtimes = self.dume.runtimes()
        qualified = [r for r in runtimes if r["qualified"]]
        counts = self.dume.counts()
        blocked = [p for p in self.dume.work_packages() if p.waiting_on]

        tiles = []
        if package:
            tiles.append(f"""<a href="/dume" class="card" style="display:block">
              <div class="card-head"><span style="color:var(--dume-cyan)">◈</span>
                <span class="id">{e(package.wp_id)}</span>
                <span class="title">{e(package.title[:46])}</span></div>
              <div class="grid4">
                <div><div class="k">Stage</div><div class="v">{e(package.state.replace('_',' ').title())}</div></div>
                <div><div class="k">Next</div><div class="v">{e(package.next_stage())}</div></div>
                <div><div class="k">Candidate</div><div class="v mono">{e((package.candidate or '—')[:12])}</div></div>
              </div></a>""")
        if report:
            verdict = report.get("verdict", "—")
            colour = ("var(--success)" if verdict == "MERGE_ELIGIBLE"
                      else "var(--failure)")
            tiles.append(f"""<div class="card">
              <div class="card-head"><span>⚖</span><span class="id">Last run</span>
                <span class="right"><span class="pill" style="--c:{colour}">
                  {e(verdict)}</span></span></div>
              <div class="grid4">
                <div><div class="k">Package</div><div class="v">{e(report.get('wp_id','—'))}</div></div>
                <div><div class="k">Elapsed</div><div class="v">{e(report.get('elapsed_seconds','—'))} s</div></div>
                <div><div class="k">Stages</div><div class="v">{len(report.get('steps',[]))}</div></div>
              </div></div>""")
        tiles.append(f"""<a href="/models" class="card" style="display:block">
          <div class="card-head"><span>▤</span><span class="id">Runtimes</span></div>
          <div class="grid4">
            <div><div class="k">Available</div><div class="v">{sum(1 for r in runtimes if r['status']=='AVAILABLE')}</div></div>
            <div><div class="k">Qualified</div><div class="v">{len(qualified)}</div></div>
            <div><div class="k">Families</div><div class="v">{len({r['family'] for r in qualified if r['family']})}</div></div>
          </div>
          <div class="foot"><span>Availability is not eligibility. A runtime that
            has not been measured for a role cannot hold it.</span></div></a>""")
        if blocked:
            rows = "".join(
                f'<div class="linked"><span style="color:var(--warning)">▲</span>'
                f'<span>{e(p.wp_id)}</span>'
                f'<span class="n">{e(", ".join(p.waiting_on))}</span></div>'
                for p in blocked[:5])
            tiles.append(f'<div class="card"><div class="card-head">'
                         f'<span>▲</span><span class="id">Waiting</span></div>'
                         f'{rows}</div>')

        counts_line = " · ".join(f"{n} {state.replace('_',' ').lower()}"
                                 for state, n in sorted(counts.items(),
                                                        key=lambda kv: -kv[1]))
        main = (f'<main>{R.channel_head("home", counts_line)}'
                f'<div class="stream">{"".join(tiles)}'
                f'<h2 style="margin:22px 0 8px">Recent</h2>'
                f'<div class="card">{events(self.dume.activity(), 8)}</div>'
                f'</div></main>')
        return R.page(section="home", context=self._collab_context("dume"),
                      main=main, title="Home · AETHRIONIS Studio")

    def research(self) -> str:
        """The research workspace shell, on the same primitives.

        Deliberately empty of invented content: the surfaces exist and say what
        each will hold, and none of them shows a number nothing produced yet.
        """
        surfaces = [
            ("Literature", "Sources projected from Zotero and Obsidian. The "
                           "Source Registry owns bibliographic identity; this "
                           "renders it."),
            ("Experiments", "Runs, environments and metrics, each bound to the "
                            "revision that produced it."),
            ("Claims", "Claims and their verified values, with the evidence "
                       "each one rests on."),
            ("Evidence", "Artefacts and receipts. An empty artefact is shown as "
                         "empty rather than omitted."),
            ("Publications", "Publication as a projection of accepted claims, "
                             "not a separate truth."),
        ]
        cards_html = "".join(f"""<div class="card">
          <div class="card-head"><span style="color:var(--dume-cyan)">▢</span>
            <span class="id">{e(name)}</span>
            <span class="right"><span class="pill" style="--c:var(--text-muted)">
              not built</span></span></div>
          <div class="foot"><span>{e(purpose)}</span></div></div>"""
          for name, purpose in surfaces)
        main = (f'<main>{R.channel_head("research", "Workspace surfaces, on the same primitives as DUM-E")}'
                f'<div class="stream">{cards_html}</div></main>')
        return R.page(section="projects", context=self._collab_context("dume"),
                      main=main, title="Research · AETHRIONIS Studio")

    def agents(self) -> str:
        cohort = self.dume.cohort()
        rows = []
        for role, binding in cohort.items():
            rows.append(R.message(
                who=role.replace("_", " ").title(), when="", initials=role[:2].upper(),
                text=f"bound to {binding['runtime_id']} · family {binding['family']}",
                card=f"""<div class="card"><div class="grid4">
                  <div><div class="k">Agent identity</div><div class="v mono">{e(binding['agent_id'])}</div></div>
                  <div><div class="k">Runtime</div><div class="v">{e(binding['runtime_id'])}</div></div>
                  <div><div class="k">Model family</div><div class="v">{e(binding['family'])}</div></div>
                  <div><div class="k">Bound</div><div class="v">{e(binding['bound_at'][11:16])}</div></div>
                </div></div>"""))
        body = "".join(rows) or ('<div class="empty">No cohort has been bound yet. '
                                 'Agents appear once DUM-E deploys one.</div>')
        main = (f'<main>{R.channel_head("agents", "Role, identity, runtime and model — four things, kept apart")}'
                f'<div class="stream">{body}</div></main>')
        return R.page(section="agents", context=self._collab_context("dume"), main=main,
                      title="Agents · AETHRIONIS Studio")

    def models(self) -> str:
        rows = []
        for runtime in self.dume.runtimes():
            tone = {"AVAILABLE": "var(--success)", "UNKNOWN": "var(--text-muted)",
                    "RUNTIME_MISSING": "var(--text-muted)"}.get(
                        runtime["status"], "var(--failure)")
            roles = ", ".join(runtime["qualified"]) or \
                "not qualified — availability is not eligibility"
            rows.append(f"""<div class="card">
              <div class="card-head"><span class="id">{e(runtime['runtime_id'])}</span>
                <span class="title">{e(runtime['model'][:46])}</span>
                <span class="right"><span class="pill" style="--c:{tone}">
                  {e(runtime['status'])}</span></span></div>
              <div class="grid4">
                <div><div class="k">Family</div><div class="v">{e(runtime['family'] or '—')}</div></div>
                <div><div class="k">Mode</div><div class="v">{e(runtime['mode'])}</div></div>
                <div><div class="k">Location</div><div class="v">{'local' if runtime['local'] else 'remote'}</div></div>
              </div>
              <div class="foot"><span>Qualified for: {e(roles)}</span></div>
            </div>""")
        main = (f'<main>{R.channel_head("models", "Runtimes and the roles each has been measured to hold")}'
                f'<div class="stream">{"".join(rows)}</div></main>')
        return R.page(section="models", context=self._collab_context("dume"), main=main,
                      title="Models · AETHRIONIS Studio")

    def activity(self) -> str:
        """A semantic event stream, not a terminal dump."""
        rows = []
        for item in self.dume.activity(60):
            colour = R.TONE.get(item.get("tone", "neutral"), "var(--text-muted)")
            glyph = {"success": "✓", "failure": "!", "warning": "▲",
                     "review": "◇", "info": "●"}.get(item.get("tone"), "●")
            rows.append(f"""<div class="msg">
              <div class="avatar" style="color:{colour};font-size:15px">{glyph}</div>
              <div><div class="head"><span class="who">{e(item['title'])}</span>
                <time>{e((item.get('at') or '')[11:19])}</time></div>
                <div class="text" style="color:var(--text-secondary);font-size:12.5px">
                  {e(item.get('detail','')[:180])}</div></div></div>""")
        body = "".join(rows) or '<div class="empty">Nothing has happened yet.</div>'
        main = (f'<main>{R.channel_head("activity", "Meaningful transitions. Raw logs live in the diagnostic viewer.")}'
                f'<div class="stream">{body}</div></main>')
        return R.page(section="activity", context=self._collab_context("dume"),
                      main=main, title="Activity · AETHRIONIS Studio")


class Handler(BaseHTTPRequestHandler):
    studio: Studio = None

    # The desktop application is served from its own origin, so a fetch from it
    # to this gateway is cross-origin and the webview drops the response unless
    # this says otherwise. It failed as "Load failed" with nothing in the log
    # here — the request arrived and was answered; the answer was discarded.
    #
    # The allowed origins are named rather than "*". This gateway hands out a
    # relay invite and reads DUM-E's state; a wildcard would let any page the
    # operator happens to open read both.
    ALLOWED_ORIGINS = frozenset({
        "tauri://localhost",
        "http://tauri.localhost",
        "https://tauri.localhost",
    })

    def _cors(self):
        origin = self.headers.get("Origin")
        if origin in self.ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "content-type, accept")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def _send(self, body: bytes, content="text/html; charset=utf-8", status=200):
        self.send_response(status)
        self.send_header("Content-Type", content)
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        # The pack's security WP asks for a restrictive policy; nothing here
        # loads anything remote, so the policy can be strict from the start.
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; img-src 'self'; style-src 'self'; "
                         "form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path, content: str):
        if not path.is_file():
            return self._send(b"not found", "text/plain", 404)
        self._send(path.read_bytes(), content)

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        route = parsed.path.rstrip("/") or "/"

        if route.startswith("/static/"):
            return self._file(STYLES / Path(route).name, "text/css")
        if route.startswith("/assets/"):
            rel = route[len("/assets/"):]
            target = (ASSETS / rel).resolve()
            # A path that resolves outside the asset root is refused rather than
            # served: a static handler is the easiest place to give away a
            # filesystem.
            if ASSETS.resolve() not in target.parents:
                return self._send(b"refused", "text/plain", 403)
            return self._file(target, "image/png")
        if route.startswith("/api/"):
            return self._api(route, query)

        page = {
            "/": self.studio.home,
            "/projects": self.studio.research,
            "/dume": lambda: self.studio.dume_channel(
                query.get("channel", ["control"])[0],
                thread=query.get("thread", [""])[0],
                query=query.get("q", [""])[0],
                mode=query.get("filter", [""])[0]),
            "/dume/wp": lambda: (
                self.studio.work_package(query["id"][0],
                                         query.get("tab", ["specification"])[0])
                if query.get("id") else self.studio.work_packages()),
            "/agents": self.studio.agents,
            "/models": self.studio.models,
            "/activity": self.studio.activity,
        }.get(route)
        if page is None:
            return self._send(b"not found", "text/plain", 404)
        self._send(page().encode())


    # ---- the read-only DUM-E API the desktop app calls -------------------
    #
    # The desktop client reads its conversation from the relay. It must not
    # read DUM-E's state from there too: a message about a verdict and a
    # verdict are different objects, and the moment the client cannot tell
    # them apart, `verdict_from_text` is available to anyone who can type.
    # So canonical state comes from here, from DUM-E's own store, read-only,
    # and the client renders it as a record rather than as a message.

    def _api(self, route: str, query: dict):
        studio = self.studio
        one = lambda k, d=None: query.get(k, [d])[0]  # noqa: E731
        try:
            if route == "/api/state":
                package = studio.dume.current()
                body = {
                    "current": package.as_dict() if package else None,
                    "counts": studio.dume.counts(),
                    "runtimes": studio.dume.runtimes(),
                    "last_run": (studio.dume.last_run() or {}).get("verdict"),
                }
            elif route == "/api/packages":
                body = {"packages": [p.as_dict()
                                     for p in studio.dume.work_packages(
                                         active_only=one("all") != "1")]}
            elif route == "/api/package":
                wp_id = one("id")
                if not wp_id:
                    return self._send(b'{"error":"id is required"}',
                                      "application/json", 400)
                package = next((p for p in studio.dume.work_packages(
                    active_only=False) if p.wp_id == wp_id), None)
                if package is None:
                    return self._send(b'{"error":"no such package"}',
                                      "application/json", 404)
                body = {
                    "package": package.as_dict(),
                    "candidate": studio.dume.candidate_card(wp_id,
                                                            package.candidate),
                    "reviews": studio.dume.review_records(wp_id),
                    "verification": studio.dume.verification(wp_id),
                    "gate": studio.dume.gate(wp_id),
                    "evidence": studio.dume.evidence_files(wp_id),
                    "findings": studio.dume.findings(wp_id),
                    "history": studio.dume.history(wp_id),
                }
            elif route == "/api/activity":
                body = {"activity": studio.dume.activity(int(one("limit", 40)))}
            elif route == "/api/runtimes":
                body = {"runtimes": studio.dume.runtimes()}
            elif route == "/api/vocabulary":
                return self._vocabulary()
            elif route == "/api/relay":
                # Where AETHRIONIS's own relay is, and the invite that joins it.
                #
                # Served so the desktop client does not have to send the
                # operator to a hosted third party to obtain a community. We
                # run the relay; there is nothing to sign up for. The invite
                # lives outside the repository, on ext4, mode 0600, because
                # DATADRIVE1 is NTFS and silently discards chmod (ADR-0007).
                #
                # Bound to loopback and answering only the operator's own
                # machine. That is the same trust boundary as the database
                # this process already reads.
                invite = Path.home() / ".dume" / "secrets" / "studio-invite"
                # Whether opening the application asks for a GitHub account.
                #
                # Off by default. On a machine the operator owns, running a
                # relay the operator runs, being asked to prove an account
                # before the workspace will open is a checkpoint with nobody on
                # the other side of it. The gate earns its place when there is
                # somebody to keep out, and that is a decision about the
                # deployment, not a property of the software.
                #
                # Turned on from Settings, or by writing "require": true into
                # the membership config. Nothing else changes when it is off:
                # the roster, the queue and the approvals are all still there,
                # which is what makes turning it on a switch rather than a
                # migration.
                required = False
                try:
                    import json as _json
                    from dume.collaboration import github as _gh
                    if _gh.CONFIG.is_file():
                        required = bool(_json.loads(
                            _gh.CONFIG.read_text()).get("require", False))
                except Exception:
                    required = False
                if os.environ.get("AETHRIONIS_MEMBERSHIP") == "require":
                    required = True
                # Derived, not written down. The address in an invite is the
                # address somebody else's device will try, and loopback is the
                # one address guaranteed to be wrong for them.
                ws, http_url = self._relay_address()

                def reachable(link: str | None) -> str | None:
                    """An invite minted earlier may name an address that has
                    since stopped meaning anything — a different lease, or one
                    minted before this was derived at all. The code is what the
                    relay checks; the address is only how to get there, so it
                    is replaced rather than trusted."""
                    if not link:
                        return None
                    marker = "code="
                    if marker not in link:
                        return link
                    code = link.split(marker, 1)[1]
                    return f"buzz://join?relay={ws}&code={code}"

                body = {
                    "relay_ws": ws,
                    "relay_http": http_url,
                    "invite": reachable(invite.read_text().strip()
                                        if invite.is_file() else None),
                    "membership_required": required,
                }
            else:
                return self._send(b'{"error":"no such endpoint"}',
                                  "application/json", 404)
        except Exception as exc:
            # The client is told the read failed. It must not be handed an
            # empty object it would render as "no findings".
            return self._send(
                json.dumps({"error": str(exc)[:300]}).encode(),
                "application/json", 500)
        return self._send(json.dumps(body, indent=2, default=str).encode(),
                          "application/json")

    # ---- commanding DUM-E ---------------------------------------------------
    #
    # The same gateway the CLI and Telegram use: the same vocabulary, the same
    # four authority classes, the same audit trail. Not a second command path —
    # a second copy of the authorisation logic is a second thing that can be
    # wrong about who may do what, and the two would diverge on the first change.
    #
    # The interface gets no privilege the console does not have. A
    # DANGEROUS_ACTION still asks for confirmation, and the reply says which
    # class it was, so a reader can tell "I looked something up" from "I changed
    # something" without inspecting the verb.

    # The authorisation half is cached; the store is not. This server is
    # threaded, and a SQLite connection belongs to the thread that opened it —
    # caching one across a request pool raised "SQLite objects created in a
    # thread can only be used in that same thread" on the second command from
    # a different worker. Opening a connection per request costs microseconds
    # against a local file, and it is the only arrangement that is true.
    _authoriser = None

    @classmethod
    def _commander(cls):
        from dume.control.command_gateway import CommandGateway, Principal
        from dume.control.intent_handler import IntentHandler
        from dume.runtimes.profiles import RuntimeRegistry
        from dume.state import Store

        principals = {"studio": Principal(
            actor_id="studio", display_name="AETHRIONIS Studio",
            # The operator sitting at the machine, which is who the desktop is.
            # Not more than the console has, and the confirmation step for a
            # dangerous action is unchanged.
            max_class="DANGEROUS_ACTION")}
        if cls._authoriser is None:
            cls._authoriser = CommandGateway(
                principals,
                audit_path=DUME_REPO / "evidence" / "command_audit.jsonl")
        store = Store(DUME_REPO / "state" / "dume.db")
        handler = IntentHandler(store, RuntimeRegistry.load(),
                                DUME_REPO / "state" / "paused")
        return cls._authoriser, handler, store

    def _command(self, form: dict):
        from dume.control.command_gateway import CommandRefused

        text = (form.get("text") or [""])[0].strip()
        confirm = (form.get("confirm") or [""])[0].strip()
        if not text and not confirm:
            return self._send(b'{"error":"text is required"}',
                              "application/json", 400)
        # What the sentence was taken to mean. Telegram has done this since it
        # was built and the command bar never did, so "durum nedir" worked on a
        # phone and was refused in the application — the same words, two
        # different answers, which reads as the application being broken.
        reading = None
        if text:
            try:
                from dume.control.address import interpret
                reading, _ = interpret(text)
            except Exception:
                reading = None

        try:
            gateway, handler, store = self._commander()
            intent = gateway.translate(actor_id="studio", channel="studio",
                                       text=reading or text or f"confirm {confirm}")
        except CommandRefused as exc:
            # Not a command is usually a question. Read the state and answer it
            # rather than printing the vocabulary at somebody who asked how the
            # work was going. Nothing is run and nothing is decided.
            said = None
            if text and not text.startswith("/"):
                try:
                    from dume.control.narrate import converse
                    said = converse(text, self._state_summary())
                except Exception:
                    said = None
            if said:
                return self._send(json.dumps({
                    "outcome": "ANSWERED", "reply": said}).encode(),
                    "application/json")
            # A refusal is an answer, not a failure. 200 with a verdict, so the
            # interface renders the reason rather than a network error.
            return self._send(json.dumps({
                "outcome": "REFUSED", "reply": str(exc)}).encode(),
                "application/json")
        except Exception as exc:
            return self._send(json.dumps({
                "outcome": "ERROR", "reply": f"{type(exc).__name__}: {exc}"
            }).encode(), "application/json", 500)

        if intent.authorization_result == "AWAITING_CONFIRMATION":
            return self._send(json.dumps({
                "outcome": "AWAITING_CONFIRMATION",
                "action": intent.action,
                "confirmation_ref": intent.confirmation_ref,
                "reply": f"{intent.action} is a DANGEROUS_ACTION. It expires in "
                         "120 seconds and only this actor can confirm it.",
            }).encode(), "application/json")

        try:
            reply = handler(intent)
        except Exception as exc:
            reply = f"the command was authorised but failed: {type(exc).__name__}: {exc}"
        finally:
            store.close()
        return self._send(json.dumps({
            "outcome": "EXECUTED", "action": intent.action,
            "class": intent.klass, "audit": intent.audit_ref, "reply": reply,
        }).encode(), "application/json")

    def _state_summary(self) -> str:
        """The work as it stands, for a question that named no command."""
        try:
            gateway, handler, store = self._commander()
            try:
                intent = gateway.translate(actor_id="studio", channel="studio",
                                           text="status")
                return handler(intent) or ""
            finally:
                store.close()
        except Exception:
            return ""

    def _vocabulary(self):
        gateway, _, store = self._commander()
        store.close()
        return self._send(json.dumps({"commands": gateway.vocabulary()}).encode(),
                          "application/json")

    # ---- membership -------------------------------------------------------
    #
    # Three things kept apart: the identity is a key on this machine, the
    # membership is a GitHub account in this deployment's roster, and the
    # admission is a relay invite minted only once the two are bound. They fail
    # differently — a lost key cannot be reset, a revoked membership leaves the
    # identity intact — and merging them would make "remove someone from the
    # project" and "destroy their identity" the same operation.
    #
    # The GitHub token never reaches the interface. It is used here, to read one
    # login, and dropped.

    @staticmethod
    def _relay_address() -> tuple[str, str]:
        """Where other devices can reach the relay.

        Derived once here so an invite minted by the membership flow and one
        read from /api/relay cannot disagree — they did, and the second was
        reading a name that was never bound in its own scope.
        """
        import sys
        sys.path.insert(0, str(DUME_REPO))
        try:
            from dume.collaboration.host import relay_http, relay_ws
            return relay_ws(), relay_http()
        except Exception:
            return "ws://127.0.0.1:3000", "http://127.0.0.1:3000"

    def _membership(self, route: str, form: dict):
        try:
            from dume.collaboration import github
        except ImportError as exc:
            return self._send(json.dumps({
                "error": f"the membership module could not be loaded: {exc}"
            }).encode(), "application/json", 500)

        def one(key, default=""):
            return form.get(key, [default])[0]

        try:
            roster = github.load_roster()
            if route == "/api/membership/roster":
                # What this deployment admits, and who is waiting on it. Read by
                # the settings panel; the same data `dume membership` prints.
                try:
                    roster = github.load_roster()
                    import json as _json
                    raw = _json.loads(github.CONFIG.read_text())
                    body = {"configured": True, "client_id": roster.client_id,
                            "logins": list(roster.logins), "org": roster.org,
                            "require": bool(raw.get("require", False))}
                except github.NotConfigured as exc:
                    body = {"configured": False, "reason": str(exc),
                            "logins": [], "org": None, "require": False}
                body["pending"] = github.pending()
                return self._send(json.dumps(body).encode(), "application/json")

            if route == "/api/membership/decide":
                login, verdict = one("login"), one("verdict")
                if not login or verdict not in ("approve", "deny"):
                    return self._send(
                        b'{"error":"login and verdict=approve|deny are required"}',
                        "application/json", 400)
                entry = github.decide(login, approve=verdict == "approve")
                return self._send(json.dumps(entry).encode(), "application/json")

            if route == "/api/membership/configure":
                # Writing the client id from the interface, so the operator does
                # not have to find a file to start. The org may be cleared by
                # sending it empty; the client id may not, because an empty one
                # would leave a deployment that says it is configured and is not.
                client_id = one("client_id").strip()
                if not client_id:
                    return self._send(b'{"error":"client_id is required"}',
                                      "application/json", 400)
                config = github.CONFIG
                config.parent.mkdir(parents=True, exist_ok=True)
                data = json.loads(config.read_text()) if config.is_file() else {}
                data["client_id"] = client_id
                data["org"] = one("org").strip() or None
                data["require"] = one("require") == "1"
                data.setdefault("logins", [])
                config.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
                config.chmod(0o600)
                return self._send(b'{"status":"written"}', "application/json")

            if route == "/api/membership/begin":
                if roster.is_empty():
                    return self._send(json.dumps({
                        "error": "this deployment admits nobody yet: the roster "
                                 "names no logins and no organisation."
                    }).encode(), "application/json", 409)
                body = github.begin(roster)
                # The device code is the secret half of the exchange; the
                # interface needs it to poll, and it never leaves this machine.
                return self._send(json.dumps(body).encode(), "application/json")

            if route == "/api/membership/poll":
                device_code = one("device_code")
                if not device_code:
                    return self._send(b'{"error":"device_code is required"}',
                                      "application/json", 400)
                token = github.redeem(roster, device_code)
                if token is None:
                    return self._send(b'{"status":"pending"}', "application/json")
                verdict = github.admit(roster, token)
                if not verdict["admitted"]:
                    return self._send(json.dumps({
                        "status": "refused", **verdict,
                    }).encode(), "application/json", 403)
                invite = Path.home() / ".dume" / "secrets" / "studio-invite"
                return self._send(json.dumps({
                    "status": "admitted",
                    "login": verdict["login"],
                    "via": verdict.get("via"),
                    "relay_ws": self._relay_address()[0],
                    "invite": invite.read_text().strip()
                              if invite.is_file() else None,
                }).encode(), "application/json")
        except github.NotConfigured as exc:
            return self._send(json.dumps({
                "error": str(exc), "unconfigured": True,
            }).encode(), "application/json", 501)
        except github.MembershipError as exc:
            return self._send(json.dumps({"error": str(exc)}).encode(),
                              "application/json", 502)
        return self._send(b'{"error":"no such endpoint"}', "application/json", 404)

    def do_POST(self):  # noqa: N802
        # Withholding the CORS header is not a refusal. A page on another origin
        # cannot read the answer, but the request still arrived and the command
        # still ran — which for `kill`, `retry` or `decide` is the whole of the
        # damage. So a request whose Origin is not one of ours is refused before
        # anything is parsed.
        #
        # A missing Origin is allowed: curl and the CLI send none, and they are
        # not browsers being steered by a page. Only a *wrong* one is an attempt.
        origin = self.headers.get("Origin")
        if origin is not None and origin not in self.ALLOWED_ORIGINS:
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"outcome":"REFUSED",'
                             b'"reply":"this origin may not command AETHRIONIS"}')
            return

        length = int(self.headers.get("Content-Length", 0))
        form = urllib.parse.parse_qs(self.rfile.read(length).decode())

        def one(key, default=""):
            return form.get(key, [default])[0]

        studio = self.studio
        channel, thread = one("channel", "control"), one("thread")
        route = urllib.parse.urlparse(self.path).path.rstrip("/") or "/"
        if route.startswith("/api/membership/"):
            return self._membership(route, form)
        if route == "/api/command":
            return self._command(form)
        target = "/dume?channel=" + urllib.parse.quote(channel)

        try:
            if route == "/say":
                body = one("body").strip()
                if body:
                    studio.workspace.post(Message(
                        channel_id=f"ch:dume:{channel}", space_id="space:dume",
                        sender_actor_id=studio.me, message_type=one("type", "STATUS"),
                        body=body, in_reply_to=thread or None,
                        thread_root=thread or None))
                    studio.workspace.save_draft(f"ch:dume:{channel}", studio.me, "")
            elif route == "/react":
                studio.workspace.react(one("message"), studio.me, one("glyph", "👍"))
            elif route == "/pin":
                studio.workspace.pin(one("message"), one("pinned") != "0")
        except Exception as exc:
            # A refused message is reported. Swallowing it would show a sent
            # message that was never stored.
            target += "&error=" + urllib.parse.quote(str(exc)[:200])
            thread = ""

        if thread:
            target += "&thread=" + urllib.parse.quote(thread)
        self.send_response(303)
        self.send_header("Location", target)
        self.end_headers()

    def log_message(self, fmt, *args):
        """One line per request, to stderr.

        Silenced upstream, and that silence cost an afternoon: with the screen
        locked the window renders blank, so the only way to tell a working
        application from a dead one is what it asks for. A gateway that answers
        without saying it answered leaves nothing to look at.
        """
        import sys
        print(f"  {self.address_string()}  {fmt % args}", file=sys.stderr,
              flush=True)


def serve(host: str = "127.0.0.1", port: int = 8100) -> None:
    Handler.studio = Studio()
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"AETHRIONIS Studio on http://{host}:{port}  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    serve()
