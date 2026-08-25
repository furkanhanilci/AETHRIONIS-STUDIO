"""AETHRIONIS Studio: the shell, the cards, and what the UI may never do."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, "/home/otonom/Desktop/FH/DUM-E")

from studio.app import Studio
from studio.features.collaboration import cards
from studio.features.shell import render as R
from studio.shared.gateway.dume import STATE_TO_BEAD, DumeGateway, WorkPackage


# ---- the frozen product decision ---------------------------------------

def test_dume_is_an_item_in_the_primary_rail_not_a_separate_application():
    """The design freeze: DUM-E is the first System Workspace inside Studio."""
    keys = [k for k, _, _ in R.PRIMARY if k]
    assert "dume" in keys
    assert keys[0] == "home"


def test_the_primary_rail_stays_small():
    """Literature, Evidence, Claims and Experiments belong to a workspace, not
    to global navigation."""
    keys = {k for k, _, _ in R.PRIMARY if k}
    assert len(keys) <= 9
    for forbidden in ("literature", "evidence", "claims", "experiments",
                      "reviews", "publications"):
        assert forbidden not in keys


def test_dume_selection_uses_the_cyan_workspace_accent():
    html = R.primary_rail("dume")
    assert 'class="active dume"' in html


def test_the_shell_renders_without_an_inspector():
    """The inspector must be closable and not required to finish the work."""
    page = R.page(section="home", context="", main="<main></main>")
    assert "no-inspector" in page


# ---- status is never colour alone --------------------------------------

def test_a_message_type_is_spelled_out_as_well_as_coloured():
    html = R.message(who="a", when="1", text="x", message_type="CHALLENGE")
    assert "CHALLENGE" in html


def test_a_stage_bead_carries_a_written_label():
    html = cards.wp_card(wp_id="WP-001", title="t", bead=1,
                         stage_label="Executing", next_stage="Spec Review")
    for label in cards.STAGE_RAIL:
        assert label in html
    assert "Executing" in html


def test_a_verification_card_shows_the_exit_code_not_only_a_colour():
    html = cards.verification_card({"candidate": "a" * 40, "exit": "0",
                                    "summary": "18 passed"})
    assert "exit" in html.lower() and ">0<" in html.replace(" ", "")


# ---- the thirteenth frozen principle -----------------------------------

def test_no_card_can_be_built_from_prose():
    """`no UI text can turn a chat message into ACCEPTED / VERIFIED /
    MERGE_ELIGIBLE authority`. Every card takes a record, never a string."""
    import inspect
    for name in ("candidate_card", "review_card", "verification_card"):
        signature = inspect.signature(getattr(cards, name))
        parameters = list(signature.parameters.values())
        assert len(parameters) == 1
        assert parameters[0].name == "record"


def test_the_composer_says_a_message_creates_nothing():
    studio = Studio()
    html = studio.dume_channel("control")
    assert "Nothing said here creates a review" in html


# ---- stale evidence -----------------------------------------------------

def test_evidence_from_another_candidate_is_marked_superseded():
    """A green result from an older candidate presented as current is the
    substitution the harness refuses; an interface that hides it undoes the
    refusal where it matters most."""
    html = cards.candidate_card({
        "candidate": "aaaaaaaaaaaa", "current_candidate": "bbbbbbbbbbbb",
        "stale": True, "verdict": "MERGE_ELIGIBLE"})
    assert "superseded" in html
    assert "not evidence for this one" in html


def test_matching_evidence_is_not_marked():
    html = cards.candidate_card({
        "candidate": "aaaaaaaaaaaa", "current_candidate": "aaaaaaaaaaaa",
        "stale": False, "verdict": "MERGE_ELIGIBLE"})
    assert "superseded" not in html


def test_the_gateway_detects_the_mismatch():
    gateway = DumeGateway()
    if not gateway.available():
        pytest.skip("no DUM-E state store")
    package = gateway.current()
    if package is None or not package.candidate:
        pytest.skip("no candidate recorded")
    card = gateway.candidate_card(package.wp_id, package.candidate)
    if card:
        assert card["stale"] == (not card["candidate"].startswith(
            package.candidate[:12]))


# ---- the gateway reads and never writes --------------------------------

def test_the_gateway_opens_the_state_store_read_only():
    """Studio renders DUM-E's records and must not be able to change one by
    accident, however convenient that would be."""
    import inspect
    source = inspect.getsource(DumeGateway._rows)
    assert "mode=ro" in source


def test_a_stage_is_read_from_the_lifecycle_not_computed():
    """The Studio invariant forbids inferring a stage from a percentage."""
    assert set(STATE_TO_BEAD) >= {"EXECUTING", "VERIFYING", "TECH_COMPLETE"}
    package = WorkPackage("WP-001", "t", "EXECUTING", 1, None, None)
    assert package.bead() == STATE_TO_BEAD["EXECUTING"]


def test_an_absent_value_is_reported_rather_than_invented(tmp_path):
    gateway = DumeGateway(db=tmp_path / "missing.db", evidence=tmp_path)
    assert not gateway.available()
    assert gateway.current() is None
    assert gateway.work_packages() == []
    assert gateway.last_run() is None


# ---- the supplied assets are used, not regenerated ----------------------

@pytest.mark.parametrize("asset", [
    "aethrion_master_logo_transparent.png", "dume_master_logo_transparent.png",
    "aethrion_appmark_64.png", "dume_workspace_mark_64.png"])
def test_the_approved_brand_assets_are_present(asset):
    assert (ROOT / "assets" / "logos" / asset).is_file()


def test_the_tokens_come_from_the_handoff_reference():
    tokens = (ROOT / "studio" / "shared" / "styles" / "tokens.css").read_text()
    for token in ("--aethrionis-red: #EF2E35", "--dume-cyan: #28DDEB",
                  "--bg-0: #070A0E"):
        assert token in tokens


# ---- work package detail ------------------------------------------------

def test_the_sealed_specification_is_shown_beside_its_digest():
    """A specification a reader could edit here would stop being sealed, and a
    digest is how anyone checks that what they are reading is what was frozen."""
    from studio.features.dume import detail
    html = detail.sealed_specification([
        {"name": "card", "path": "/x/WP-001.md", "sha256": "a" * 64, "text": "AC-01"}])
    assert "aaaaaaaaaaaa" in html
    assert "read-only" in html


def test_an_empty_artefact_is_listed_rather_than_omitted():
    """The harness refuses a zero-byte artefact as evidence; hiding it here
    would remove the only signal that someone tried."""
    from studio.features.dume import detail
    html = detail.evidence_list([{"name": "report.json", "bytes": 0,
                                  "empty": True, "kind": "json"}])
    assert "report.json" in html
    assert "refused as evidence" in html


def test_the_gate_shows_every_check_with_the_question_it_answers():
    """A verdict without its checks is a claim, and this page exists so it is
    not one."""
    from studio.features.dume import detail
    html = detail.gate_record({
        "verdict": "MERGE_ELIGIBLE", "candidate_revision": "a" * 40,
        "checks": [{"name": "candidate_unchanged",
                    "question": "Is this the exact candidate that was reviewed?",
                    "passed": True, "detail": "matches"}]})
    assert "Is this the exact candidate that was reviewed?" in html
    assert "candidate_unchanged" in html
    # The note wraps in the source, so compare on normalised whitespace.
    assert "No model is reachable from the gate" in " ".join(html.split())


def test_an_unevaluated_gate_says_so_rather_than_showing_nothing():
    from studio.features.dume import detail
    assert "has not been evaluated" in detail.gate_record(None)


# ---- home ---------------------------------------------------------------

def test_home_summarises_real_objects_and_invents_no_metric():
    """The design system: Home should summarise actual flows, not invent KPI
    widgets."""
    studio = Studio()
    html = studio.home()
    for invented in ("velocity", "throughput", "score", "%", "KPI"):
        assert invented.lower() not in html.lower() or invented == "%"


def test_home_repeats_that_availability_is_not_eligibility():
    assert "Availability is not eligibility" in Studio().home()


# ---- research shell -----------------------------------------------------

def test_the_research_surfaces_admit_they_are_not_built():
    html = Studio().research()
    assert html.count("not built") >= 4


# ---- visual QA ----------------------------------------------------------

def test_every_surface_is_covered_by_the_screenshot_set():
    import scripts_visual_qa as qa
    names = {n for n, _, _ in qa.SURFACES}
    assert {"home", "dume-control", "wp-gate", "agents", "models",
            "activity", "research"} <= names
    # narrow widths are where the inspector and context rail fall away
    assert any(size[0] < 1000 for _, _, size in qa.SURFACES)


def test_the_accessibility_check_catches_a_colour_only_status():
    import scripts_visual_qa as qa
    problems = qa.accessibility(
        '<html><title>x</title><h1>x</h1>'
        '<nav aria-label="Primary"></nav>'
        '<span class="pill" style="--c:red"></span></html>', "surface")
    assert any("colour but no text" in p for p in problems)


def test_the_accessibility_check_catches_a_missing_alt():
    import scripts_visual_qa as qa
    problems = qa.accessibility(
        '<html><title>x</title><h1>x</h1><nav aria-label="Primary"></nav>'
        '<img src="a.png"></html>', "surface")
    assert any("no alt attribute" in p for p in problems)


def test_the_gateway_returns_the_keys_the_panel_reads():
    """The client asked for `revision`, `producer`, `red_exit`; the gateway
    returns `candidate`, `discipline`, `tests`. Every field name was wrong.

    A missing key in TypeScript is `undefined`, which the panel rendered as an
    em dash — the same thing it shows when DUM-E genuinely recorded nothing. A
    blank that means two different things is worse than an error, and nothing
    in either language could catch it: the types were declarations, not
    observations.

    This asserts against the gateway's real output. It is the only place the
    two languages meet.
    """
    from studio.shared.gateway.dume import DumeGateway

    gateway = DumeGateway()
    package = gateway.current()
    if package is None:
        pytest.skip("no package has started; nothing to shape-check")

    candidate = gateway.candidate_card(package.wp_id, package.candidate)
    if candidate:
        for key in ("candidate", "stale", "worktree", "files", "tests",
                    "discipline"):
            assert key in candidate, f"panel reads candidate.{key}"

    for review in gateway.review_records(package.wp_id):
        for key in ("kind", "verdict", "reason", "findings"):
            assert key in review, f"panel reads review.{key}"

    verification = gateway.verification(package.wp_id)
    if verification:
        for key in ("candidate", "exit", "summary", "fresh_checkout"):
            assert key in verification, f"panel reads verification.{key}"

    gate = gateway.gate(package.wp_id)
    if gate:
        for key in ("verdict", "evaluated_at", "checks"):
            assert key in gate, f"panel reads gate.{key}"
        for check in gate["checks"]:
            for key in ("name", "question", "passed", "detail"):
                assert key in check, f"panel reads gate.checks[].{key}"

    for artefact in gateway.evidence_files(package.wp_id):
        for key in ("name", "bytes", "empty", "kind"):
            assert key in artefact, f"panel reads evidence[].{key}"

    for step in gateway.history(package.wp_id):
        for key in ("at", "from", "to", "actor", "reason"):
            assert key in step, f"panel reads history[].{key}"
