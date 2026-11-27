from exam_agents.env import load_env_file


def test_load_env_file_sets_missing_values(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text(
        "DEEPSEEK_API_KEY=local-secret\n# ignored\nDEEPSEEK_BASE_URL=\"http://api\"\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    environ = {}

    load_env_file(path, environ)

    assert environ["DEEPSEEK_API_KEY"] == "local-secret"
    assert environ["DEEPSEEK_BASE_URL"] == "http://api"


def test_existing_environment_wins(tmp_path):
    path = tmp_path / ".env"
    path.write_text("DEEPSEEK_API_KEY=file-value\n", encoding="utf-8")
    environ = {"DEEPSEEK_API_KEY": "process-value"}

    load_env_file(path, environ)

    assert environ["DEEPSEEK_API_KEY"] == "process-value"
