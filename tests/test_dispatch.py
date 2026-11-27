import json

from exam_agents.dispatch import dispatch_stage
from exam_agents.run_store import RunStore


def test_dispatch_writes_complete_task(tmp_path):
    runs = tmp_path / "runs"
    RunStore(runs).create("q1", tmp_path / "project", "a" * 40)
    run_dir = runs / "q1"

    task_path = dispatch_stage(
        run_dir,
        agent="author",
        stage="design",
        instructions="Create the design.",
        required_files=["docs/reviews/难度设计检查.md"],
    )
    task = json.loads(task_path.read_text(encoding="utf-8"))

    assert task_path.parent.name == "author"
    assert task["question_id"] == "q1"
    assert task["base_commit"] == "a" * 40
    assert task["required_files"] == ["docs/reviews/难度设计检查.md"]
