import hashlib
import json
import os
from pathlib import Path

from .state import Stage


FIXED_INPUT_PATHS = [
    "input/**/*",
    "docs/reviews/1-题目说明.md",
    "docs/reviews/2-题目要求.md",
    "docs/reviews/难度设计检查.md",
    "docs/reviews/数据真实性设计检查.md",
]


def _files_for_patterns(root: Path, patterns: list[str]) -> list[Path]:
    files: set[Path] = set()
    for pattern in patterns:
        files.update(path for path in root.glob(pattern) if path.is_file())
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def hash_paths(root: Path, patterns: list[str]) -> dict[str, str]:
    result = {}
    for path in _files_for_patterns(root, patterns):
        result[path.relative_to(root).as_posix()] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    return result


def _tree_hash(hashes: dict[str, str]) -> str:
    payload = json.dumps(hashes, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def freeze_inputs(run_dir: Path, workspace: Path, manifest: dict) -> dict:
    workspace = workspace.resolve()
    run_dir = run_dir.resolve()
    hashes = hash_paths(workspace, FIXED_INPUT_PATHS)
    if not hashes:
        raise ValueError("no input files found to freeze")
    gate = {
        "question_id": manifest["question_id"],
        "status": "frozen",
        "base_commit": manifest["base_commit"],
        "patterns": FIXED_INPUT_PATHS,
        "hashes": hashes,
        "tree_hash": _tree_hash(hashes),
    }
    target = run_dir / "gates" / "input-freeze.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(gate, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, target)
    manifest["artifact_hashes"]["input-tree"] = gate["tree_hash"]
    return manifest


def verify_hashes(run_dir: Path, workspace: Path, manifest: dict) -> bool:
    gate_path = run_dir.resolve() / "gates" / "input-freeze.json"
    if not gate_path.is_file():
        return False
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    current = hash_paths(workspace.resolve(), gate["patterns"])
    return current == gate["hashes"]


def invalidate_if_changed(
    run_dir: Path,
    workspace: Path,
    manifest: dict,
) -> Stage:
    if verify_hashes(run_dir, workspace, manifest):
        return Stage(manifest["stage"])
    manifest["stage"] = Stage.INPUT_INVALIDATED.value
    manifest["active"] = False
    return Stage.INPUT_INVALIDATED
