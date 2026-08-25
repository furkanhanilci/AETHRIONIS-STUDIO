"""Work package detail: the frozen specification, the evidence, the gate.

Where the collaboration surface shows a package as a card, this shows it as a
record. Three things live here that deliberately do not live in a channel:

* **the sealed specification**, read-only and beside its digest, because a
  specification a reader could edit in the interface would stop being sealed;
* **the evidence**, including any artefact that is zero bytes, because the
  harness refuses one as evidence and hiding it here would remove the only
  signal that someone tried;
* **the gate**, check by check, with the question each one answers — a verdict
  without its checks is a claim, and this page exists so it is not one.
"""
from __future__ import annotations

from ..shell.render import block, e, kv


def sealed_specification(sections: list[dict]) -> str:
    if not sections:
        return ('<div class="card"><div class="foot"><span>No frozen packet was '
                'recorded for this package.</span></div></div>')
    blocks = []
    for section in sections:
        blocks.append(f"""<div class="card">
  <div class="card-head"><span aria-hidden="true" style="color:var(--dume-cyan)">▤</span>
    <span class="id">{e(section['name'])}</span>
    <span class="title">sealed</span>
    <span class="right"><span class="pill" style="--c:var(--text-muted)">
      {e(section['sha256'][:12])}</span></span></div>
  <pre class="sealed">{e(section['text'][:4000])}</pre>
  <div class="foot"><span>{e(section['path'])}</span>
    <span class="right">read-only · a specification you could edit here would
      not be sealed</span></div>
</div>""")
    return "".join(blocks)


def evidence_list(files: list[dict]) -> str:
    if not files:
        return ('<div class="card"><div class="foot"><span>Nothing has been '
                'recorded against this package yet.</span></div></div>')
    rows = []
    for item in files:
        tone = "var(--failure)" if item["empty"] else "var(--text-muted)"
        size = ("0 bytes — refused as evidence" if item["empty"]
                else f"{item['bytes']:,} bytes")
        rows.append(f'<div class="linked"><span style="color:{tone}" '
                    f'aria-hidden="true">◆</span>'
                    f'<span class="mono">{e(item["name"])}</span>'
                    f'<span class="n">{e(size)}</span></div>')
    return f'<div class="card">{"".join(rows)}</div>'


def gate_record(gate: dict | None) -> str:
    if not gate:
        return ('<div class="card"><div class="foot"><span>The gate has not been '
                'evaluated for this candidate.</span></div></div>')
    verdict = gate.get("verdict", "—")
    colour = "var(--success)" if verdict == "MERGE_ELIGIBLE" else "var(--failure)"
    rows = []
    for check in gate.get("checks", []):
        passed = check.get("passed")
        mark = ('<span style="color:var(--success)">✔</span>' if passed
                else '<span style="color:var(--failure)">✕</span>')
        rows.append(f"""<div class="gate-row">
  <div class="g">{mark}</div>
  <div><div class="q">{e(check.get('question',''))}</div>
    <div class="d">{e(check.get('detail','')[:160])}</div></div>
  <div class="n mono">{e(check.get('name',''))}</div>
</div>""")
    return f"""<div class="card">
  <div class="card-head"><span aria-hidden="true">⚖</span>
    <span class="id">Deterministic gate</span>
    <span class="right"><span class="pill" style="--c:{colour}">{e(verdict)}</span></span></div>
  <div class="gate">{''.join(rows)}</div>
  <div class="foot"><span>Eleven checks over recorded facts. No model is
    reachable from the gate, and a test asserts it.</span>
    <span class="right">{e(gate.get('candidate_revision','')[:12])}</span></div>
</div>"""


def history_list(entries: list[dict]) -> str:
    rows = []
    for entry in entries:
        rows.append(f'<div class="evt"><span class="d" '
                    f'style="--c:var(--text-muted)"></span>'
                    f'<span>{e(entry["from"] or "—")} → <b>{e(entry["to"])}</b>'
                    f'<span class="sub">{e(entry["actor"])}'
                    + (f' · {e(entry["reason"][:80])}' if entry["reason"] else "")
                    + f'</span></span><time>{e(entry["at"][11:16])}</time></div>')
    return "".join(rows) or '<div class="check">no transitions recorded</div>'


def findings_list(findings: list[dict]) -> str:
    if not findings:
        return '<div class="check"><span class="g">✔</span><span>no findings</span></div>'
    rows = []
    for finding in findings:
        colour = {"CRITICAL": "var(--failure)", "HIGH": "var(--failure)",
                  "MEDIUM": "var(--warning)", "LOW": "var(--text-muted)"}.get(
                      finding["severity"], "var(--text-muted)")
        rows.append(f'<div class="linked"><span style="color:{colour}" '
                    f'aria-hidden="true">▲</span>'
                    f'<span>{e(finding["summary"][:110])}</span>'
                    f'<span class="n">{e(finding["severity"])}</span></div>')
    return "".join(rows)
