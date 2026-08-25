"""What a message may never become.

The architecture lists seven authority transfers that must not happen. Every one
of them is tempting, because in each case a person or an agent said the right
words in the right place, and turning those words into the corresponding record
would save a step.

The reason not to is the same in all seven: the words are a *representation* of
a decision made somewhere with a signature, a candidate revision or a policy
behind it. Parsing the representation back into the decision loses whatever made
it trustworthy, and it does so silently — the resulting record looks exactly
like a real one.

So this module refuses. It is small and it exists to be imported by everything
that reads a message and might be tempted to act on it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ProhibitedTransfer:
    name: str
    tempting_because: str
    why_refused: str
    correct_path: str


TRANSFERS: dict[str, ProhibitedTransfer] = {t.name: t for t in (
    ProhibitedTransfer(
        "verdict_from_text",
        "a reviewer typed '@verifier PASS' in the review room",
        "text parsing cannot establish which candidate was verified, in which "
        "environment, by which independent identity — and a VerificationRecord "
        "that cannot answer those is indistinguishable from one that can",
        "the verifier records a VerificationRecord bound to a candidate revision"),
    ProhibitedTransfer(
        "decision_from_channel_approval",
        "the human replied 'approve' on Telegram",
        "a channel reply proves a message was sent from an account, not that an "
        "authorised human read the material and decided",
        "the authenticated Decision Service path, signed"),
    ProhibitedTransfer(
        "acceptance_from_runtime_completion",
        "the runtime reported the session completed",
        "a process exiting zero says the process exited zero; acceptance is "
        "about evidence, independence and open findings",
        "the machine gate, over recorded facts"),
    ProhibitedTransfer(
        "separation_override_by_membership",
        "the same actor is in the team for both roles",
        "operational team membership is a deployment convenience; "
        "separation of duties is a property of the RoleContract",
        "bind two ActorIdentities, one per role"),
    ProhibitedTransfer(
        "liveness_from_presence",
        "the agent shows as online",
        "presence is a backend's opinion about a connection, not a statement "
        "that the actor is doing or able to do its work",
        "a health control that exercises the capability"),
    ProhibitedTransfer(
        "approval_from_delivery_receipt",
        "the message was delivered and read",
        "a receipt proves bytes arrived at a device; it proves nothing about a "
        "human having read, understood or agreed",
        "an explicit, authenticated acknowledgement"),
    ProhibitedTransfer(
        "closure_from_vote_count",
        "four of five participants agreed",
        "a material challenge is closed by being answered, not outvoted; "
        "counting turns a disagreement about substance into a headcount",
        "address the challenge, or record it as an open finding"),
)}


class AuthorityRefused(PermissionError):
    """A message was about to become a record it cannot be."""

    def __init__(self, transfer: ProhibitedTransfer, detail: str = ""):
        self.transfer = transfer
        super().__init__(
            f"{transfer.name}: refused.\n"
            f"  tempting because: {transfer.tempting_because}\n"
            f"  why not: {transfer.why_refused}\n"
            f"  do this instead: {transfer.correct_path}"
            + (f"\n  seen: {detail}" if detail else ""))


# Shapes that look like a verdict being asserted in prose. Detected so the
# refusal can be specific, and so the audit can show what was attempted.
VERDICT_IN_TEXT = re.compile(
    r"(?i)(?:^|\s)@?(?:verifier|reviewer|spec[_\-]?reviewer|code[_\-]?reviewer)\b"
    r"[\s:,-]*\b(pass|fail|accept(?:ed)?|approve[ds]?|reject(?:ed)?|merge)\b")

APPROVAL_IN_TEXT = re.compile(
    r"(?i)^\s*(?:approve[ds]?|onayla(?:ndı|dım)?|ok(?:ay)?|lgtm|ship it)\s*[.!]?\s*$")


def refuse(name: str, detail: str = "") -> None:
    """Raise the named refusal. Used where the temptation is structural."""
    raise AuthorityRefused(TRANSFERS[name], detail)


def screen_message(body: str, message_type: str) -> list[str]:
    """Warnings for a message whose text asserts something it cannot create.

    Returns rather than raises: the message is allowed to *say* it — people talk
    about verdicts — but the platform records that nothing followed from the
    saying, and never turns it into a record.
    """
    warnings: list[str] = []
    if VERDICT_IN_TEXT.search(body):
        warnings.append(
            "this reads as a verdict. It will be delivered as a message and "
            "will not create a VerificationRecord: "
            + TRANSFERS["verdict_from_text"].correct_path)
    if APPROVAL_IN_TEXT.match(body.strip()):
        warnings.append(
            "this reads as an approval. Delivered as a message; a scientific "
            "decision comes from "
            + TRANSFERS["decision_from_channel_approval"].correct_path)
    return warnings


def assert_separation(role_a: str, role_b: str, actor_a: str, actor_b: str,
                      separated: tuple[str, ...]) -> None:
    """Two roles that must not share an identity, and do."""
    if role_b in separated and actor_a == actor_b:
        refuse("separation_override_by_membership",
               f"{actor_a} holds both {role_a} and {role_b}")
