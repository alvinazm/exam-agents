import pytest

from exam_agents.mock_harness import MockHarnessRunner


TASK = {"stage": "design", "task_id": "task-1"}
RESULT = {
    "task_id": "task-1",
    "status": "passed",
    "checked_items": [],
    "findings": [],
    "commands_run": [],
    "artifacts_written": [],
    "output_hashes": {},
}


def test_mock_returns_stage_result(tmp_path):
    runner = MockHarnessRunner({"design": RESULT})

    assert runner.run(TASK, tmp_path, tmp_path / "home", 10) == RESULT
    assert runner.calls == [(TASK, tmp_path.resolve(), (tmp_path / "home").resolve())]


def test_mock_returns_copy(tmp_path):
    runner = MockHarnessRunner({"design": RESULT})
    result = runner.run(TASK, tmp_path, tmp_path / "home", 10)
    result["status"] = "blocked"

    assert runner.responses["design"]["status"] == "passed"


def test_mock_rejects_unknown_stage(tmp_path):
    runner = MockHarnessRunner({})

    with pytest.raises(KeyError):
        runner.run(TASK, tmp_path, tmp_path / "home", 10)
