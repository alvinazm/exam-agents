from pathlib import Path

from exam_agents.agent_runtime import build_deepseek_runners, load_agent_specs


ROOT = Path(__file__).resolve().parents[1]


def test_loads_all_agent_prompts_and_permissions():
    specs = load_agent_specs(ROOT / "agents")

    assert set(specs) == {
        "coordinator",
        "author",
        "material-reviewer",
        "quality-reviewer",
    }
    assert specs["author"].permission_mode == "workspace-write"
    assert specs["material-reviewer"].permission_mode == "read-only"
    assert "出题主笔" in specs["author"].prompt_text


def test_builds_independent_runner_per_agent():
    specs = load_agent_specs(ROOT / "agents")
    runners = build_deepseek_runners(
        specs,
        sdk_factory=lambda **kwargs: None,
        environ={"DEEPSEEK_API_KEY": "secret"},
    )

    assert set(runners) == set(specs)
    assert runners["author"].config.permission_mode == "workspace-write"
    assert runners["quality-reviewer"].config.permission_mode == "read-only"
    assert "考试质量审查 Agent" in runners["quality-reviewer"].agent_prompt
