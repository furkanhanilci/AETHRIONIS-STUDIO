"""What a collaboration backend must be able to do, and what happens when it cannot.

The architecture is unusually strict here, and for a good reason: a task that
needs round-zero isolation deployed onto a backend that cannot deliver privately
does not degrade gracefully. It silently stops being an independent review, and
nothing in the resulting record says so.

So capabilities are declared, a deployment states what it requires, and a
missing capability is a deployment failure — never permission to relax the
requirement.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# The capability surface the fabric asks about. Named after what a task needs,
# not after what any particular backend happens to provide.
TARGETED_DELIVERY = "targeted_delivery"        # to named recipients only
PRE_SEAL_ISOLATION = "pre_seal_isolation"      # embargo before release
THREADS = "threads"                            # conversation correlation
ORDERED = "ordered_delivery"                   # and deduplicated
ACTOR_BINDING = "actor_identity_binding"       # a message is attributable
LIFECYCLE = "actor_lifecycle"                  # start, stop, cancel
RUNTIME_ATTACH = "runtime_attachment"
AUDIT_EXPORT = "audit_export"
GIT_LINKAGE = "git_linkage"
REMOTE_AGENTS = "remote_agents"
HUMAN_PARTICIPATION = "human_participation"

ALL_CAPABILITIES = (
    TARGETED_DELIVERY, PRE_SEAL_ISOLATION, THREADS, ORDERED, ACTOR_BINDING,
    LIFECYCLE, RUNTIME_ATTACH, AUDIT_EXPORT, GIT_LINKAGE, REMOTE_AGENTS,
    HUMAN_PARTICIPATION)


class BackendUnqualified(RuntimeError):
    """A deployment needs something this backend has not shown it can do."""


class BackendUnavailable(RuntimeError):
    """The backend cannot be reached.

    Distinct from unqualified: one is a permanent property of the backend, the
    other is today's weather. They call for different responses and must not be
    reported as the same thing.
    """


@dataclass
class BackendProfile:
    backend_id: str
    description: str
    capabilities: frozenset[str] = field(default_factory=frozenset)
    # What was actually checked, rather than what the vendor claims. A
    # capability that has not been exercised is listed as unverified, and the
    # difference is recorded rather than smoothed over.
    verified: frozenset[str] = field(default_factory=frozenset)
    notes: str = ""

    def qualifies_for(self, required: set[str]) -> tuple[bool, set[str]]:
        missing = set(required) - set(self.capabilities)
        return (not missing), missing

    def as_dict(self) -> dict:
        return {"backend_id": self.backend_id, "description": self.description,
                "capabilities": sorted(self.capabilities),
                "verified": sorted(self.verified),
                "unverified": sorted(set(self.capabilities) - set(self.verified)),
                "notes": self.notes}


class CollaborationBackend:
    """The interface. Deliberately narrow.

    A backend delivers and reads. It does not decide who may see what, what a
    message means, or whether anything follows from it — those are AETHRIONIS's,
    and a backend that offered to do them would be offering to become the
    semantics.
    """

    profile: BackendProfile

    def deliver(self, message, recipients_backend_refs: list[str]) -> str:
        """Deliver, and return the backend's own reference for it."""
        raise NotImplementedError

    def fetch(self, channel_backend_ref: str, limit: int = 100) -> list[dict]:
        """Raw backend events. Canonicalised elsewhere, never domain truth here."""
        raise NotImplementedError

    def ensure_channel(self, channel) -> str:
        raise NotImplementedError

    def health(self) -> dict:
        raise NotImplementedError


def require(profile: BackendProfile, required: set[str], task: str = "") -> None:
    """Refuse a deployment the backend cannot honour."""
    ok, missing = profile.qualifies_for(required)
    if not ok:
        raise BackendUnqualified(
            f"{profile.backend_id} cannot provide {', '.join(sorted(missing))}"
            + (f" for {task}" if task else "")
            + ". A missing capability is a deployment failure, not permission "
              "to relax the requirement.")
