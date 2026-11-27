import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from .dispatch import dispatch_stage
from .freeze import freeze_inputs, verify_hashes
from .gitops import GitRepo
from .run_store import RunStore
from .state import Stage, transition
from .submit import submit_result


class WorkflowError(RuntimeError):
    pass


def _has_blocking_findings(result: dict) -> bool:
    return result["status"] != "passed" or any(
        finding["severity"] in {"high", "medium"}
        for finding in result["findings"]
    )


def _execute_task(
    run_dir: Path,
    runner,
    agent: str,
    stage: str,
    instructions: str,
    workspace: Path,
    required_files: list[str] | None = None,
) -> dict:
    task_path = dispatch_stage(
        run_dir,
        agent=agent,
        stage=stage,
        instructions=instructions,
        required_files=required_files or [],
    )
    task = json.loads(task_path.read_text(encoding="utf-8"))
    home = run_dir / "homes" / agent
    home.mkdir(parents=True, exist_ok=True)
    result = runner.run(task, workspace, home, 1800)
    result = dict(result)
    result["task_id"] = task["task_id"]
    return submit_result(run_dir, task["task_id"], result)


def _advance(
    store: RunStore,
    manifest: dict,
    event: str,
) -> dict:
    manifest["stage"] = transition(
        Stage(manifest["stage"]),
        event,
    ).value
    store.save(manifest)
    return manifest


def _record_reviews(
    manifest: dict,
    material: dict,
    quality: dict,
) -> None:
    manifest["reviews"]["material-reviewer"] = material
    manifest["reviews"]["quality-reviewer"] = quality


def _run_review_round(
    run_dir: Path,
    runner,
    workspaces: dict[str, Path],
) -> tuple[dict, dict]:
    jobs = (
        ("material-reviewer", "Evaluate materials.", "material_review"),
        ("quality-reviewer", "Evaluate exam quality.", "quality_review"),
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(
                _execute_task,
                run_dir,
                runner,
                agent,
                stage,
                instructions,
                workspaces[agent],
            ): agent
            for agent, instructions, stage in jobs
        }
        results = {
            futures[future]: future.result() for future in futures
        }
    return results["material-reviewer"], results["quality-reviewer"]


def _blocked_or_changed(
    store: RunStore,
    manifest: dict,
    results: tuple[dict, dict],
) -> dict | None:
    if any(result["status"] == "blocked" for result in results):
        return _advance(store, manifest, "blocked")
    if any(_has_blocking_findings(result) for result in results):
        manifest["repair_rounds"] += 1
        manifest["stage"] = transition(
            Stage(manifest["stage"]),
            "changes_requested",
        ).value
        store.save(manifest)
        return manifest
    return None


def _create_author_worktree(
    project: Path,
    run_dir: Path,
    question_id: str,
) -> Path:
    repo = GitRepo(project)
    return repo.create_worktree(
        f"exam/{question_id}/author",
        run_dir / "worktrees" / "author",
    )


def _refresh_review_worktrees(
    project: Path,
    run_dir: Path,
    question_id: str,
    commit: str,
) -> dict[str, Path]:
    repo = GitRepo(project)
    paths = {
        "material-reviewer": run_dir / "worktrees" / "material-review",
        "quality-reviewer": run_dir / "worktrees" / "quality-review",
    }
    for path in paths.values():
        if path.exists():
            repo.remove_worktree(path)
    suffix = f"{commit[:8]}-{uuid4().hex[:6]}"
    repo.create_worktree(
        f"exam/{question_id}/material-review-{suffix}",
        paths["material-reviewer"],
        commit,
    )
    repo.create_worktree(
        f"exam/{question_id}/quality-review-{suffix}",
        paths["quality-reviewer"],
        commit,
    )
    return paths


def _commit_author_draft(
    store: RunStore,
    manifest: dict,
    author: Path,
    label: str,
) -> str:
    commit = GitRepo(author).commit_all(f"draft: {manifest['question_id']} {label}")
    manifest["base_commit"] = commit
    store.save(manifest)
    return commit


