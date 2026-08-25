"""The workspace store: channels, threads, messages, reactions, identities.

Adapted from Buzz's domain model — channels and threads as distinct things, a
thread correlated by root and reply reference, a mention as a recipient rather
than a permission — with an AETHRIONIS contract underneath that Buzz does not
have: every message carries a type, a visibility class and an embargo state, and
none of them can be inferred from its text.

SQLite because the workspace is one operator's and runs beside the harness it
watches. It is a place things are recorded, not a service.
"""
from __future__ import annotations

import json
import secrets
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path.home() / ".aethrionis" / "studio.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


SCHEMA = """
CREATE TABLE IF NOT EXISTS space (
    space_id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL,
    purpose TEXT NOT NULL DEFAULT '', decides TEXT NOT NULL DEFAULT '[]',
    accent TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS channel (
    channel_id TEXT PRIMARY KEY, space_id TEXT NOT NULL, name TEXT NOT NULL,
    purpose TEXT NOT NULL DEFAULT '', archived INTEGER NOT NULL DEFAULT 0,
    task_id TEXT, backend_ref TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS actor (
    actor_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, kind TEXT NOT NULL,
    role_id TEXT, persona_id TEXT, runtime_id TEXT, model_id TEXT,
    pubkey TEXT, about TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS membership (
    space_id TEXT NOT NULL, actor_id TEXT NOT NULL, alias TEXT,
    member_role TEXT NOT NULL DEFAULT 'member',
    PRIMARY KEY (space_id, actor_id));
CREATE TABLE IF NOT EXISTS message (
    message_id TEXT PRIMARY KEY, channel_id TEXT NOT NULL, space_id TEXT NOT NULL,
    sender_actor_id TEXT NOT NULL, message_type TEXT NOT NULL, body TEXT NOT NULL,
    thread_root TEXT, in_reply_to TEXT, task_id TEXT,
    recipients TEXT NOT NULL DEFAULT '[]', artifact_refs TEXT NOT NULL DEFAULT '[]',
    visibility TEXT NOT NULL DEFAULT 'PUBLIC',
    embargo TEXT NOT NULL DEFAULT 'NOT_APPLICABLE',
    edited_at TEXT, deleted INTEGER NOT NULL DEFAULT 0,
    pinned INTEGER NOT NULL DEFAULT 0, backend_ref TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reaction (
    message_id TEXT NOT NULL, actor_id TEXT NOT NULL, glyph TEXT NOT NULL,
    at TEXT NOT NULL, PRIMARY KEY (message_id, actor_id, glyph));
CREATE TABLE IF NOT EXISTS read_marker (
    channel_id TEXT NOT NULL, actor_id TEXT NOT NULL, last_seen TEXT NOT NULL,
    PRIMARY KEY (channel_id, actor_id));
CREATE TABLE IF NOT EXISTS draft (
    channel_id TEXT NOT NULL, actor_id TEXT NOT NULL, body TEXT NOT NULL,
    message_type TEXT NOT NULL DEFAULT 'STATUS', at TEXT NOT NULL,
    PRIMARY KEY (channel_id, actor_id));
CREATE TABLE IF NOT EXISTS resolution (
    id INTEGER PRIMARY KEY AUTOINCREMENT, alias TEXT NOT NULL, space_id TEXT NOT NULL,
    resolved_actor_id TEXT, outcome TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS notification (
    id INTEGER PRIMARY KEY AUTOINCREMENT, actor_id TEXT NOT NULL, kind TEXT NOT NULL,
    title TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', link TEXT,
    seen INTEGER NOT NULL DEFAULT 0, at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS message_channel ON message(channel_id, created_at);
CREATE INDEX IF NOT EXISTS message_thread ON message(thread_root);
"""


class WorkspaceError(RuntimeError):
    """An operation was refused because it would have recorded something untrue."""


@dataclass
class Message:
    channel_id: str
    space_id: str
    sender_actor_id: str
    message_type: str
    body: str
    message_id: str = field(default_factory=lambda: f"msg:{uuid.uuid4()}")
    thread_root: str | None = None
    in_reply_to: str | None = None
    task_id: str | None = None
    recipients: list[str] = field(default_factory=list)
    artifact_refs: list[str] = field(default_factory=list)
    visibility: str = "PUBLIC"
    embargo: str = "NOT_APPLICABLE"
    edited_at: str | None = None
    deleted: bool = False
    pinned: bool = False
    backend_ref: str | None = None
    created_at: str = field(default_factory=_now)
    reactions: dict = field(default_factory=dict)
    reply_count: int = 0

    def as_dict(self) -> dict:
        return asdict(self)


