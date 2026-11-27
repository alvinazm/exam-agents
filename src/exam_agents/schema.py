import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


class SchemaValidationError(ValueError):
    """A structured task, result, or manifest does not match its contract."""


SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"


def _validate(name: str, data: dict[str, Any]) -> None:
    schema = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(data),
        key=lambda error: list(error.path),
    )
    if errors:
        location = "/".join(str(part) for part in errors[0].path) or "<root>"
        raise SchemaValidationError(f"{location}: {errors[0].message}")


def validate_task(data: dict[str, Any]) -> None:
    _validate("task.schema.json", data)


def validate_result(data: dict[str, Any]) -> None:
    _validate("result.schema.json", data)


def validate_manifest(data: dict[str, Any]) -> None:
    _validate("manifest.schema.json", data)
