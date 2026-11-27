import fcntl
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .schema import validate_manifest
from .state import Stage


class RunStore:
    """Owns run manifests and the single-active-question lock."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._active_file = self.root / ".active"

    @contextmanager
    def _lock(self) -> Iterator[None]:
        lock_path = self.root / ".active.lock"
        with lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _run_dir(self, question_id: str) -> Path:
        return self.root / question_id

    def create(
        self,
        question_id: str,
        project_root: Path,
        base_commit: str,
    ) -> dict:
        with self._lock():
            if self._active_file.exists():
                active = self._active_file.read_text(encoding="utf-8").strip()
                raise RuntimeError(f"question {active} is already active")
            run_dir = self._run_dir(question_id)
            run_dir.mkdir(parents=True, exist_ok=False)
            for name in ("tasks", "reports", "gates", "logs", "homes", "worktrees"):
                (run_dir / name).mkdir()
            manifest = {
                "question_id": question_id,
                "project_root": str(project_root.resolve()),
                "stage": Stage.INIT.value,
                "base_commit": base_commit,
                "artifact_hashes": {},
                "reviews": {},
                "approvals": {},
                "repair_rounds": 0,
                "active": True,
            }
            validate_manifest(manifest)
            self._write_manifest(run_dir, manifest)
            self._active_file.write_text(question_id + "\n", encoding="utf-8")
            return manifest

    def load(self, question_id: str) -> dict:
        path = self._run_dir(question_id) / "manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        validate_manifest(data)
        return data

    def save(self, manifest: dict) -> None:
        validate_manifest(manifest)
        run_dir = self._run_dir(manifest["question_id"])
        if not run_dir.is_dir():
            raise FileNotFoundError(run_dir)
        with self._lock():
            self._write_manifest(run_dir, manifest)
            if not manifest["active"]:
                self._active_file.unlink(missing_ok=True)

    def active_question(self) -> str | None:
        if not self._active_file.exists():
            return None
        return self._active_file.read_text(encoding="utf-8").strip() or None

    @staticmethod
    def _write_manifest(run_dir: Path, manifest: dict) -> None:
        target = run_dir / "manifest.json"
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, target)
