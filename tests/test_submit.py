import json

import pytest

from exam_agents.dispatch import dispatch_stage
from exam_agents.run_store import RunStore
from exam_agents.submit import ResultSubmissionError, submit_result


def make_result(task_id: str, *, status: str = "passed", written=None):
    return {
        "task_id": task_id,
        "status": status,
        "checked_items": ["design"],
        "findings": [],
        "commands_run": [],
        "artifacts_written": written or [],
        "output_hashes": {},
    }


def setup_task(tmp_path, agent="author"):
    runs = tmp_path / "runs"
    RunStore(runs).create("q1", tmp_path / "project", "a" * 40)
    run_dir = runs / "q1"
    task_path = dispatch_stage(
        run_dir,
        agent=agent,
        stage="design",
        instructions="Create the design.",
        required_files=[],
    )
    return run_dir, json.loads(task_path.read_text(encoding="utf-8"))


def test_submit_persists_valid_result(tmp_path):
    run_dir, task = setup_task(tmp_path)
    result = submit_result(run_dir, task["task_id"], make_result(task["task_id"]))

    saved = json.loads(
        (run_dir / "reports" / "author" / f"{task['task_id']}.json").read_text(
            encoding="utf-8"
        )
    )
    assert result == saved


def test_rejects_task_id_mismatch(tmp_path):
    run_dir, task = setup_task(tmp_path)

    with pytest.raises(ResultSubmissionError):
        submit_result(run_dir, task["task_id"], make_result("other-task"))


def test_rejects_reviewer_writes(tmp_path):
    run_dir, task = setup_task(tmp_path, agent="material-reviewer")

    with pytest.raises(ResultSubmissionError):
        submit_result(
            run_dir,
            task["task_id"],
            make_result(task["task_id"], written=["input/a.csv"]),
        )
