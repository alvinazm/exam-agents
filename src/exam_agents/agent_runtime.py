import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .deepseek_runner import DeepSeekConfig, DeepSeekRunner


AGENT_NAMES = (
    "coordinator",
    "author",
    "material-reviewer",
    "quality-reviewer",
)


@dataclass(frozen=True)
class AgentSpec:
    name: str
    config_path: Path
    config: DeepSeekConfig
    prompt_text: str

    @property
    def permission_mode(self) -> str:
        return self.config.permission_mode


def load_agent_specs(agents_dir: Path) -> dict[str, AgentSpec]:
    specs = {}
    for name in AGENT_NAMES:
        directory = (agents_dir / name).resolve()
        config_path = directory / "config.json"
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        prompt_name = raw.pop("prompt")
        prompt_path = directory / prompt_name
        specs[name] = AgentSpec(
            name=name,
            config_path=config_path,
            config=DeepSeekConfig.from_dict(raw),
            prompt_text=prompt_path.read_text(encoding="utf-8"),
        )
    return specs


def build_deepseek_runners(
    specs: dict[str, AgentSpec],
    sdk_factory: Callable[..., object] | None = None,
    environ: dict[str, str] | None = None,
) -> dict[str, DeepSeekRunner]:
    return {
        name: DeepSeekRunner(
            spec.config,
            sdk_factory=sdk_factory,
            environ=environ,
            agent_prompt=spec.prompt_text,
        )
        for name, spec in specs.items()
    }
