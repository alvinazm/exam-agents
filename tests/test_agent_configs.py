import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_all_agents_have_prompt_and_config():
    expected = {
        "coordinator": "read-only",
        "author": "workspace-write",
        "material-reviewer": "read-only",
        "quality-reviewer": "read-only",
    }
    for agent, permission in expected.items():
        directory = ROOT / "agents" / agent
        assert (directory / "AGENT.md").is_file()
        config = json.loads(
            (directory / "config.json").read_text(encoding="utf-8")
        )
        assert config["permission_mode"] == permission
        assert config["profile"] == "sdk"


def test_control_scripts_exist():
    for name in (
        "init_run.py",
        "dispatch_stage.py",
        "freeze_inputs.py",
        "verify_hashes.py",
        "submit_result.py",
    ):
        assert (ROOT / "scripts" / name).is_file()


def test_quality_reviewer_owns_difficulty_and_ai_style_checks():
    prompt = (
        ROOT / "agents" / "quality-reviewer" / "AGENT.md"
    ).read_text(encoding="utf-8")

    assert "难度设计检查.md" in prompt
    assert "三模型" in prompt
    assert "audit_package_style.py" in prompt
    assert "AI 文风" in prompt
