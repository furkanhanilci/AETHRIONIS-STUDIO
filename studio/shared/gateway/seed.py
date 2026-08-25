"""The AETHRIONIS workspace as it exists on first run.

Spaces are drawn where the plane and authority model draws them: each is a
concern with a different authoritative owner and different rules about what a
message there can mean. DUM-E is one of them, and the first, because it is the
harness that builds the rest.
"""
from __future__ import annotations

from pathlib import Path

from .workspace import Workspace

SPACES = [
    ("space:dume", "DUM-E", "system",
     "The commissioning harness that builds AETHRIONIS.",
     ["merge eligibility, and that by a deterministic gate rather than by "
      "anything said here"], "dume"),
    ("space:research", "Research", "collaboration",
     "Literature, sources, claims and what is still open.",
     ["nothing — the Source Registry owns bibliographic truth"], None),
    ("space:review", "Review", "collaboration",
     "Independent review and rebuttal, engineering and scientific.",
     ["nothing by itself — a verdict is a record bound to a candidate"], None),
    ("space:decisions", "Decisions", "collaboration",
     "Human scientific and architecture decisions, and their escalations.",
     ["nothing here either — a decision is signed and then announced"], None),
    ("space:operations", "Operations", "collaboration",
     "Runtimes, quotas, health and incidents.",
     ["routing and availability, which carry no scientific authority"], None),
]

CHANNELS = {
    "space:dume": [("control", "Package state, cohorts and gate verdicts."),
                   ("implementation", "Candidates and the discipline behind them."),
                   ("review", "Specification and code review."),
                   ("verification", "Fresh checkouts and their exit codes.")],
    "space:research": [("literature", "Sources, and what they actually support."),
                       ("questions", "What is not yet established.")],
    "space:review": [("engineering", "Reviews of candidates."),
                     ("science", "Claims, evidence and rebuttal.")],
    "space:decisions": [("escalations", "What could not be settled below."),
                        ("records", "Decisions and what they superseded.")],
    "space:operations": [("runtimes", "Availability, quota, qualification."),
                         ("incidents", "What broke, and what was learned.")],
}

# The commissioning roles, with the four references kept apart. A cohort binds
# them; it never merges them.
COHORT = [
    ("orchestrator", "Orchestrator", "qwen-local", "model:qwen3.8-27b"),
    ("architect", "Architect", "qwen-local", "model:qwen3.8-27b"),
    ("implementer", "Implementer", "qwen-local", "model:qwen3.8-27b"),
    ("spec_reviewer", "Specification Reviewer", "mistral-local",
     "model:mistral-small-3.2-24b"),
    ("code_reviewer", "Code Reviewer", "mistral-local",
     "model:mistral-small-3.2-24b"),
    ("verifier", "Verifier", "mistral-local", "model:mistral-small-3.2-24b"),
]

OPERATOR = "actor:human:operator"


def seed(path: Path | str, operator_name: str = "Furkan Hanilçi") -> Workspace:
    workspace = Workspace(path)
    for space_id, name, kind, purpose, decides, accent in SPACES:
        workspace.upsert_space(space_id, name, kind, purpose, decides, accent)
        for channel, channel_purpose in CHANNELS.get(space_id, []):
            workspace.upsert_channel(
                f"ch:{space_id.split(':')[1]}:{channel}", space_id, channel,
                channel_purpose)

    workspace.upsert_actor(OPERATOR, operator_name, kind="human",
                           role_id="human_commander",
                           about="Scope, architecture conflicts, irreversible "
                                 "actions. The decisions the machine may not make.")
    for space_id, *_ in SPACES:
        workspace.join(space_id, OPERATOR, "commander", "owner")

    for role, name, runtime, model in COHORT:
        actor_id = f"actor:dume:{role}"
        workspace.upsert_actor(actor_id, name, kind="agent", role_id=role,
                               persona_id=f"persona:{role}", runtime_id=runtime,
                               model_id=model)
        workspace.join("space:dume", actor_id, role)
        if role in ("spec_reviewer", "code_reviewer", "verifier"):
            workspace.join("space:review", actor_id, role)
    return workspace


def ensure(path: Path | str) -> Workspace:
    path = Path(path)
    if path.is_file():
        workspace = Workspace(path)
        if workspace.spaces():
            return workspace
        workspace.conn.close()
    return seed(path)
