"""Buzz as a backend.

`OPTIONAL_BACKEND + ADAPTER`, exactly as the assimilation matrix classifies it.
The adapter translates an AETHRIONIS message into a Nostr event and back; it does
not invent roles, decide topology or interpret anything.

Two things this adapter is honest about rather than papering over:

* **Buzz cannot embargo.** A relay delivers to a channel; it has no notion of
  "visible to its author until they commit". So `pre_seal_isolation` is absent
  from its profile, and a round-zero review deployed here is refused rather than
  quietly downgraded into a review everyone can read.
* **Its identities are pubkeys.** They are external references. The AETHRIONIS
  actor id remains the identity, and the mapping is recorded rather than
  inferred.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .base import (ACTOR_BINDING, AUDIT_EXPORT, BackendProfile,
                   BackendUnavailable, CollaborationBackend,
                   HUMAN_PARTICIPATION, LIFECYCLE, ORDERED, REMOTE_AGENTS,
                   RUNTIME_ATTACH, TARGETED_DELIVERY, THREADS)

# The commissioning harness already speaks NIP-98 to this relay. Reusing its
# client rather than writing a second one keeps one implementation of the
# signature, which is the part that is easy to get subtly wrong.
DUME = Path("/home/otonom/Desktop/FH/DUM-E")


class BuzzBackend(CollaborationBackend):
    profile = BackendProfile(
        backend_id="buzz",
        description="Block's Buzz relay, reached over its NIP-98 HTTP bridge.",
        capabilities=frozenset({TARGETED_DELIVERY, THREADS, ORDERED,
                                ACTOR_BINDING, AUDIT_EXPORT, LIFECYCLE,
                                RUNTIME_ATTACH, REMOTE_AGENTS,
                                HUMAN_PARTICIPATION}),
        verified=frozenset({TARGETED_DELIVERY, THREADS, ORDERED, ACTOR_BINDING,
                            AUDIT_EXPORT}),
        notes="No pre-seal isolation: a relay delivers to a channel and has no "
              "notion of a message visible only to its author until committed. "
              "Round-zero isolation must not be deployed here. Lifecycle and "
              "runtime attachment exist in Buzz but through its desktop "
              "application, which is why they are listed unverified.")

    def __init__(self, base_url: str = "http://127.0.0.1:3000",
                 identity_name: str = "dume_orchestrator"):
        if str(DUME) not in sys.path:
            sys.path.insert(0, str(DUME))
        try:
            from dume.collaboration.buzz import (BuzzClient, BuzzError,
                                                 load_identity)
        except ImportError as exc:
            raise BackendUnavailable(
                f"the Buzz client is not importable: {exc}") from None
        self._error = BuzzError
        store = Path.home() / ".dume" / "secrets" / "buzz-identities.json"
        try:
            self.client = BuzzClient(base_url, load_identity(store, identity_name))
        except BuzzError as exc:
            raise BackendUnavailable(str(exc)) from None

    def ensure_channel(self, channel) -> str:
        """Derive the backend channel id rather than allocate one.

        A derivation survives a restart and a rebuild; an allocated id needs a
        table that can be lost.
        """
        from dume.collaboration.buzz import channel_id_for
        backend_ref = channel_id_for(channel.channel_id)
        try:
            self.client.create_channel(backend_ref, channel.name, channel.purpose)
        except self._error:
            pass          # already created; deriving the id is what makes this safe
        return backend_ref

    def deliver(self, message, recipients_backend_refs: list[str] | None = None) -> str:
        """Render a typed message onto the relay.

        The rendering is lossy on purpose and says so: the type, the references
        and the visibility class are the record, and the channel text is a
        human-readable projection of them.
        """
        header = f"[{message.message_type}]"
        if message.artifact_refs:
            header += " re: " + ", ".join(message.artifact_refs[:3])
        text = f"{header}\n{message.body}"
        if message.visibility_class != "PUBLIC":
            text += (f"\n\n({message.visibility_class.lower()} — the relay "
                     "delivers to the channel; visibility is enforced by the "
                     "workspace, not here)")
        try:
            result = self.client.announce(
                message.backend_ref or self._channel_ref(message),
                text, mentions=recipients_backend_refs or [])
        except self._error as exc:
            raise BackendUnavailable(str(exc)) from None
        return result["event_id"]

    def _channel_ref(self, message) -> str:
        from dume.collaboration.buzz import channel_id_for
        return channel_id_for(message.channel_id)

    def fetch(self, channel_backend_ref: str, limit: int = 100) -> list[dict]:
        try:
            return self.client.read(channel_backend_ref, limit=limit)
        except self._error as exc:
            raise BackendUnavailable(str(exc)) from None

    def health(self) -> dict:
        try:
            info = self.client.relay_info()
        except Exception as exc:
            return {"backend_id": "buzz", "reachable": False,
                    "detail": str(exc)[:200]}
        return {"backend_id": "buzz", "reachable": True,
                "detail": f"{info.get('name')} — {len(info.get('supported_nips', []))} NIPs"}
