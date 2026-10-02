import json

from typesafe_sdk import Choice, Noul, Score

from src.constants import Urgency
from src.schemas import TICKET_CLASSIFICATION_SCHEMA
from src.ticket_classifier import normalize_urgency_value

DEPARTMENT_LABELS = ["billing", "technical", "account", "general"]

URGENCY_LEVELS = [
    "Low - no immediate action required.",
    "Medium - should be handled soon.",
    "High - requires prompt attention.",
    "Critical - requires immediate attention.",
]


class TestSchemaShape:
    def test_contains_expected_questions(self):
        assert set(TICKET_CLASSIFICATION_SCHEMA) == {
            "department",
            "urgency",
            "refund_requested",
        }

    def test_department_is_choice(self):
        assert isinstance(TICKET_CLASSIFICATION_SCHEMA["department"], Choice)

    def test_urgency_is_score(self):
        assert isinstance(TICKET_CLASSIFICATION_SCHEMA["urgency"], Score)

    def test_refund_requested_is_noul(self):
        assert isinstance(TICKET_CLASSIFICATION_SCHEMA["refund_requested"], Noul)

    def test_questions_have_instructions(self):
        for question in TICKET_CLASSIFICATION_SCHEMA.values():
            assert question.instructions
            assert isinstance(question.instructions, str)

    def test_questions_serialize_to_json(self):
        payload = {
            name: question.model_dump()
            for name, question in TICKET_CLASSIFICATION_SCHEMA.items()
        }
        assert json.loads(json.dumps(payload)) == payload


class TestDepartmentQuestion:
    def test_type_discriminator(self):
        dumped = TICKET_CLASSIFICATION_SCHEMA["department"].model_dump()
        assert dumped["type"] == "choice"

    def test_labels(self):
        criteria = TICKET_CLASSIFICATION_SCHEMA["department"].criteria
        assert list(criteria) == DEPARTMENT_LABELS

    def test_label_descriptions(self):
        # sourcery skip: no-loop-in-tests
        for description in TICKET_CLASSIFICATION_SCHEMA["department"].criteria.values():
            assert description
            assert isinstance(description, str)


class TestUrgencyQuestion:
    def test_type_discriminator(self):
        dumped = TICKET_CLASSIFICATION_SCHEMA["urgency"].model_dump()
        assert dumped["type"] == "score"

    def test_levels_are_ordered_low_to_critical(self):
        criteria = TICKET_CLASSIFICATION_SCHEMA["urgency"].criteria
        assert criteria == URGENCY_LEVELS

    def test_levels_normalize_to_urgency_members(self):
        criteria = TICKET_CLASSIFICATION_SCHEMA["urgency"].criteria
        assert [normalize_urgency_value(level) for level in criteria] == [
            Urgency.LOW,
            Urgency.MEDIUM,
            Urgency.HIGH,
            Urgency.CRITICAL,
        ]


class TestRefundQuestion:
    def test_type_discriminator(self):
        dumped = TICKET_CLASSIFICATION_SCHEMA["refund_requested"].model_dump()
        assert dumped["type"] == "noul"

    def test_no_criteria(self):
        dumped = TICKET_CLASSIFICATION_SCHEMA["refund_requested"].model_dump()
        assert "criteria" not in dumped
