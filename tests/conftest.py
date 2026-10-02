import logging
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from typesafe_sdk import ChoiceAnswer, NoulAnswer, ScoreAnswer

from src.models import TicketResponse

CLASSIFIER_LOGGER = "TICKET CLASSIFIER"

DEPARTMENT_CHOICES = ("billing", "technical", "account", "general")

DEFAULT_LEGEND = {
    0: "Low - no immediate action required.",
    1: "Medium - should be handled soon.",
    2: "High - requires prompt attention.",
    3: "Critical - requires immediate attention.",
}


@pytest.fixture
def legend():
    return dict(DEFAULT_LEGEND)


@pytest.fixture
def make_choice_answer():
    def _make(choice="billing", confidence=0.95, probabilities=None):
        if probabilities is None:
            probabilities = {choice: confidence}
        return ChoiceAnswer(
            type="choice",
            choice=choice,
            confidence=confidence,
            probabilities=probabilities,
        )

    return _make


@pytest.fixture
def make_score_answer():
    def _make(score=2.0, confidence=0.9, legend=None):
        answer_legend = dict(DEFAULT_LEGEND) if legend is None else dict(legend)
        probabilities = {key: (1.0 if key == 0 else 0.0) for key in answer_legend}
        return ScoreAnswer(
            type="score",
            score=score,
            confidence=confidence,
            legend=answer_legend,  # type: ignore
            probabilities=probabilities,
        )

    return _make


@pytest.fixture
def make_noul_answer():
    def _make(noul=0.95):
        return NoulAnswer(type="noul", noul=noul)

    return _make


@pytest.fixture
def make_ticket_response(make_choice_answer, make_score_answer, make_noul_answer):
    def _make(department=None, urgency=None, refund_requested=None):
        return TicketResponse(
            department=(department if department is not None else make_choice_answer()),
            urgency=urgency if urgency is not None else make_score_answer(),
            refund_requested=(
                refund_requested if refund_requested is not None else make_noul_answer()
            ),
        )

    return _make


@pytest.fixture
def ticket_response(make_ticket_response):
    return make_ticket_response()


@pytest.fixture
def answers(legend):
    """Raw (post-parse) answer payload shaped like a system one response body."""
    return {
        "department": {
            "type": "choice",
            "choice": "billing",
            "confidence": 0.93,
            "probabilities": {"billing": 0.93, "general": 0.07},
        },
        "urgency": {
            "type": "score",
            "score": 2.4,
            "confidence": 0.88,
            "legend": legend,
            "probabilities": {0: 0.0, 1: 0.1, 2: 0.8, 3: 0.1},
        },
        "refund_requested": {"type": "noul", "noul": 0.93},
    }


@pytest.fixture
def mock_type_safe_client():
    """Patch the TypeSafeClient used inside src.ticket_classifier."""
    with patch("src.ticket_classifier.TypeSafeClient") as client_cls:
        yield client_cls


@pytest.fixture
def wire_client(mock_type_safe_client):
    """Configure the mocked client to return the given answers payload."""

    def _wire(answers):
        client = mock_type_safe_client.return_value.__enter__.return_value
        client.system_one.return_value = SimpleNamespace(answers=answers)
        return mock_type_safe_client

    return _wire


@pytest.fixture
def classifier_logs(caplog):
    """Collect log messages emitted by the TICKET CLASSIFIER logger."""
    caplog.set_level(logging.DEBUG, logger=CLASSIFIER_LOGGER)

    def _collect(level=logging.WARNING):
        return [
            record.getMessage()
            for record in caplog.records
            if record.name == CLASSIFIER_LOGGER and record.levelno == level
        ]

    return _collect
