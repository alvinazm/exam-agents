import json

import pytest

from exam_agents.run_store import RunStore


def test_create_and_load_manifest(tmp_path):
    store = RunStore(tmp_path / "runs")
    manifest = store.create("q1", tmp_path / "project", "abc")

    assert manifest["question_id"] == "q1"
    assert store.load("q1") == manifest
    assert (tmp_path / "runs" / "q1" / "tasks").is_dir()
    assert (tmp_path / "runs" / "q1" / "reports").is_dir()


def test_only_one_active_question(tmp_path):
    store = RunStore(tmp_path / "runs")
    store.create("q1", tmp_path / "q1", "abc")

    with pytest.raises(RuntimeError):
        store.create("q2", tmp_path / "q2", "def")


def test_save_is_valid_and_atomic(tmp_path):
    store = RunStore(tmp_path / "runs")
    manifest = store.create("q1", tmp_path / "q1", "abc")
    manifest["repair_rounds"] = 2

    store.save(manifest)

    assert store.load("q1")["repair_rounds"] == 2
    assert json.loads(
        (tmp_path / "runs" / "q1" / "manifest.json").read_text(encoding="utf-8")
    )["repair_rounds"] == 2
