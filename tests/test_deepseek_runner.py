import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from exam_agents.deepseek_runner import (
    DeepSeekConfig,
    DeepSeekRunner,
    HarnessConfigurationError,
    InvalidAgentOutputError,
)


TASK = {"task_id": "task-1", "stage": "design"}


def valid_result_payload():
    return {
        "task_id": "task-1",
        "status": "passed",
        "checked_items": [],
        "findings": [],
        "commands_run": [],
        "artifacts_written": [],
        "output_hashes": {},
    }


class FakeHarness:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls = []
        self.__class__.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def run(self, prompt, session_id):
        self.calls.append((prompt, session_id))
        return SimpleNamespace(
            final_response=json.dumps(valid_result_payload())
        )


def config():
    return DeepSeekConfig(
        provider="deepseek-official",
        model="deepseek-v4-flash",
        max_tokens=49152,
        profile="sdk",
        patches=(),
        timeout_seconds=30,
    )


def test_uses_workspace_home_and_sdk_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret")
    FakeHarness.instances.clear()
    runner = DeepSeekRunner(config(), sdk_factory=FakeHarness)

    runner.run(TASK, tmp_path / "work", tmp_path / "home", 30)

    instance = FakeHarness.instances[0]
    assert instance.kwargs["cwd"] == str((tmp_path / "work").resolve())
    assert instance.kwargs["dsh_home"] == str((tmp_path / "home").resolve())
    assert instance.kwargs["profile"] == "sdk"
    assert instance.kwargs["env"]["DSH_PERMISSION_MODE"] == "workspace-write"
    assert instance.kwargs["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
    assert instance.kwargs["env"]["DSH_AGENTS_HOME"] == str(
        Path.home() / ".codex"
    )
    prompt = instance.calls[0][0]
    assert '"title": "Exam Agent Result"' in prompt
    assert '"findings"' in prompt
    assert '"required"' in prompt


def test_requires_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    runner = DeepSeekRunner(config(), sdk_factory=FakeHarness)

    with pytest.raises(HarnessConfigurationError):
        runner.run(TASK, tmp_path / "work", tmp_path / "home", 30)


def test_rejects_non_object_json(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret")

    class BadHarness(FakeHarness):
        def run(self, prompt, session_id):
            self.calls.append((prompt, session_id))
            return SimpleNamespace(final_response="[]")

    BadHarness.instances = []
    runner = DeepSeekRunner(config(), sdk_factory=BadHarness)

    with pytest.raises(InvalidAgentOutputError):
        runner.run(TASK, tmp_path / "work", tmp_path / "home", 30)
    assert len(BadHarness.instances[0].calls) == 2


def test_retries_invalid_json_once(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret")

    class RepairingHarness(FakeHarness):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.responses = ["not-json", json.dumps(valid_result_payload())]

        def run(self, prompt, session_id):
            self.calls.append((prompt, session_id))
            return SimpleNamespace(final_response=self.responses.pop(0))

    RepairingHarness.instances = []
    runner = DeepSeekRunner(config(), sdk_factory=RepairingHarness)
    result = runner.run(TASK, tmp_path / "work", tmp_path / "home", 30)

    assert result == valid_result_payload()
    calls = RepairingHarness.instances[0].calls
    assert len(calls) == 2
    assert "上一次输出" in calls[1][0]
