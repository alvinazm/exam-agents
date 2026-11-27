import json

from exam_agents.cli import main
import exam_agents.cli as cli


def test_init_run_and_status(tmp_path, capsys):
    runs = tmp_path / "runs"
    project = tmp_path / "project"
    project.mkdir()

    code = main(
        [
            "init-run",
            "--runs-root",
            str(runs),
            "--question-id",
            "q1",
            "--project-root",
            str(project),
            "--base-commit",
            "abc",
        ]
    )
    assert code == 0
    assert json.loads(capsys.readouterr().out)["question_id"] == "q1"

    code = main(
        [
            "status",
            "--runs-root",
            str(runs),
            "--question-id",
            "q1",
        ]
    )
    assert code == 0
    assert json.loads(capsys.readouterr().out)["stage"] == "INIT"


def test_duplicate_active_question_returns_error(tmp_path, capsys):
    runs = tmp_path / "runs"
    project = tmp_path / "project"
    project.mkdir()
    args = [
        "init-run",
        "--runs-root",
        str(runs),
        "--question-id",
        "q1",
        "--project-root",
        str(project),
        "--base-commit",
        "abc",
    ]
    assert main(args) == 0
    capsys.readouterr()

    assert main(args) != 0
    payload = json.loads(capsys.readouterr().out)
    assert "already active" in payload["error"]


def test_run_real_workflow_command(tmp_path, capsys, monkeypatch):
    captured = {}

    def fake_run(project_root, runs_root, question_id, runners, approve_input):
        captured.update(
            {
                "project_root": project_root,
                "runs_root": runs_root,
                "question_id": question_id,
                "runners": runners,
                "approve_input": approve_input,
            }
        )
        return {"question_id": question_id, "stage": "HUMAN_REVIEW"}

    monkeypatch.setattr(cli, "run_real_workflow", fake_run)
    monkeypatch.setattr(
        cli,
        "build_deepseek_runners",
        lambda specs: {name: name for name in specs},
    )
    monkeypatch.setattr(
        cli,
        "load_agent_specs",
        lambda path: {
            "coordinator": object(),
            "author": object(),
            "material-reviewer": object(),
            "quality-reviewer": object(),
        },
    )

    code = main(
        [
            "run-real-workflow",
            "--project-root",
            str(tmp_path / "project"),
            "--runs-root",
            str(tmp_path / "runs"),
            "--question-id",
            "q1",
            "--agents-dir",
            str(tmp_path / "agents"),
            "--approve-input",
        ]
    )

    assert code == 0
    assert captured["question_id"] == "q1"
    assert captured["approve_input"] is True
    assert json.loads(capsys.readouterr().out)["stage"] == "HUMAN_REVIEW"


def test_release_run_command_requires_explicit_approval(tmp_path, capsys, monkeypatch):
    captured = {}

    def fake_release(project_root, runs_root, question_id, approved):
        captured.update(
            {
                "project_root": project_root,
                "runs_root": runs_root,
                "question_id": question_id,
                "approved": approved,
            }
        )
        return {"question_id": question_id, "stage": "RELEASED"}

    monkeypatch.setattr(cli, "release_run", fake_release)
    code = main(
        [
            "release-run",
            "--project-root",
            str(tmp_path / "project"),
            "--runs-root",
            str(tmp_path / "runs"),
            "--question-id",
            "q1",
            "--approve",
        ]
    )

    assert code == 0
    assert captured["approved"] is True
    assert json.loads(capsys.readouterr().out)["stage"] == "RELEASED"
