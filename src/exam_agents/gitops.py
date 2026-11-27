import os
import subprocess
from pathlib import Path


class GitOperationError(RuntimeError):
    """A controlled Git operation failed."""


class GitRepo:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def _run(self, *args: str, check: bool = True) -> str:
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        result = subprocess.run(
            ["git", *args],
            cwd=self.root,
            env=env,
            text=True,
            capture_output=True,
        )
        if check and result.returncode:
            raise GitOperationError(
                f"git {args[0] if args else ''} failed: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        return result.stdout.strip()

    def head(self) -> str:
        return self._run("rev-parse", "HEAD")

    def commit_all(self, message: str) -> str:
        self._run("add", "-A")
        status = self._run("status", "--porcelain")
        if status:
            self._run("commit", "-m", message)
        return self.head()

    def create_worktree(
        self,
        name: str,
        target: Path,
        ref: str = "HEAD",
    ) -> Path:
        target = target.resolve()
        self._run("worktree", "add", "-b", name, str(target), ref)
        return target

    def remove_worktree(self, target: Path) -> None:
        self._run("worktree", "remove", str(target.resolve()))

    def tag(self, name: str, ref: str) -> None:
        self._run("tag", name, ref)

    def checkout_main(self) -> None:
        self._run("checkout", "main")

    def merge_ff_only(self, ref: str) -> None:
        self._run("merge", "--ff-only", ref)

    def push(self, remote: str, branch: str = "main") -> None:
        self._run("push", remote, f"HEAD:{branch}")
