import json

from exam_agents.cli import main


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
