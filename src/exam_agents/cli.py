import argparse
import json
from pathlib import Path

from .dispatch import dispatch_stage
from .freeze import freeze_inputs, verify_hashes
from .run_store import RunStore
from .submit import submit_result
from .agent_runtime import build_deepseek_runners, load_agent_specs
from .env import load_env_file
from .workflow import release_run, run_real_workflow


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="exam-agents")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init-run")
    init.add_argument("--runs-root", type=Path, required=True)
    init.add_argument("--question-id", required=True)
    init.add_argument("--project-root", type=Path, required=True)
    init.add_argument("--base-commit", required=True)

    status = sub.add_parser("status")
    status.add_argument("--runs-root", type=Path, required=True)
    status.add_argument("--question-id", required=True)

    dispatch = sub.add_parser("dispatch-stage")
    dispatch.add_argument("--run-dir", type=Path, required=True)
    dispatch.add_argument("--agent", required=True)
    dispatch.add_argument("--stage", required=True)
    dispatch.add_argument("--instructions", required=True)
    dispatch.add_argument("--required-file", action="append", default=[])

    submit = sub.add_parser("submit-result")
    submit.add_argument("--run-dir", type=Path, required=True)
    submit.add_argument("--expected-task-id", required=True)
    submit.add_argument("--result-file", type=Path, required=True)

    freeze = sub.add_parser("freeze-inputs")
    freeze.add_argument("--runs-root", type=Path, required=True)
    freeze.add_argument("--question-id", required=True)
    freeze.add_argument("--workspace", type=Path, required=True)

    verify = sub.add_parser("verify-hashes")
    verify.add_argument("--runs-root", type=Path, required=True)
    verify.add_argument("--question-id", required=True)
    verify.add_argument("--workspace", type=Path, required=True)

    real = sub.add_parser("run-real-workflow")
    real.add_argument("--project-root", type=Path, required=True)
    real.add_argument("--runs-root", type=Path, required=True)
    real.add_argument("--question-id", required=True)
    real.add_argument("--agents-dir", type=Path, required=True)
    real.add_argument("--approve-input", action="store_true")
    real.add_argument("--env-file", type=Path, default=Path(".env"))

    release = sub.add_parser("release-run")
    release.add_argument("--project-root", type=Path, required=True)
    release.add_argument("--runs-root", type=Path, required=True)
    release.add_argument("--question-id", required=True)
    release.add_argument("--approve", action="store_true")
    return parser


def _execute(args: argparse.Namespace) -> dict:
    if args.command == "init-run":
        return RunStore(args.runs_root).create(
            args.question_id,
            args.project_root,
            args.base_commit,
        )
    if args.command == "status":
        return RunStore(args.runs_root).load(args.question_id)
    if args.command == "dispatch-stage":
        path = dispatch_stage(
            args.run_dir,
            agent=args.agent,
            stage=args.stage,
            instructions=args.instructions,
            required_files=args.required_file,
        )
        return {"task_file": str(path)}
    if args.command == "submit-result":
        result = json.loads(args.result_file.read_text(encoding="utf-8"))
        return submit_result(args.run_dir, args.expected_task_id, result)
    if args.command == "freeze-inputs":
        store = RunStore(args.runs_root)
        manifest = store.load(args.question_id)
        manifest = freeze_inputs(
            args.runs_root / args.question_id,
            args.workspace,
            manifest,
        )
        store.save(manifest)
        return manifest
    if args.command == "verify-hashes":
        store = RunStore(args.runs_root)
        manifest = store.load(args.question_id)
        valid = verify_hashes(
            args.runs_root / args.question_id,
            args.workspace,
            manifest,
        )
        return {"valid": valid}
    if args.command == "run-real-workflow":
        load_env_file(args.env_file)
        specs = load_agent_specs(args.agents_dir)
        runners = build_deepseek_runners(specs)
        return run_real_workflow(
            args.project_root,
            args.runs_root,
            args.question_id,
            runners,
            args.approve_input,
        )
    if args.command == "release-run":
        return release_run(
            args.project_root,
            args.runs_root,
            args.question_id,
            args.approve,
        )
    raise ValueError(f"unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        _emit(_execute(args))
    except Exception as exc:
        _emit({"status": "error", "error": str(exc)})
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
