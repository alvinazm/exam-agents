import json

from exam_agents.freeze import (
    freeze_inputs,
    hash_paths,
    invalidate_if_changed,
    verify_hashes,
)
from exam_agents.state import Stage


def prepare(tmp_path):
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "runs" / "q1"
    (workspace / "input").mkdir(parents=True)
    (workspace / "docs" / "reviews").mkdir(parents=True)
    run_dir.mkdir(parents=True)
    (workspace / "input" / "a.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    for name in (
        "1-题目说明.md",
        "2-题目要求.md",
        "难度设计检查.md",
        "数据真实性设计检查.md",
    ):
        (workspace / "docs" / "reviews" / name).write_text(
            name,
            encoding="utf-8",
        )
    manifest = {
        "question_id": "q1",
        "project_root": str(workspace),
        "stage": Stage.INPUT_REVIEW.value,
        "base_commit": "abc",
        "artifact_hashes": {},
        "reviews": {},
        "approvals": {},
        "repair_rounds": 0,
        "active": True,
    }
    return workspace, run_dir, manifest


def test_hash_changes_when_file_changes(tmp_path):
    workspace, _, _ = prepare(tmp_path)
    first = hash_paths(workspace, ["input/**/*"])
    (workspace / "input" / "a.csv").write_text("changed\n", encoding="utf-8")
    second = hash_paths(workspace, ["input/**/*"])

    assert first != second


def test_freeze_and_verify(tmp_path):
    workspace, run_dir, manifest = prepare(tmp_path)
    frozen = freeze_inputs(run_dir, workspace, manifest)

    assert verify_hashes(run_dir, workspace, frozen) is True
    gate = json.loads(
        (run_dir / "gates" / "input-freeze.json").read_text(encoding="utf-8")
    )
    assert gate["status"] == "frozen"


def test_modified_input_is_detected_and_invalidated(tmp_path):
    workspace, run_dir, manifest = prepare(tmp_path)
    frozen = freeze_inputs(run_dir, workspace, manifest)
    frozen["stage"] = Stage.INPUT_FROZEN.value
    (workspace / "input" / "a.csv").write_text("changed\n", encoding="utf-8")

    assert verify_hashes(run_dir, workspace, frozen) is False
    assert invalidate_if_changed(run_dir, workspace, frozen) == Stage.INPUT_INVALIDATED
