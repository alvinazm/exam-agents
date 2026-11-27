from pathlib import Path
from typing import Protocol


class HarnessRunner(Protocol):
    def run(
        self,
        task: dict,
        workspace: Path,
        home: Path,
        timeout_seconds: int,
    ) -> dict: ...
