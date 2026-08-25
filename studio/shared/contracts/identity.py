"""The six objects that must stay distinct.

Collapsing any two of these is the failure the architecture warns about most
often, because each collapse looks like a simplification and removes a different
guarantee:

* **CognitiveFunction → RoleContract** loses the ability to say that two roles
  need the same kind of scrutiny from different authorities.
* **RoleContract → OperationalPersona** makes the prompt the source of truth for
  what an actor is allowed to decide.
* **ActorIdentity → RuntimeProfile** means swapping a model mid-task changes who
  did the work, and the audit trail stops being about a person or an agent.
* **RuntimeProfile → ModelProfile** hides that the same model behaves
  differently under different harnesses.

A team or cohort *binds* several of these. It does not merge them.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class CognitiveFunction:
    """What kind of scrutiny or reasoning the work needs.

    Deliberately not "which agent" — a cognitive function outlives the roster
    that happens to satisfy it this week.
    """
    function_id: str
    summary: str
    requires_independence: bool = False


@dataclass(frozen=True)
class RoleContract:
    """Authority, obligations and allowed outputs. AETHRIONIS-governed.

    This is the canonical statement of what a role may decide. A persona may
    describe it in friendlier words; it may not extend it.
    """
    role_id: str
    decides: str
    may_produce: tuple[str, ...] = ()
    must_not: tuple[str, ...] = ()
    # Roles this one may not share an ActorIdentity with.
    separated_from: tuple[str, ...] = ()
    # Roles this one may not share a ModelProfile family with, where a shared
    # blind spot would make a second opinion worthless.
    family_separated_from: tuple[str, ...] = ()
    accountable_owner: str = "AETHRIONIS"


@dataclass(frozen=True)
class OperationalPersona:
    """A runtime-facing projection of a RoleContract. Not the contract.

    Compiled from the contract plus task context. If a persona and a contract
    disagree about authority, the contract wins and the persona is a defect.
    """
    persona_id: str
    role_id: str
    instructions: str
    skill_refs: tuple[str, ...] = ()
    communication_constraints: tuple[str, ...] = ()

    def projects(self, contract: RoleContract) -> bool:
        return self.role_id == contract.role_id


@dataclass(frozen=True)
class RuntimeProfile:
    """A harness and its capabilities. Not the model it runs."""
    runtime_id: str
    harness: str
    version: str = ""
    capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelProfile:
    """A model family, snapshot and configuration. Not the harness."""
    model_id: str
    family: str
    snapshot: str = ""
    context_tokens: int = 0
    local: bool = False


@dataclass
class ActorIdentity:
    """A concrete operational identity. Who did it.

    Survives a runtime switch: rebinding an actor to another model does not make
    it a different actor, and that is precisely why the two must not be one
    object.
    """
    actor_id: str
    display_name: str
    kind: str = "agent"          # agent | human | service
    role_id: str | None = None
    persona_id: str | None = None
    runtime_id: str | None = None
    model_id: str | None = None
    # The backend's own idea of this actor — a Nostr pubkey, a chat id. An
    # external reference, never the identity itself.
    backend_ref: str | None = None
    created_at: str = field(default_factory=_now)

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class ActorBinding:
    """One actor, bound into one cohort, for one task.

    The record the architecture asks for, with every reference kept separate so
    an audit can answer "who decided this, under what authority, on what model"
    without inferring any of the three from the others.
    """
    actor_id: str
    cohort_id: str
    role_id: str
    cognitive_function_id: str
    persona_id: str | None = None
    runtime_id: str | None = None
    model_id: str | None = None
    backend_ref: str | None = None
    bound_at: str = field(default_factory=_now)

    def as_dict(self) -> dict:
        return asdict(self)
