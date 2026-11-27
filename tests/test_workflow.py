import json
import subprocess
from pathlib import Path

import pytest

from exam_agents.mock_harness import MockHarnessRunner
from exam_agents.workflow import (
    WorkflowError,
    release_run,
    run_mock_workflow,
    run_real_workflow,
)


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def make_project(path: Path) -> Path:
    path.mkdir()
    git(path, "init", "-b", "main")
    git(path, "config", "user.name", "test")
    git(path, "config", "user.email", "test@example.com")
    (path / "input").mkdir()
    (path / "input" / "a.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    reviews = path / "docs" / "reviews"
    reviews.mkdir(parents=True)
    for name in (
        "1-题目说明.md",
        "2-题目要求.md",
        "难度设计检查.md",
        "数据真实性设计检查.md",
    ):
        (reviews / name).write_text(name, encoding="utf-8")
    git(path, "add", "-A")
    git(path, "commit", "-m", "base")
    return path


def result(task_id="placeholder", status="passed", findings=None):
    return {
        "task_id": task_id,
        "status": status,
        "checked_items": ["checked"],
        "findings": findings or [],
        "commands_run": [],
        "artifacts_written": [],
        "output_hashes": {},
    }


def responses(review_status="passed"):
    return {
        "coordinator_check": result(),
        "design": result(),
        "input": result(),
        "material_review": result(
            status=review_status,
            findings=(
                [
                    {
                        "id": "F-1",
                        "severity": "high",
                        "classification": "material_defect",
                        "file": "input/a.csv",
                        "field": "a",
                        "evidence": "bad",
                        "required_action": "repair",
                    }
                ]
                if review_status == "changes_required"
                else []
            ),
        ),
        "quality_review": result(status=review_status),
        "output_build": result(),
    }


def test_success_path_reaches_human_review_then_releases(tmp_path):
    project = make_project(tmp_path / "project")
    runs = tmp_path / "runs"
    manifest = run_mock_workflow(
        project,
        runs,
        "q1",
        MockHarnessRunner(responses()),
        approve_input=True,
    )

    assert manifest["stage"] == "HUMAN_REVIEW"
    with pytest.raises(WorkflowError):
        release_run(project, runs, "q1", approved=False)
    released = release_run(project, runs, "q1", approved=True)
    assert released["stage"] == "RELEASED"


def test_material_high_finding_requires_changes(tmp_path):
    project = make_project(tmp_path / "project")
    runs = tmp_path / "runs"
    manifest = run_mock_workflow(
        project,
        runs,
        "q1",
        MockHarnessRunner(responses("changes_required")),
        approve_input=True,
    )

    assert manifest["stage"] == "CHANGES_REQUIRED"
    assert manifest["repair_rounds"] == 1
    assert not (runs / "q1" / "gates" / "input-freeze.json").exists()


def test_input_freeze_waits_for_approval(tmp_path):
    project = make_project(tmp_path / "project")
    runs = tmp_path / "runs"
    manifest = run_mock_workflow(
        project,
        runs,
        "q1",
        MockHarnessRunner(responses()),
        approve_input=False,
    )

    assert manifest["stage"] == "INPUT_REVIEW"
    assert not (runs / "q1" / "gates" / "input-freeze.json").exists()


def test_release_detects_changed_frozen_input(tmp_path):
    project = make_project(tmp_path / "project")
    runs = tmp_path / "runs"
    run_mock_workflow(
        project,
        runs,
        "q1",
        MockHarnessRunner(responses()),
        approve_input=True,
    )
    author_input = runs / "q1" / "worktrees" / "author" / "input" / "a.csv"
    author_input.write_text("changed\n", encoding="utf-8")

    with pytest.raises(WorkflowError, match="frozen inputs changed"):
        release_run(project, runs, "q1", approved=True)

    manifest = json.loads(
        (runs / "q1" / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["stage"] == "INPUT_INVALIDATED"
    assert manifest["active"] is False


def test_reviewers_see_latest_author_draft(tmp_path):
    class WritingRunner(MockHarnessRunner):
        def run(self, task, workspace, home, timeout_seconds):
            result = super().run(task, workspace, home, timeout_seconds)
            if task["stage"] == "input" and workspace.name == "author":
                (workspace / "input" / "new.txt").write_text(
                    "new\n",
                    encoding="utf-8",
                )
            return result

    project = make_project(tmp_path / "project")
    runs = tmp_path / "runs"
    run_mock_workflow(
        project,
        runs,
        "q1",
        WritingRunner(responses()),
        approve_input=True,
    )

    assert (runs / "q1" / "worktrees" / "material-review" / "input" / "new.txt").is_file()
    assert (runs / "q1" / "worktrees" / "quality-review" / "input" / "new.txt").is_file()


def test_real_workflow_uses_agent_specific_runners(tmp_path):
    project = make_project(tmp_path / "project")
    runs = tmp_path / "runs"
    used = []

    class NamedRunner(MockHarnessRunner):
        def __init__(self, name):
            super().__init__(responses())
            self.name = name

        def run(self, task, workspace, home, timeout_seconds):
            used.append((self.name, task["stage"], workspace.name))
            return super().run(task, workspace, home, timeout_seconds)

    runners = {
        name: NamedRunner(name)
        for name in (
            "coordinator",
            "author",
            "material-reviewer",
            "quality-reviewer",
        )
    }
    manifest = run_real_workflow(
        project,
        runs,
        "q1",
        runners,
        approve_input=True,
    )

    assert manifest["stage"] == "HUMAN_REVIEW"
    assert ("coordinator", "coordinator_check", "project") in used
    assert ("author", "design", "author") in used
    assert ("material-reviewer", "material_review", "material-review") in used
    assert ("quality-reviewer", "quality_review", "quality-review") in used
