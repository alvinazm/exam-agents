import pytest

from exam_agents.schema import (
    SchemaValidationError,
    validate_manifest,
    validate_result,
    validate_task,
)


def task_payload():
    return {
        "task_id": "task-design-1",
        "question_id": "q1",
        "stage": "design",
        "base_commit": "a" * 40,
        "skill_ref": "rubrics-growth-exam@abc",
        "input_manifest_hash": "hash",
        "required_files": [],
        "instructions": "Create the design.",
        "output_schema": "result-v1",
    }


def result_payload():
    return {
        "task_id": "task-design-1",
        "status": "passed",
        "checked_items": ["design"],
        "findings": [],
        "commands_run": [],
        "artifacts_written": [],
        "output_hashes": {},
    }


def manifest_payload():
    return {
        "question_id": "q1",
        "project_root": "/tmp/q1",
        "stage": "INIT",
        "base_commit": "a" * 40,
        "artifact_hashes": {},
        "reviews": {},
        "approvals": {},
        "repair_rounds": 0,
        "active": True,
    }


def test_valid_contracts_are_accepted():
    validate_task(task_payload())
    validate_result(result_payload())
    validate_manifest(manifest_payload())


def test_rejects_unknown_result_status():
    payload = result_payload()
    payload["status"] = "probably_ok"

    with pytest.raises(SchemaValidationError):
        validate_result(payload)


def test_rejects_unknown_finding_classification():
    payload = result_payload()
    payload["findings"] = [
        {
            "id": "F-1",
            "severity": "high",
            "classification": "guess",
            "file": "input/a.csv",
            "field": "amount",
            "evidence": "conflict",
            "required_action": "repair",
        }
    ]

    with pytest.raises(SchemaValidationError):
        validate_result(payload)


def test_rejects_missing_task_field():
    payload = task_payload()
    del payload["instructions"]

    with pytest.raises(SchemaValidationError):
        validate_task(payload)


def test_rejects_missing_manifest_field():
    payload = manifest_payload()
    del payload["artifact_hashes"]

    with pytest.raises(SchemaValidationError):
        validate_manifest(payload)
