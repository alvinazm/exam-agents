from pathlib import Path

import pytest


@pytest.fixture
def sample_root(tmp_path: Path) -> Path:
    return tmp_path
