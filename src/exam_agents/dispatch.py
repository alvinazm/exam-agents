import json
import os
from pathlib import Path
from uuid import uuid4

from .schema import validate_task


AGENTS = {
    "coordinator",
    "author",
    "material-reviewer",
    "quality-reviewer",
}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def dispatch_stage(
    run_dir: Path,
    agent: str,
    stage: str,
    instructions: str,
    required_files: list[str],
) -> Path:
    if agent not in AGENTS:
        raise ValueError(f"unknown agent: {agent}")
    run_dir = run_dir.resolve()
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    input_hash = manifest.get("artifact_hashes", {}).get("input-tree", "")
    task = {
        "task_id": f"task-{stage}-{uuid4().hex[:12]}",
        "question_id": manifest["question_id"],
        "stage": stage,
        "base_commit": manifest["base_commit"],
        "skill_ref": "rubrics-growth-exam@current",
        "input_manifest_hash": input_hash,
        "required_files": required_files,
        "instructions": instructions,
        "output_schema": "result-v1",
    }
    validate_task(task)
    path = run_dir / "tasks" / agent / f"{task['task_id']}.json"
    _write_json(path, task)
    return path