class Workspace:
    def __init__(self, path: Path | str = DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---- spaces ---------------------------------------------------------

    def upsert_space(self, space_id: str, name: str, kind: str = "collaboration",
                     purpose: str = "", decides: list[str] | None = None,
                     accent: str | None = None) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO space VALUES (?,?,?,?,?,?,?) "
                "ON CONFLICT(space_id) DO UPDATE SET name=excluded.name, "
                "kind=excluded.kind, purpose=excluded.purpose, "
                "decides=excluded.decides, accent=excluded.accent",
                (space_id, name, kind, purpose, json.dumps(decides or []),
                 accent, _now()))

    def spaces(self) -> list[dict]:
        return [dict(r, decides=json.loads(r["decides"]))
                for r in self.conn.execute("SELECT * FROM space ORDER BY name")]

    # ---- channels -------------------------------------------------------

    def upsert_channel(self, channel_id: str, space_id: str, name: str,
                       purpose: str = "", task_id: str | None = None) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO channel (channel_id,space_id,name,purpose,task_id,created_at) "
                "VALUES (?,?,?,?,?,?) ON CONFLICT(channel_id) DO UPDATE SET "
                "name=excluded.name, purpose=excluded.purpose",
                (channel_id, space_id, name, purpose, task_id, _now()))

    def channels(self, space_id: str | None = None,
                 include_archived: bool = False) -> list[dict]:
        sql = "SELECT * FROM channel WHERE 1=1"
        args: list = []
        if space_id:
            sql += " AND space_id=?"
            args.append(space_id)
        if not include_archived:
            sql += " AND archived=0"
        return [dict(r) for r in self.conn.execute(sql + " ORDER BY name", args)]

    def archive_channel(self, channel_id: str, archived: bool = True) -> None:
        """Archived, never deleted. A channel that held a challenge is part of
        how that challenge was answered."""
        with self.conn:
            self.conn.execute("UPDATE channel SET archived=? WHERE channel_id=?",
                              (1 if archived else 0, channel_id))

    # ---- actors ---------------------------------------------------------

    def upsert_actor(self, actor_id: str, display_name: str, kind: str = "agent",
                     **fields) -> None:
        columns = {"role_id": None, "persona_id": None, "runtime_id": None,
                   "model_id": None, "pubkey": None, "about": ""}
        columns.update({k: v for k, v in fields.items() if k in columns})
        with self.conn:
            self.conn.execute(
                "INSERT INTO actor VALUES (?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(actor_id) DO UPDATE SET display_name=excluded.display_name,"
                "kind=excluded.kind, role_id=excluded.role_id, "
                "persona_id=excluded.persona_id, runtime_id=excluded.runtime_id,"
                "model_id=excluded.model_id, about=excluded.about",
                (actor_id, display_name, kind, columns["role_id"],
                 columns["persona_id"], columns["runtime_id"], columns["model_id"],
                 columns["pubkey"], columns["about"], _now()))

    def join(self, space_id: str, actor_id: str, alias: str | None = None,
             member_role: str = "member") -> None:
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO membership VALUES (?,?,?,?)",
                (space_id, actor_id, alias, member_role))

    def actors(self, space_id: str | None = None) -> list[dict]:
        if space_id:
            rows = self.conn.execute(
                "SELECT a.*, m.alias, m.member_role FROM actor a "
                "JOIN membership m ON a.actor_id=m.actor_id WHERE m.space_id=? "
                "ORDER BY a.display_name", (space_id,))
        else:
            rows = self.conn.execute(
                "SELECT a.*, NULL alias, NULL member_role FROM actor a "
                "ORDER BY a.display_name")
        return [dict(r) for r in rows]

    def actor(self, actor_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM actor WHERE actor_id=?",
                                (actor_id,)).fetchone()
        return dict(row) if row else None

    # ---- mentions -------------------------------------------------------

    def resolve_alias(self, alias: str, space_id: str) -> str | None:
        """Alias to actor, recorded either way.

        An alias resolving to nobody is recorded too: a mention of a role nobody
        is filling is worth knowing about, and dropping it silently makes a
        message look delivered when it reached no one.
        """
        alias = alias.lstrip("@").rstrip(".,:;!?").replace("-", "_")
        row = self.conn.execute(
            "SELECT actor_id FROM membership WHERE space_id=? AND alias=?",
            (space_id, alias)).fetchone()
        actor_id = row["actor_id"] if row else None
        with self.conn:
            self.conn.execute(
                "INSERT INTO resolution (alias,space_id,resolved_actor_id,outcome,at) "
                "VALUES (?,?,?,?,?)", (alias, space_id, actor_id,
                                       "RESOLVED" if actor_id else "UNRESOLVED", _now()))
        return actor_id

    def resolutions(self, limit: int = 20) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM resolution ORDER BY id DESC LIMIT ?", (limit,))]

    # ---- messages -------------------------------------------------------

    def post(self, message: Message) -> Message:
        from ..contracts.messages import Message as Contract
        # Validated through the contract rather than here: the rules about what
        # a message must carry belong to AETHRIONIS's semantics, and a second copy
        # of them in the store is a second copy that can drift.
        Contract(space_id=message.space_id, channel_id=message.channel_id,
                 sender_actor_id=message.sender_actor_id,
                 message_type=message.message_type, body=message.body,
                 artifact_refs=message.artifact_refs,
                 recipient_actor_ids=message.recipients,
                 visibility_class=message.visibility,
                 embargo_state=message.embargo).validate()
        if message.in_reply_to and not message.thread_root:
            parent = self.message(message.in_reply_to)
            message.thread_root = (parent.get("thread_root") or message.in_reply_to) \
                if parent else message.in_reply_to
        with self.conn:
            self.conn.execute(
                "INSERT INTO message (message_id,channel_id,space_id,sender_actor_id,"
                "message_type,body,thread_root,in_reply_to,task_id,recipients,"
                "artifact_refs,visibility,embargo,backend_ref,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (message.message_id, message.channel_id, message.space_id,
                 message.sender_actor_id, message.message_type, message.body,
                 message.thread_root, message.in_reply_to, message.task_id,
                 json.dumps(message.recipients), json.dumps(message.artifact_refs),
                 message.visibility, message.embargo, message.backend_ref,
                 message.created_at))
        for actor_id in message.recipients:
            self.notify(actor_id, "mention",
                        f"{message.sender_actor_id} mentioned you",
                        message.body[:120], f"/dume?channel={message.channel_id}")
        return message

    def _row_to_message(self, row: sqlite3.Row) -> dict:
        item = dict(row)
        item["recipients"] = json.loads(row["recipients"])
        item["artifact_refs"] = json.loads(row["artifact_refs"])
        item["reactions"] = self.reactions(row["message_id"])
        item["reply_count"] = self.conn.execute(
            "SELECT COUNT(*) n FROM message WHERE thread_root=? AND message_id<>?",
            (row["message_id"], row["message_id"])).fetchone()["n"]
        return item

    def message(self, message_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM message WHERE message_id=?",
                                (message_id,)).fetchone()
        return self._row_to_message(row) if row else None

    def read(self, channel_id: str, *, as_actor: str | None = None,
             thread_root: str | None = None, limit: int = 200) -> list[dict]:
        if thread_root:
            rows = self.conn.execute(
                "SELECT * FROM message WHERE thread_root=? OR message_id=? "
                "ORDER BY created_at, rowid LIMIT ?",
                (thread_root, thread_root, limit))
        else:
            # Top level only: a reply belongs to its thread, and flattening them
            # into the channel is how a conversation stops being answerable.
            rows = self.conn.execute(
                "SELECT * FROM message WHERE channel_id=? AND thread_root IS NULL "
                "ORDER BY created_at, rowid LIMIT ?", (channel_id, limit))
        messages = [self._row_to_message(r) for r in rows]
        if as_actor is None:
            return messages
        members = {a["actor_id"] for a in self.actors(
            messages[0]["space_id"])} if messages else set()
        return [m for m in messages if self._visible(m, as_actor, members)]

    @staticmethod
    def _visible(message: dict, actor_id: str, members: set[str]) -> bool:
        if message["sender_actor_id"] == actor_id:
            return True
        if message["embargo"] == "EMBARGOED":
            return False
        if message["visibility"] == "PUBLIC":
            return True
        if message["visibility"] == "COHORT":
            return actor_id in members
        return actor_id in message["recipients"]

    def edit(self, message_id: str, body: str) -> None:
        """Edited, with the fact recorded. A silently rewritten message is a
        record nobody can rely on."""
        if not body.strip():
            raise WorkspaceError("an edit cannot empty a message; delete it instead")
        with self.conn:
            self.conn.execute(
                "UPDATE message SET body=?, edited_at=? WHERE message_id=?",
                (body, _now(), message_id))

    def delete(self, message_id: str) -> None:
        """Tombstoned, not removed: a reply that answered it must still point
        somewhere."""
        with self.conn:
            self.conn.execute(
                "UPDATE message SET deleted=1, body='' WHERE message_id=?",
                (message_id,))

    def pin(self, message_id: str, pinned: bool = True) -> None:
        with self.conn:
            self.conn.execute("UPDATE message SET pinned=? WHERE message_id=?",
                              (1 if pinned else 0, message_id))

    def pinned(self, channel_id: str) -> list[dict]:
        return [self._row_to_message(r) for r in self.conn.execute(
            "SELECT * FROM message WHERE channel_id=? AND pinned=1 "
            "ORDER BY created_at", (channel_id,))]

    def search(self, query: str, space_id: str | None = None,
               limit: int = 50) -> list[dict]:
        sql = "SELECT * FROM message WHERE deleted=0 AND body LIKE ?"
        args: list = [f"%{query}%"]
        if space_id:
            sql += " AND space_id=?"
            args.append(space_id)
        return [self._row_to_message(r) for r in self.conn.execute(
            sql + " ORDER BY created_at DESC LIMIT ?", args + [limit])]

    def open_items(self, space_id: str | None = None) -> list[dict]:
        """Challenges, requests, disagreements and blockers with no reply."""
        sql = ("SELECT * FROM message WHERE deleted=0 AND message_type IN "
               "('CHALLENGE','REQUEST','DISAGREEMENT','BLOCKER')")
        args: list = []
        if space_id:
            sql += " AND space_id=?"
            args.append(space_id)
        candidates = [self._row_to_message(r) for r in self.conn.execute(sql, args)]
        answered = {r["in_reply_to"] for r in self.conn.execute(
            "SELECT DISTINCT in_reply_to FROM message WHERE in_reply_to IS NOT NULL")}
        return [m for m in candidates if m["message_id"] not in answered]

    # ---- reactions ------------------------------------------------------

    def react(self, message_id: str, actor_id: str, glyph: str) -> None:
        with self.conn:
            self.conn.execute("INSERT OR IGNORE INTO reaction VALUES (?,?,?,?)",
                              (message_id, actor_id, glyph, _now()))

    def unreact(self, message_id: str, actor_id: str, glyph: str) -> None:
        with self.conn:
            self.conn.execute(
                "DELETE FROM reaction WHERE message_id=? AND actor_id=? AND glyph=?",
                (message_id, actor_id, glyph))

    def reactions(self, message_id: str) -> dict[str, int]:
        return {r["glyph"]: r["n"] for r in self.conn.execute(
            "SELECT glyph, COUNT(*) n FROM reaction WHERE message_id=? "
            "GROUP BY glyph ORDER BY n DESC", (message_id,))}

    # ---- read markers, drafts, notifications ---------------------------

    def mark_read(self, channel_id: str, actor_id: str) -> None:
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO read_marker VALUES (?,?,?)",
                              (channel_id, actor_id, _now()))

    def unread(self, channel_id: str, actor_id: str) -> int:
        row = self.conn.execute(
            "SELECT last_seen FROM read_marker WHERE channel_id=? AND actor_id=?",
            (channel_id, actor_id)).fetchone()
        since = row["last_seen"] if row else "0"
        return self.conn.execute(
            "SELECT COUNT(*) n FROM message WHERE channel_id=? AND created_at>? "
            "AND sender_actor_id<>? AND deleted=0",
            (channel_id, since, actor_id)).fetchone()["n"]

    def save_draft(self, channel_id: str, actor_id: str, body: str,
                   message_type: str = "STATUS") -> None:
        with self.conn:
            if body.strip():
                self.conn.execute("INSERT OR REPLACE INTO draft VALUES (?,?,?,?,?)",
                                  (channel_id, actor_id, body, message_type, _now()))
            else:
                self.conn.execute(
                    "DELETE FROM draft WHERE channel_id=? AND actor_id=?",
                    (channel_id, actor_id))

    def draft(self, channel_id: str, actor_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM draft WHERE channel_id=? AND actor_id=?",
            (channel_id, actor_id)).fetchone()
        return dict(row) if row else None

    def notify(self, actor_id: str, kind: str, title: str, detail: str = "",
               link: str | None = None) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO notification (actor_id,kind,title,detail,link,at) "
                "VALUES (?,?,?,?,?,?)", (actor_id, kind, title, detail, link, _now()))

    def notifications(self, actor_id: str, unseen_only: bool = False,
                      limit: int = 50) -> list[dict]:
        sql = "SELECT * FROM notification WHERE actor_id=?"
        if unseen_only:
            sql += " AND seen=0"
        return [dict(r) for r in self.conn.execute(
            sql + " ORDER BY id DESC LIMIT ?", (actor_id, limit))]

    def mark_notifications_seen(self, actor_id: str) -> None:
        with self.conn:
            self.conn.execute("UPDATE notification SET seen=1 WHERE actor_id=?",
                              (actor_id,))
