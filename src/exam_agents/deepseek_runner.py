import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .schema import SchemaValidationError, validate_result


class HarnessConfigurationError(RuntimeError):
    pass


class InvalidAgentOutputError(ValueError):
    pass


@dataclass(frozen=True)
class DeepSeekConfig:
    provider: str = "deepseek-official"
    model: str = "deepseek-v4-flash"
    max_tokens: int = 49152
    profile: str = "sdk"
    patches: tuple[str, ...] = ()
    timeout_seconds: int = 1800
    permission_mode: str = "workspace-write"
    agents_home: str | None = "~/.codex"

    @classmethod
    def from_dict(cls, data: dict) -> "DeepSeekConfig":
        return cls(
            provider=data.get("provider", cls.provider),
            model=data.get("model", cls.model),
            max_tokens=data.get("max_tokens", cls.max_tokens),
            profile=data.get("profile", cls.profile),
            patches=tuple(data.get("patches", ())),
            timeout_seconds=data.get("timeout_seconds", cls.timeout_seconds),
            permission_mode=data.get("permission_mode", cls.permission_mode),
            agents_home=data.get("agents_home", cls.agents_home),
        )


def _default_sdk_factory(**kwargs):
    from deepseek_harness import DeepSeekHarness

    return DeepSeekHarness(**kwargs)


class DeepSeekRunner:
    def __init__(
        self,
        config: DeepSeekConfig,
        sdk_factory: Callable[..., object] | None = None,
        environ: dict[str, str] | None = None,
        agent_prompt: str = "",
    ):
        if config.profile == "sdk-minimal":
            raise HarnessConfigurationError(
                "sdk-minimal has no subagents and uses danger-full-access"
            )
        if config.permission_mode not in {
            "read-only",
            "workspace-write",
            "danger-full-access",
        }:
            raise HarnessConfigurationError("invalid permission mode")
        self.config = config
        self.sdk_factory = sdk_factory or _default_sdk_factory
        self.environ = environ if environ is not None else os.environ
        self.agent_prompt = agent_prompt

    def run(
        self,
        task: dict,
        workspace: Path,
        home: Path,
        timeout_seconds: int,
    ) -> dict:
        if not self.environ.get("DEEPSEEK_API_KEY"):
            raise HarnessConfigurationError("DEEPSEEK_API_KEY is required")
        sdk = self.sdk_factory(
            provider=self.config.provider,
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            cwd=str(workspace.resolve()),
            dsh_home=str(home.resolve()),
            profile=self.config.profile,
            patches=self.config.patches,
            env={
                "DSH_PERMISSION_MODE": self.config.permission_mode,
                "PYTHONDONTWRITEBYTECODE": "1",
                **(
                    {
                        "DSH_AGENTS_HOME": str(
                            Path(self.config.agents_home).expanduser().resolve()
                        )
                    }
                    if self.config.agents_home
                    else {}
                ),
            },
        )
        with sdk as harness:
            result = harness.run(
                (
                    f"{self.agent_prompt}\n\n"
                    "任务包如下，只返回符合 result-v1 的 JSON：\n"
                    f"{json.dumps(task, ensure_ascii=False)}"
                ).strip(),
                session_id=task["task_id"],
            )
        try:
            payload = json.loads(result.final_response)
            if not isinstance(payload, dict):
                raise InvalidAgentOutputError("agent response must be an object")
            validate_result(payload)
        except (json.JSONDecodeError, SchemaValidationError) as exc:
            raise InvalidAgentOutputError(str(exc)) from exc
        return payload
