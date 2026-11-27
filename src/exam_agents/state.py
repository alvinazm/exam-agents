from enum import Enum


class Stage(str, Enum):
    INIT = "INIT"
    DESIGN_DRAFT = "DESIGN_DRAFT"
    DESIGN_PASSED = "DESIGN_PASSED"
    INPUT_DRAFT = "INPUT_DRAFT"
    INPUT_REVIEW = "INPUT_REVIEW"
    INPUT_FROZEN = "INPUT_FROZEN"
    OUTPUT_DRAFT = "OUTPUT_DRAFT"
    OUTPUT_REVIEW = "OUTPUT_REVIEW"
    OUTPUT_PASSED = "OUTPUT_PASSED"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    RELEASED = "RELEASED"
    CHANGES_REQUIRED = "CHANGES_REQUIRED"
    BLOCKED = "BLOCKED"
    INPUT_INVALIDATED = "INPUT_INVALIDATED"
    CONFLICT = "CONFLICT"
    HUMAN_DECISION_REQUIRED = "HUMAN_DECISION_REQUIRED"


class TransitionError(ValueError):
    """The requested state transition is not allowed."""


MAIN_PATH = {
    (Stage.INIT, "design_started"): Stage.DESIGN_DRAFT,
    (Stage.DESIGN_DRAFT, "design_passed"): Stage.DESIGN_PASSED,
    (Stage.DESIGN_PASSED, "input_started"): Stage.INPUT_DRAFT,
    (Stage.INPUT_DRAFT, "input_review_started"): Stage.INPUT_REVIEW,
    (Stage.INPUT_REVIEW, "input_frozen"): Stage.INPUT_FROZEN,
    (Stage.INPUT_FROZEN, "output_started"): Stage.OUTPUT_DRAFT,
    (Stage.OUTPUT_DRAFT, "output_review_started"): Stage.OUTPUT_REVIEW,
    (Stage.OUTPUT_REVIEW, "output_passed"): Stage.OUTPUT_PASSED,
    (Stage.OUTPUT_PASSED, "human_review_started"): Stage.HUMAN_REVIEW,
    (Stage.HUMAN_REVIEW, "released"): Stage.RELEASED,
    (Stage.CHANGES_REQUIRED, "input_resumed"): Stage.INPUT_DRAFT,
    (Stage.CHANGES_REQUIRED, "output_resumed"): Stage.OUTPUT_DRAFT,
}

TERMINAL_STAGES = {
    Stage.RELEASED,
    Stage.BLOCKED,
    Stage.INPUT_INVALIDATED,
}


def transition(current: Stage, event: str) -> Stage:
    if (current, event) in MAIN_PATH:
        return MAIN_PATH[(current, event)]
    if current in TERMINAL_STAGES:
        raise TransitionError(f"cannot transition from terminal stage {current.value}")
    exceptions = {
        "changes_requested": Stage.CHANGES_REQUIRED,
        "blocked": Stage.BLOCKED,
        "input_invalidated": Stage.INPUT_INVALIDATED,
        "conflict": Stage.CONFLICT,
        "human_decision_required": Stage.HUMAN_DECISION_REQUIRED,
    }
    if event in exceptions:
        return exceptions[event]
    raise TransitionError(
        f"event {event!r} is not allowed from stage {current.value}"
    )
