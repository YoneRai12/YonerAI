from pathlib import Path


WORKFLOW = Path(".github/workflows/pr-intake-gate.yml")


def test_pr_intake_gate_triggers_on_pr_reviews_and_comments() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "pull_request_target:" in workflow
    assert "- opened" in workflow
    assert "- reopened" in workflow
    assert "- synchronize" in workflow
    assert "pull_request_review:" in workflow
    assert "pull_request_review_comment:" in workflow
    assert "issue_comment:" in workflow
    assert "review-intake-required" in workflow


def test_pr_intake_gate_requires_maintainer_controlled_label() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'const needs = "needs-intake";' in workflow
    assert 'const reviewed = "intake-reviewed";' in workflow
    assert "materialPrActions.has(action)" in workflow
    assert "await removeLabel(reviewed);" in workflow
    assert "reopened" in workflow
    assert "ready_for_review" in workflow
    assert "core.setFailed(" in workflow


def test_pr_intake_gate_invalidates_reviewed_label_on_new_review_or_comment() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    review_block = (
        'if (eventName === "pull_request_review" || eventName === "pull_request_review_comment" || eventName === "issue_comment") {\n'
        "              await addLabel(needs);\n"
        "              await removeLabel(reviewed);\n"
        "            }"
    )
    assert review_block in workflow


def test_pr_intake_gate_does_not_execute_pr_code_or_merge() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8").lower()

    assert "actions/checkout" not in workflow
    assert "gh pr merge" not in workflow
    assert "auto-merge" not in workflow
    assert "pull_request_target" in workflow
    assert "github.event.issue.pull_request" in workflow

def test_pr_intake_gate_ignores_closed_or_merged_pr_activity() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "github.rest.pulls.get" in workflow
    assert 'prState.state !== "open" || prState.merged_at' in workflow
    assert "Ignoring review intake for closed or merged PR." in workflow

def test_pr_intake_gate_marks_missing_intake_without_stale_failed_runs() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "const intakeMessage =" in workflow
    assert "core.warning(intakeMessage);" in workflow
    assert "Add the maintainer-controlled" in workflow
