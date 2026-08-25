"""The local backend: the workspace store itself.

Not a placeholder. A single-operator workspace with no relay is a legitimate
deployment, and it happens to be the one backend that can honour every
capability the fabric asks about, because there is no network between the
semantics and the storage.

Its real job is comparative: it is the reference against which a networked
backend's limitations become visible.
"""
from __future__ import annotations

from .base import (ACTOR_BINDING, ALL_CAPABILITIES, AUDIT_EXPORT,
                   BackendProfile, CollaborationBackend, HUMAN_PARTICIPATION,
                   ORDERED, PRE_SEAL_ISOLATION, TARGETED_DELIVERY, THREADS)


class LocalBackend(CollaborationBackend):
    profile = BackendProfile(
        backend_id="local",
        description="The workspace store. No network, therefore no delivery "
                    "semantics to lose.",
        capabilities=frozenset({TARGETED_DELIVERY, PRE_SEAL_ISOLATION, THREADS,
                                ORDERED, ACTOR_BINDING, AUDIT_EXPORT,
                                HUMAN_PARTICIPATION}),
        verified=frozenset({TARGETED_DELIVERY, PRE_SEAL_ISOLATION, THREADS,
                            ORDERED, ACTOR_BINDING, AUDIT_EXPORT}),
        notes="Cannot start or attach a runtime, and has no remote actors — "
              "those need a backend with processes behind it.")

    def __init__(self, workspace):
        self.workspace = workspace

    def deliver(self, message, recipients_backend_refs=None) -> str:
        return message.message_id

    def fetch(self, channel_backend_ref: str, limit: int = 100) -> list[dict]:
        return [m.as_dict() for m in
                self.workspace.read(channel_backend_ref, limit=limit)]

    def ensure_channel(self, channel) -> str:
        return channel.channel_id

    def health(self) -> dict:
        return {"backend_id": "local", "reachable": True,
                "detail": "in-process"}
