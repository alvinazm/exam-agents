import json
import os
from pathlib import Path

from .schema import SchemaValidationError, validate_result


class ResultSubmissionError(ValueError):
    """A result cannot be accepted for the referenced task."""


READ_ONLY_AGENTS = {"material-reviewer", "quality-reviewer"}


def _task_path(run_dir: Path, task_id: str) -> tuple[str, dict]:
    for path in (run_dir / "tasks").glob(f"*/{task_id}.json"):
        return path.parent.name, json.loads(path.read_text(encoding="utf-8"))
    raise ResultSubmissionError(f"unknown task: {task_id}")


def submit_result(run_dir: Path, expected_task_id: str, result: dict) -> dict:
    run_dir = run_dir.resolve()
    try:
        validate_result(result)
    except SchemaValidationError as exc:
        raise ResultSubmissionError(str(exc)) from exc
    if result["task_id"] != expected_task_id:
        raise ResultSubmissionError("result task_id does not match task")
    agent, task = _task_path(run_dir, expected_task_id)
    if task["task_id"] != result["task_id"]:
        raise ResultSubmissionError("result references a different task")
    if agent in READ_ONLY_AGENTS and result["artifacts_written"]:
        raise ResultSubmissionError(f"{agent} must not write artifacts")
    target = run_dir / "reports" / agent / f"{expected_task_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, target)
    return result
