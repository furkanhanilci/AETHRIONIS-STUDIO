"""Reading DUM-E's canonical state.

The invariant the Studio pack states plainly: *Studio never computes acceptance
from chat or visual completion percentage. It renders DUM-E's authoritative
records.*

So this module reads and never writes, and everything it returns is traceable to
a row in DUM-E's state store or a file in its evidence directory. Where a value
is absent it says so rather than substituting a plausible default — a stage
inferred from a percentage is exactly the failure the invariant names.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

DUME = Path("/home/otonom/Desktop/FH/DUM-E")
STATE_DB = DUME / "state" / "dume.db"
EVIDENCE = DUME / "evidence"

# The Superpowers pipeline as the commissioning lifecycle realises it. The card
# shows five beads because that is what a reader can hold; the lifecycle has
# more states and the detail view carries them.
STAGE_RAIL = ("Plan", "Red", "Green", "Review", "Verify")

# Which rail bead a lifecycle state lights.
STATE_TO_BEAD = {
    "DISCOVERED": -1, "READY": -1, "PACKAGED": 0, "PLANNED": 0,
    "EXECUTING": 1, "SPEC_REVIEW": 3, "CODE_REVIEW": 3, "VERIFYING": 4,
    "TECH_COMPLETE": 4, "ACCEPTANCE_READY": 4, "ACCEPTED": 4,
    "FAILED": 1, "RETRY": 0, "BLOCKED": -1,
}

STATE_TONE = {
    "ACCEPTED": "success", "TECH_COMPLETE": "success",
    "ACCEPTANCE_READY": "info", "VERIFYING": "info",
    "SPEC_REVIEW": "review", "CODE_REVIEW": "review",
    "EXECUTING": "warning", "PLANNED": "warning", "PACKAGED": "warning",
    "READY": "warning", "FAILED": "failure", "BLOCKED": "failure",
    "RETRY": "review", "DISCOVERED": "neutral",
}


@dataclass
class WorkPackage:
    wp_id: str
    title: str
    state: str
    wave: int
    candidate: str | None
    producer: str | None
    waiting_on: list[str] = field(default_factory=list)

    def bead(self) -> int:
        return STATE_TO_BEAD.get(self.state, -1)

    def tone(self) -> str:
        return STATE_TONE.get(self.state, "neutral")

    def next_stage(self) -> str:
        """What the lifecycle permits next — read from DUM-E, not guessed."""
        try:
            from dume.state.store import TRANSITIONS
        except ImportError:
            return "—"
        allowed = sorted(TRANSITIONS.get(self.state, set()))
        forward = [s for s in allowed if s not in {"BLOCKED", "FAILED"}]
        return (forward or allowed or ["—"])[0].replace("_", " ").title()

    def as_dict(self) -> dict:
        return asdict(self)


class DumeGateway:
    """Read-only access to the commissioning harness."""

    def __init__(self, db: Path | str = STATE_DB, evidence: Path | str = EVIDENCE):
        self.db = Path(db)
        self.evidence = Path(evidence)

    # ---- availability ---------------------------------------------------

    def available(self) -> bool:
        return self.db.is_file()

    def _rows(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        if not self.available():
            return []
        # Read-only on purpose: Studio renders DUM-E's records and must not be
        # able to change one by accident, however convenient that would be.
        conn = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            return list(conn.execute(sql, args))
        except sqlite3.Error:
            return []
        finally:
            conn.close()

    # ---- work packages --------------------------------------------------

    def work_packages(self, active_only: bool = True) -> list[WorkPackage]:
        rows = self._rows("SELECT * FROM wp ORDER BY wave, wp_id")
        packages = []
        for row in rows:
            if active_only and row["state"] == "DISCOVERED":
                continue
            packages.append(WorkPackage(
                row["wp_id"], row["title"], row["state"], row["wave"],
                row["candidate_revision"], row["producer_actor"],
                self._unmet(row["wp_id"])))
        return packages

    def _unmet(self, wp_id: str) -> list[str]:
        deps = [r["depends_on"] for r in self._rows(
            "SELECT depends_on FROM dependency WHERE wp_id=?", (wp_id,))]
        if not deps:
            return []
        marks = ",".join("?" * len(deps))
        accepted = {r["wp_id"] for r in self._rows(
            f"SELECT wp_id FROM wp WHERE wp_id IN ({marks}) AND state='ACCEPTED'",
            tuple(deps))}
        return [d for d in deps if d not in accepted]

    def current(self) -> WorkPackage | None:
        """The package a reader most likely means by "now".

        The furthest through the pipeline, not the most recently touched: a
        package that failed and is waiting is more interesting than one that was
        merely updated.
        """
        active = self.work_packages()
        if not active:
            return None
        order = ["ACCEPTANCE_READY", "TECH_COMPLETE", "VERIFYING", "CODE_REVIEW",
                 "SPEC_REVIEW", "EXECUTING", "PLANNED", "PACKAGED", "READY",
                 "FAILED", "RETRY", "BLOCKED", "ACCEPTED"]
        return sorted(active, key=lambda p: order.index(p.state)
                      if p.state in order else 99)[0]

    def counts(self) -> dict[str, int]:
        return {r["state"]: r["n"] for r in self._rows(
            "SELECT state, COUNT(*) n FROM wp GROUP BY state")}

    # ---- evidence -------------------------------------------------------

    def last_run(self) -> dict | None:
        path = self.evidence / "live" / "run_result.json"
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return None

    def review_records(self, wp_id: str) -> list[dict]:
        """What each reviewer actually recorded, from the evidence files."""
        out = []
        for kind, label in (("specification_compliance", "Specification"),
                            ("code_quality", "Code quality")):
            path = self.evidence / "live" / wp_id / f"{kind}.json"
            if path.is_file():
                try:
                    record = json.loads(path.read_text())
                except json.JSONDecodeError:
                    continue
                out.append({"kind": label, "verdict": record.get("verdict"),
                            "reason": record.get("reason", ""),
                            "findings": len(record.get("findings") or [])})
        return out

    def verification(self, wp_id: str) -> dict | None:
        path = self.evidence / "live" / wp_id / "fresh_verification.txt"
        if not path.is_file():
            return None
        text = path.read_text()
        candidate = next((l.split("=", 1)[1] for l in text.splitlines()
                          if l.startswith("candidate=")), "")
        exit_code = next((l.split("=", 1)[1] for l in text.splitlines()
                          if l.startswith("exit=")), "")
        passed = next((l for l in text.splitlines() if " passed" in l), "")
        return {"candidate": candidate.strip(), "exit": exit_code.strip(),
                "summary": passed.strip()[:80], "fresh_checkout": True}

    def candidate_card(self, wp_id: str, current: str | None = None) -> dict | None:
        """The candidate as a PR-shaped object, from the run report.

        `current` is the candidate DUM-E's state store records for this package.
        When the recorded run produced a different one, the card says so rather
        than rendering as though the evidence belonged to the candidate under
        review — presenting a green result from an older candidate as current is
        the exact substitution the harness refuses, and an interface that makes
        it look fine has undone the refusal in the only place anyone looks.
        """
        report = self.last_run()
        if not report or report.get("wp_id") != wp_id:
            return None
        steps = {s["name"]: s for s in report.get("steps", [])}
        implement = steps.get("implement", {}).get("detail", "")
        protected = steps.get("protected_paths", {}).get("detail", "")
        files = next((w for w in protected.split() if w.isdigit()), "—")
        verification = self.verification(wp_id) or {}
        produced = report.get("candidate_revision") or ""
        return {
            "candidate": produced[:12],
            "stale": bool(current and produced and not produced.startswith(current[:12])),
            "current_candidate": (current or "")[:12],
            "worktree": steps.get("worktree", {}).get("detail", "").split(" off ")[0],
            "files": files,
            "tests": verification.get("summary", "—"),
            "discipline": implement.split("evidence: ")[-1] if "evidence: " in implement else "—",
            "verdict": report.get("verdict"),
        }

    # ---- runtimes -------------------------------------------------------

    def runtimes(self) -> list[dict]:
        config = DUME / "config" / "runtimes.json"
        if not config.is_file():
            return []
        try:
            data = json.loads(config.read_text())
        except json.JSONDecodeError:
            return []
        return [{"runtime_id": r["runtime_id"], "model": r.get("model", ""),
                 "status": r.get("status", "UNKNOWN"), "mode": r.get("mode", "NORMAL"),
                 "family": r.get("family", ""), "local": r.get("local", False),
                 "qualified": r.get("qualified_roles") or []}
                for r in data.get("runtimes", [])]

    def cohort(self) -> dict:
        report = self.last_run() or {}
        return report.get("bindings") or {}

    # ---- work package detail -------------------------------------------

    def packet(self, wp_id: str) -> dict | None:
        """The frozen packet as DUM-E built it.

        Read from the evidence directory rather than rebuilt, because the packet
        under review is the one that was written when the work started — a
        packet regenerated now could differ from the one the reviewers judged
        against, and would look identical.
        """
        path = self.evidence / "live" / wp_id / f"{wp_id}.packet.json"
        if not path.is_file():
            path = self.evidence / wp_id / f"{wp_id}.packet.json"
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return None

    def sealed_sections(self, wp_id: str) -> list[dict]:
        """The frozen card, tests and acceptance, with their digests.

        Shown read-only and with the digest visible: a specification a reader
        could edit in the interface would stop being sealed, and a digest is how
        anyone checks that what they are reading is what was frozen.
        """
        packet = self.packet(wp_id)
        if not packet:
            return []
        return [{"name": s["name"], "path": s["path"],
                 "sha256": s.get("sha256", ""), "text": s.get("text", "")}
                for s in packet.get("sections", [])]

    def evidence_files(self, wp_id: str) -> list[dict]:
        """Every artefact recorded against this package, with its size.

        A zero-byte artefact is shown as zero rather than omitted: the harness
        refuses one as evidence, and hiding it here would remove the only signal
        that someone tried.
        """
        directory = self.evidence / "live" / wp_id
        if not directory.is_dir():
            directory = self.evidence / wp_id
        if not directory.is_dir():
            return []
        out = []
        for path in sorted(directory.iterdir()):
            if path.is_dir():
                continue
            size = path.stat().st_size
            out.append({"name": path.name, "bytes": size,
                        "empty": size == 0,
                        "kind": path.suffix.lstrip(".") or "file"})
        return out

    def gate(self, wp_id: str) -> dict | None:
        """The deterministic gate's own record, check by check."""
        report = self.last_run()
        if not report or report.get("wp_id") != wp_id:
            return None
        return report.get("gate")

    def history(self, wp_id: str) -> list[dict]:
        return [{"at": r["at"], "from": r["from_state"], "to": r["to_state"],
                 "actor": r["actor"], "reason": r["reason"] or ""}
                for r in self._rows(
                    "SELECT * FROM transition WHERE wp_id=? ORDER BY id", (wp_id,))]

    def findings(self, wp_id: str) -> list[dict]:
        return [{"severity": r["severity"], "summary": r["summary"],
                 "status": r["status"], "at": r["at"]}
                for r in self._rows(
                    "SELECT * FROM finding WHERE wp_id=? ORDER BY id DESC", (wp_id,))]

    # ---- activity -------------------------------------------------------

    def activity(self, limit: int = 40) -> list[dict]:
        """A semantic event stream, not a log dump.

        Built from transitions and the last run's steps — meaningful movements
        rather than every tool call, which the design system asks for explicitly.
        """
        events: list[dict] = []
        for row in self._rows(
                "SELECT * FROM transition ORDER BY id DESC LIMIT ?", (limit,)):
            events.append({
                "at": row["at"], "kind": "state",
                "tone": STATE_TONE.get(row["to_state"], "neutral"),
                "title": f"{row['wp_id']} → {row['to_state'].replace('_',' ').title()}",
                "detail": row["reason"] or "",
                "actor": row["actor"], "chips": [row["wp_id"]]})
        report = self.last_run()
        if report:
            for step in report.get("steps", []):
                tone = {"OK": "success", "FAILED": "failure",
                        "BLOCKED": "warning"}.get(step["outcome"], "neutral")
                events.append({
                    "at": step.get("at", ""), "kind": "run", "tone": tone,
                    "title": step["name"].replace("_", " ").title(),
                    "detail": step["detail"][:160], "actor": "run",
                    "chips": [report.get("wp_id", "")]})
        return sorted(events, key=lambda e: e["at"], reverse=True)[:limit]