def run_mock_workflow(
    project_root: Path,
    runs_root: Path,
    question_id: str,
    runner,
    approve_input: bool,
) -> dict:
    project_root = project_root.resolve()
    store = RunStore(runs_root)
    manifest = store.create(
        question_id,
        project_root,
        GitRepo(project_root).head(),
    )
    run_dir = runs_root.resolve() / question_id
    author = _create_author_worktree(
        project_root,
        run_dir,
        question_id,
    )
    _advance(store, manifest, "design_started")
    design = _execute_task(
        run_dir,
        runner,
        "author",
        "design",
        "Create the difficulty and realism designs.",
        author,
    )
    if _has_blocking_findings(design):
        manifest["repair_rounds"] += 1
        manifest["stage"] = Stage.CHANGES_REQUIRED.value
        store.save(manifest)
        return manifest
    design_commit = _commit_author_draft(store, manifest, author, "design")
    _advance(store, manifest, "design_passed")
    _advance(store, manifest, "input_started")
    input_result = _execute_task(
        run_dir,
        runner,
        "author",
        "input",
        "Create input, Query, and task brief.",
        author,
    )
    if _has_blocking_findings(input_result):
        manifest["repair_rounds"] += 1
        manifest["stage"] = Stage.CHANGES_REQUIRED.value
        store.save(manifest)
        return manifest
    input_commit = _commit_author_draft(store, manifest, author, "input")
    _advance(store, manifest, "input_review_started")
    review_workspaces = _refresh_review_worktrees(
        project_root,
        run_dir,
        question_id,
        input_commit,
    )
    reviews = _run_review_round(run_dir, runner, review_workspaces)
    _record_reviews(manifest, *reviews)
    changed = _blocked_or_changed(store, manifest, reviews)
    if changed:
        return changed
    if not approve_input:
        store.save(manifest)
        return manifest
    manifest["approvals"]["input_frozen"] = True
    manifest = freeze_inputs(run_dir, author, manifest)
    repo = GitRepo(project_root)
    repo.tag(f"exam/{question_id}/input-frozen", input_commit)
    _advance(store, manifest, "input_frozen")
    _advance(store, manifest, "output_started")
    output = _execute_task(
        run_dir,
        runner,
        "author",
        "output_build",
        "Create answer, Rubrics, and output audit.",
        author,
    )
    if _has_blocking_findings(output):
        manifest["repair_rounds"] += 1
        manifest["stage"] = Stage.CHANGES_REQUIRED.value
        store.save(manifest)
        return manifest
    output_commit = _commit_author_draft(store, manifest, author, "output")
    _advance(store, manifest, "output_review_started")
    review_workspaces = _refresh_review_worktrees(
        project_root,
        run_dir,
        question_id,
        output_commit,
    )
    reviews = _run_review_round(run_dir, runner, review_workspaces)
    _record_reviews(manifest, *reviews)
    changed = _blocked_or_changed(store, manifest, reviews)
    if changed:
        return changed
    _advance(store, manifest, "output_passed")
    return _advance(store, manifest, "human_review_started")


def release_run(
    project_root: Path,
    runs_root: Path,
    question_id: str,
    approved: bool,
) -> dict:
    if not approved:
        raise WorkflowError("final release requires explicit human approval")
    store = RunStore(runs_root)
    manifest = store.load(question_id)
    run_dir = runs_root.resolve() / question_id
    author = run_dir / "worktrees" / "author"
    if not verify_hashes(run_dir, author, manifest):
        manifest["stage"] = Stage.INPUT_INVALIDATED.value
        manifest["active"] = False
        store.save(manifest)
        raise WorkflowError("frozen inputs changed before release")
    if Stage(manifest["stage"]) != Stage.HUMAN_REVIEW:
        raise WorkflowError("run is not ready for release")
    manifest["approvals"]["final_release"] = True
    manifest["stage"] = transition(
        Stage.HUMAN_REVIEW,
        "released",
    ).value
    manifest["active"] = False
    store.save(manifest)
    GitRepo(project_root).tag(
        f"exam/{question_id}/released",
        manifest["base_commit"],
    )
    return manifest
