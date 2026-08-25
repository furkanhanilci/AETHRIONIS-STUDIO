"""Inline work artifacts.

The design system's critical rule, and the reason these live in their own module
away from anything that renders a message: *the card renders canonical backend
data. A message saying "PASS" does not create a PASS card automatically.*

So every function here takes a record the gateway read from DUM-E, and none of
them takes a string typed by a person or an agent. A card that could be produced
from prose would be a way of manufacturing authority out of typing, which is the
first of the seven prohibited transfers.
"""
from __future__ import annotations

from ..shell.render import e

STAGE_RAIL = ("Plan", "Red", "Green", "Review", "Verify")


def wp_card(*, wp_id: str, title: str, bead: int, stage_label: str,
            next_stage: str, tone: str = "warning") -> str:
    """The work package, with the stage rail the mockup fixes.

    `bead` is the index of the current stage, taken from DUM-E's lifecycle state
    rather than from a completion percentage — a percentage is exactly the thing
    the Studio invariant forbids computing a stage from.
    """
    stages = []
    for index, label in enumerate(STAGE_RAIL):
        if index < bead:
            cls = "stage done"
        elif index == bead:
            cls = "stage current"
        else:
            cls = "stage"
        stages.append(f'<div class="{cls}"><div class="bead"></div>'
                      f'<div class="label">{e(label)}</div></div>')
    colour = {"success": "var(--success)", "failure": "var(--failure)",
              "warning": "var(--warning)", "info": "var(--info)",
              "review": "var(--review)"}.get(tone, "var(--text-muted)")
    return f"""<div class="card">
  <div class="card-head"><span aria-hidden="true" style="color:var(--dume-cyan)">▤</span>
    <span class="id">{e(wp_id)}</span>
    <span class="title">{e(title)}</span></div>
  <div class="stages">{''.join(stages)}</div>
  <div class="foot">
    <span>Stage <b style="color:{colour}">● {e(stage_label)}</b></span>
    <span class="right">Next <b>{e(next_stage)}</b></span>
  </div>
</div>"""


def candidate_card(record: dict) -> str:
    """Candidate as a PR-shaped object: sha, worktree, files, tests.

    When the recorded evidence belongs to a different candidate than the one
    under review, the card says so instead of rendering as though it were
    current. Presenting a green result from an older candidate as this one's is
    the substitution the harness refuses, and an interface that makes it look
    fine has undone the refusal in the only place anyone actually looks.
    """
    stale = bool(record.get("stale"))
    verdict = record.get("verdict") or "open"
    if stale:
        colour = "var(--warning)"
        verdict = f"{verdict} · superseded"
    elif verdict == "MERGE_ELIGIBLE":
        colour = "var(--success)"
    elif verdict == "FAILED":
        colour = "var(--failure)"
    else:
        colour = "var(--warning)"

    note = ""
    if stale:
        note = (
            '<div class="foot"><span style="color:var(--warning)">'
            f'This evidence belongs to candidate {e(record.get("candidate", ""))}. '
            f'The package under review is {e(record.get("current_candidate") or "—")}. '
            'A green result from another candidate is not evidence for this one.'
            "</span></div>")

    return f"""<div class="card">
  <div class="card-head"><span aria-hidden="true" style="color:var(--info)">⑂</span>
    <span class="id">{e(record.get('candidate','—'))}</span>
    <span class="title">candidate</span>
    <span class="right"><span class="pill" style="--c:{colour}">{e(verdict)}</span></span></div>
  <div class="grid4">
    <div><div class="k">Worktree</div><div class="v mono">{e(record.get('worktree','—'))}</div></div>
    <div><div class="k">Changed files</div><div class="v">{e(record.get('files','—'))}</div></div>
    <div><div class="k">Tests</div><div class="v">{e(record.get('tests','—'))}</div></div>
    <div><div class="k">Discipline</div><div class="v">{e(record.get('discipline','—'))}</div></div>
  </div>
  {note}
</div>"""


def review_card(record: dict) -> str:
    verdict = record.get("verdict") or "—"
    colour = "var(--success)" if verdict == "PASS" else "var(--failure)"
    findings = record.get("findings", 0)
    return f"""<div class="card">
  <div class="card-head"><span aria-hidden="true" style="color:var(--review)">◈</span>
    <span class="id">{e(record.get('kind','Review'))}</span>
    <span class="right"><span class="pill" style="--c:{colour}">{e(verdict)}</span></span></div>
  <div class="grid4">
    <div><div class="k">Verdict</div><div class="v">{e(verdict)}</div></div>
    <div><div class="k">Blocking findings</div><div class="v">{findings}</div></div>
  </div>
  <div class="foot"><span>{e(record.get('reason','')[:150])}</span></div>
</div>"""


def verification_card(record: dict) -> str:
    """The one card whose verdict comes from an exit code.

    Shown as such: the exit code is the evidence, and the fresh-checkout marker
    is there because a suite re-run in the implementer's own tree would prove
    considerably less.
    """
    passed = record.get("exit") == "0"
    colour = "var(--success)" if passed else "var(--failure)"
    return f"""<div class="card">
  <div class="card-head"><span aria-hidden="true" style="color:var(--success)">✔</span>
    <span class="id">Fresh verification</span>
    <span class="right"><span class="pill" style="--c:{colour}">
      {'PASS' if passed else 'FAIL'}</span></span></div>
  <div class="grid4">
    <div><div class="k">Candidate</div><div class="v mono">{e(record.get('candidate','')[:12])}</div></div>
    <div><div class="k">Checkout</div><div class="v">fresh clone</div></div>
    <div><div class="k">Suite</div><div class="v">{e(record.get('summary','—'))}</div></div>
    <div><div class="k">Exit code</div><div class="v mono">{e(record.get('exit','—'))}</div></div>
  </div>
  <div class="foot"><span>The exit code decides. The verifier interprets it and
    cannot overrule it.</span></div>
</div>"""
