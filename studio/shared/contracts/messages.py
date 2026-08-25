"""Typed collaboration messages.

The architecture is precise about this: backend text is a *representation* of a
typed message, not the type itself. A room full of prose is not a collaboration
record — you cannot answer "was this challenge ever addressed" by grepping it.

So a message carries its type, its recipients, what it refers to, and what it
is allowed to be seen by. The rendering into a channel is a projection of that,
and the projection is lossy on purpose.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# The ten classes. Each is a different move in a conversation that is supposed
# to converge on something, which is why "comment" is not among them.
PROPOSAL = "PROPOSAL"                        # here is what I think we should do
CHALLENGE = "CHALLENGE"                      # I think this is wrong, and why
EVIDENCE = "EVIDENCE"                        # here is something checkable
REQUEST = "REQUEST"                          # I need something from someone
CORRECTION = "CORRECTION"                    # I was wrong; here is the fix
DISAGREEMENT = "DISAGREEMENT"                # we differ and I am recording it
CONSENSUS_CANDIDATE = "CONSENSUS_CANDIDATE"  # I believe we have converged
ABSTAIN = "ABSTAIN"                          # I decline to judge, and why
STATUS = "STATUS"                            # operational, decides nothing
BLOCKER = "BLOCKER"                          # this stops, until someone acts

MESSAGE_TYPES = (PROPOSAL, CHALLENGE, EVIDENCE, REQUEST, CORRECTION,
                 DISAGREEMENT, CONSENSUS_CANDIDATE, ABSTAIN, STATUS, BLOCKER)

# Types that assert something and therefore have to be answerable. A CHALLENGE
# nobody replied to is an open question; a STATUS nobody replied to is nothing.
REQUIRES_RESPONSE = (CHALLENGE, REQUEST, DISAGREEMENT, BLOCKER)

# Types that must name what they are about. "This is wrong" without a reference
# is an opinion about the weather.
REQUIRES_ARTIFACT = (CHALLENGE, EVIDENCE, CORRECTION, CONSENSUS_CANDIDATE)

# Who may see it.
PUBLIC = "PUBLIC"              # everyone in the space
COHORT = "COHORT"              # the task's cohort only
TARGETED = "TARGETED"          # named recipients only
PRIVATE = "PRIVATE"            # sender and one recipient
VISIBILITY = (PUBLIC, COHORT, TARGETED, PRIVATE)

# Independent-first. A round-zero reviewer must not see a peer's verdict before
# recording its own, or the second opinion is an echo of the first.
EMBARGOED = "EMBARGOED"
RELEASED = "RELEASED"
NOT_APPLICABLE = "NOT_APPLICABLE"
EMBARGO_STATES = (EMBARGOED, RELEASED, NOT_APPLICABLE)


class MessageRefused(ValueError):
    """A message was refused because it would not have said anything usable."""


@dataclass
class Message:
    space_id: str
    channel_id: str
    sender_actor_id: str
    message_type: str
    body: str
    message_id: str = field(default_factory=lambda: f"msg:{uuid.uuid4()}")
    task_id: str | None = None
    cohort_id: str | None = None
    thread_ref: str | None = None
    recipient_actor_ids: list[str] = field(default_factory=list)
    artifact_refs: list[str] = field(default_factory=list)
    visibility_class: str = PUBLIC
    embargo_state: str = NOT_APPLICABLE
    # Set when a policy decided this message may be delivered. Absent means
    # nothing decided, which is not the same as allowed.
    policy_decision_ref: str | None = None
    # The backend's own id once delivered. An external reference.
    backend_ref: str | None = None
    in_reply_to: str | None = None
    created_at: str = field(default_factory=_now)

    def as_dict(self) -> dict:
        return asdict(self)

    def digest(self) -> str:
        material = json.dumps(
            {k: v for k, v in self.as_dict().items()
             if k not in {"backend_ref", "policy_decision_ref"}},
            sort_keys=True)
        return hashlib.sha256(material.encode()).hexdigest()

    def validate(self) -> "Message":
        """Refuse a message that cannot do its job."""
        if self.message_type not in MESSAGE_TYPES:
            raise MessageRefused(
                f"{self.message_type!r} is not a message type; expected one of "
                + ", ".join(MESSAGE_TYPES))
        if self.visibility_class not in VISIBILITY:
            raise MessageRefused(f"unknown visibility class {self.visibility_class!r}")
        if self.embargo_state not in EMBARGO_STATES:
            raise MessageRefused(f"unknown embargo state {self.embargo_state!r}")
        if not self.body.strip():
            raise MessageRefused("a message with no body says nothing")
        if self.message_type in REQUIRES_ARTIFACT and not self.artifact_refs:
            raise MessageRefused(
                f"a {self.message_type} must name what it is about. Without a "
                "reference it cannot be answered, tracked or closed.")
        if self.visibility_class in (TARGETED, PRIVATE) and not self.recipient_actor_ids:
            raise MessageRefused(
                f"{self.visibility_class} delivery names no recipient")
        if self.visibility_class == PRIVATE and len(self.recipient_actor_ids) != 1:
            raise MessageRefused("PRIVATE means exactly one recipient")
        return self

    def is_open(self) -> bool:
        """Does this message still expect an answer?"""
        return self.message_type in REQUIRES_RESPONSE

    def visible_to(self, actor_id: str, cohort_members: set[str] | None = None) -> bool:
        """Whether one actor may see this message.

        Embargo beats visibility: a released-to-cohort verdict is still hidden
        from a peer who has not recorded their own, because that is the whole
        point of recording it first.
        """
        if actor_id == self.sender_actor_id:
            return True
        if self.embargo_state == EMBARGOED:
            return False
        if self.visibility_class == PUBLIC:
            return True
        if self.visibility_class == COHORT:
            return actor_id in (cohort_members or set())
        return actor_id in self.recipient_actor_ids
