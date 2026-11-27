import subprocess
from pathlib import Path

import pytest

from exam_agents.gitops import GitOperationError, GitRepo


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def make_repo(path: Path) -> Path:
    path.mkdir()
    git(path, "init", "-b", "main")
    git(path, "config", "user.name", "test")
    git(path, "config", "user.email", "test@example.com")
    (path / "a.txt").write_text("base\n", encoding="utf-8")
    git(path, "add", "a.txt")
    git(path, "commit", "-m", "base")
    return path


def test_creates_two_isolated_worktrees(tmp_path):
    repo = GitRepo(make_repo(tmp_path / "repo"))
    author = repo.create_worktree("author", tmp_path / "author")
    reviewer = repo.create_worktree("reviewer", tmp_path / "reviewer")

    (author / "a.txt").write_text("author\n", encoding="utf-8")
    commit = GitRepo(author).commit_all("draft")

    assert len(commit) == 40
    assert (author / "a.txt").read_text(encoding="utf-8") == "author\n"
    assert (reviewer / "a.txt").read_text(encoding="utf-8") == "base\n"


def test_tag_and_ff_merge(tmp_path):
    repo = GitRepo(make_repo(tmp_path / "repo"))
    worktree = repo.create_worktree("feature", tmp_path / "feature")
    (worktree / "b.txt").write_text("feature\n", encoding="utf-8")
    commit = GitRepo(worktree).commit_all("feature")
    repo.tag("frozen", commit)
    repo.checkout_main()
    repo.merge_ff_only("frozen")

    assert (repo.root / "b.txt").read_text(encoding="utf-8") == "feature\n"


def test_merge_rejects_non_fast_forward(tmp_path):
    repo = GitRepo(make_repo(tmp_path / "repo"))
    worktree = repo.create_worktree("feature", tmp_path / "feature")
    (worktree / "feature.txt").write_text("feature\n", encoding="utf-8")
    GitRepo(worktree).commit_all("feature")
    repo.checkout_main()
    (repo.root / "main.txt").write_text("main\n", encoding="utf-8")
    repo.commit_all("main change")

    with pytest.raises(GitOperationError):
        repo.merge_ff_only("feature")
