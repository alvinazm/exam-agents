from copy import deepcopy
from pathlib import Path


class MockHarnessRunner:
    def __init__(self, responses: dict[str, dict]):
        self.responses = deepcopy(responses)
        self.calls: list[tuple[dict, Path, Path]] = []

    def run(
        self,
        task: dict,
        workspace: Path,
        home: Path,
        timeout_seconds: int,
    ) -> dict:
        self.calls.append(
            (
                deepcopy(task),
                workspace.resolve(),
                home.resolve(),
            )
        )
        return deepcopy(self.responses[task["stage"]])
