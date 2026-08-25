"""One workspace — AETHRIONIS — and the spaces inside it.

DUM-E is a space, not the application. That distinction is the point of the
whole exercise: a commissioning harness is one concern among several, and giving
it its own workspace would make every other concern look like an afterthought
bolted onto it.

Spaces are for concerns that have different participants and different rules.
Channels are for surfaces within a concern. Threads are for a conversation that
has to be answerable later.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..contracts.messages import EMBARGOED, Message, MessageRefused


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Space:
    """A concern with its own participants and its own rules."""
    space_id: str
    name: str
    purpose: str
    # What this space is allowed to decide. Empty means it decides nothing and
    # is a place to talk — which is a legitimate and common answer.
    decides: tuple[str, ...] = ()
    created_at: str = field(default_factory=_now)

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Channel:
    """A surface within a space."""
    channel_id: str
    space_id: str
    name: str
    purpose: str = ""
    # A channel bound to a task carries that task's cohort visibility.
    task_id: str | None = None
    # Set when the channel exists on a backend as well.
    backend_ref: str | None = None
    created_at: str = field(default_factory=_now)

    def as_dict(self) -> dict:
        return asdict(self)


SCHEMA = """
CREATE TABLE IF NOT EXISTS space (
    space_id TEXT PRIMARY KEY, name TEXT NOT NULL, purpose TEXT NOT NULL,
    decides TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS channel (
    channel_id TEXT PRIMARY KEY, space_id TEXT NOT NULL, name TEXT NOT NULL,
    purpose TEXT NOT NULL DEFAULT '', task_id TEXT, backend_ref TEXT,
    created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS actor (
    actor_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, kind TEXT NOT NULL,
    role_id TEXT, persona_id TEXT, runtime_id TEXT, model_id TEXT,
    backend_ref TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS membership (
    space_id TEXT NOT NULL, actor_id TEXT NOT NULL, alias TEXT,
    PRIMARY KEY (space_id, actor_id));
CREATE TABLE IF NOT EXISTS message (
    message_id TEXT PRIMARY KEY, space_id TEXT NOT NULL, channel_id TEXT NOT NULL,
    sender_actor_id TEXT NOT NULL, message_type TEXT NOT NULL, body TEXT NOT NULL,
    task_id TEXT, cohort_id TEXT, thread_ref TEXT, in_reply_to TEXT,
    recipient_actor_ids TEXT NOT NULL DEFAULT '[]',
    artifact_refs TEXT NOT NULL DEFAULT '[]',
    visibility_class TEXT NOT NULL, embargo_state TEXT NOT NULL,
    policy_decision_ref TEXT, backend_ref TEXT, digest TEXT NOT NULL,
    created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS resolution (
    id INTEGER PRIMARY KEY AUTOINCREMENT, alias TEXT NOT NULL,
    space_id TEXT NOT NULL, resolved_actor_id TEXT, outcome TEXT NOT NULL,
    at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS message_channel ON message(channel_id, created_at);
"""


class Workspace:
    """The store. SQLite because the workspace is one operator's, not a service."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ---- spaces and channels -------------------------------------------

    def add_space(self, space: Space) -> Space:
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO space VALUES (?,?,?,?,?)",
                (space.space_id, space.name, space.purpose,
                 json.dumps(list(space.decides)), space.created_at))
        return space

    def spaces(self) -> list[Space]:
        return [Space(r["space_id"], r["name"], r["purpose"],
                      tuple(json.loads(r["decides"])), r["created_at"])
                for r in self.conn.execute("SELECT * FROM space ORDER BY name")]

    def add_channel(self, channel: Channel) -> Channel:
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO channel VALUES (?,?,?,?,?,?,?)",
                (channel.channel_id, channel.space_id, channel.name,
                 channel.purpose, channel.task_id, channel.backend_ref,
                 channel.created_at))
        return channel

    def channels(self, space_id: str | None = None) -> list[Channel]:
        sql = "SELECT * FROM channel"
        args: tuple = ()
        if space_id:
            sql += " WHERE space_id=?"
            args = (space_id,)
        return [Channel(r["channel_id"], r["space_id"], r["name"], r["purpose"],
                        r["task_id"], r["backend_ref"], r["created_at"])
                for r in self.conn.execute(sql + " ORDER BY name", args)]

    # ---- actors ---------------------------------------------------------

    def add_actor(self, actor, space_ids: list[str] | None = None,
                  alias: str | None = None):
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO actor VALUES (?,?,?,?,?,?,?,?,?)",
                (actor.actor_id, actor.display_name, actor.kind, actor.role_id,
                 actor.persona_id, actor.runtime_id, actor.model_id,
                 actor.backend_ref, actor.created_at))
            for space_id in space_ids or []:
                self.conn.execute(
                    "INSERT OR REPLACE INTO membership VALUES (?,?,?)",
                    (space_id, actor.actor_id, alias or actor.role_id))
        return actor

    def actors(self, space_id: str | None = None) -> list[dict]:
        if space_id:
            rows = self.conn.execute(
                "SELECT a.*, m.alias FROM actor a JOIN membership m "
                "ON a.actor_id = m.actor_id WHERE m.space_id=? "
                "ORDER BY a.display_name", (space_id,))
        else:
            rows = self.conn.execute(
                "SELECT a.*, NULL AS alias FROM actor a ORDER BY a.display_name")
        return [dict(r) for r in rows]

    def cohort_members(self, space_id: str) -> set[str]:
        return {r["actor_id"] for r in self.conn.execute(
            "SELECT actor_id FROM membership WHERE space_id=?", (space_id,))}

    # ---- mentions -------------------------------------------------------

    def resolve_alias(self, alias: str, space_id: str) -> str | None:
        """Alias to actor id, audited.

        The alias is convenience; what gets recorded is the resolution. An alias
        that resolves to nothing is recorded too — a mention of a role nobody is
        filling is worth knowing about, and silently dropping it makes a message
        look delivered when it reached no one.
        """
        alias = alias.lstrip("@").replace("-", "_")
        row = self.conn.execute(
            "SELECT actor_id FROM membership WHERE space_id=? AND alias=?",
            (space_id, alias)).fetchone()
        actor_id = row["actor_id"] if row else None
        with self.conn:
            self.conn.execute(
                "INSERT INTO resolution (alias,space_id,resolved_actor_id,outcome,at) "
                "VALUES (?,?,?,?,?)",
                (alias, space_id, actor_id,
                 "RESOLVED" if actor_id else "UNRESOLVED", _now()))
        return actor_id

    def resolutions(self, limit: int = 50) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM resolution ORDER BY id DESC LIMIT ?", (limit,))]

    # ---- messages -------------------------------------------------------

    def post(self, message: Message) -> Message:
        message.validate()
        with self.conn:
            self.conn.execute(
                "INSERT INTO message VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (message.message_id, message.space_id, message.channel_id,
                 message.sender_actor_id, message.message_type, message.body,
                 message.task_id, message.cohort_id, message.thread_ref,
                 message.in_reply_to,
                 json.dumps(message.recipient_actor_ids),
                 json.dumps(message.artifact_refs),
                 message.visibility_class, message.embargo_state,
                 message.policy_decision_ref, message.backend_ref,
                 message.digest(), message.created_at))
        return message

    def _row_to_message(self, row: sqlite3.Row) -> Message:
        return Message(
            space_id=row["space_id"], channel_id=row["channel_id"],
            sender_actor_id=row["sender_actor_id"],
            message_type=row["message_type"], body=row["body"],
            message_id=row["message_id"], task_id=row["task_id"],
            cohort_id=row["cohort_id"], thread_ref=row["thread_ref"],
            in_reply_to=row["in_reply_to"],
            recipient_actor_ids=json.loads(row["recipient_actor_ids"]),
            artifact_refs=json.loads(row["artifact_refs"]),
            visibility_class=row["visibility_class"],
            embargo_state=row["embargo_state"],
            policy_decision_ref=row["policy_decision_ref"],
            backend_ref=row["backend_ref"], created_at=row["created_at"])

    def read(self, channel_id: str, *, as_actor: str | None = None,
             limit: int = 200) -> list[Message]:
        rows = self.conn.execute(
            "SELECT * FROM message WHERE channel_id=? ORDER BY created_at, rowid "
            "LIMIT ?", (channel_id, limit))
        messages = [self._row_to_message(r) for r in rows]
        if as_actor is None:
            return messages
        space_id = messages[0].space_id if messages else None
        members = self.cohort_members(space_id) if space_id else set()
        return [m for m in messages if m.visible_to(as_actor, members)]

    def open_items(self, space_id: str | None = None) -> list[Message]:
        """Challenges, requests, disagreements and blockers with no reply.

        The thing a workspace is for: a conversation that converges leaves
        nothing here, and one that does not shows exactly what it left behind.
        """
        sql = ("SELECT * FROM message WHERE message_type IN "
               "('CHALLENGE','REQUEST','DISAGREEMENT','BLOCKER')")
        args: list = []
        if space_id:
            sql += " AND space_id=?"
            args.append(space_id)
        candidates = [self._row_to_message(r) for r in self.conn.execute(sql, args)]
        answered = {r["in_reply_to"] for r in self.conn.execute(
            "SELECT DISTINCT in_reply_to FROM message WHERE in_reply_to IS NOT NULL")}
        return [m for m in candidates if m.message_id not in answered]

    def release_embargo(self, channel_id: str, actor_id: str) -> int:
        """Release one actor's embargoed messages once they have committed.

        Released per author, never in bulk: the point is that each independent
        contribution is fixed before its author can see anyone else's.
        """
        with self.conn:
            cursor = self.conn.execute(
                "UPDATE message SET embargo_state='RELEASED' WHERE channel_id=? "
                "AND sender_actor_id=? AND embargo_state=?",
                (channel_id, actor_id, EMBARGOED))
        return cursor.rowcount
