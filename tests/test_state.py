import pytest

from exam_agents.state import Stage, TransitionError, transition


def test_cannot_skip_input_freeze():
    with pytest.raises(TransitionError):
        transition(Stage.INPUT_DRAFT, "output_started")


def test_happy_path_reaches_released():
    stage = Stage.INIT
    for event in (
        "design_started",
        "design_passed",
        "input_started",
        "input_review_started",
        "input_frozen",
        "output_started",
        "output_review_started",
        "output_passed",
        "human_review_started",
        "released",
    ):
        stage = transition(stage, event)
    assert stage == Stage.RELEASED


def test_changes_can_resume_input_work():
    assert (
        transition(Stage.CHANGES_REQUIRED, "input_resumed")
        == Stage.INPUT_DRAFT
    )
