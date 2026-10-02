import pytest
from pydantic import ValidationError
from typesafe_sdk import ChoiceAnswer, NoulAnswer, ScoreAnswer

from src.constants import (
    CONFIDENCE_THRESHOLD,
    NOUL_UNCERTAINTY_HIGH,
    NOUL_UNCERTAINTY_LOW,
    Urgency,
)
from src.models import Ticket, TicketEvaluation, TicketResponse


class TestConstants:
    def test_confidence_threshold(self):
        assert CONFIDENCE_THRESHOLD == pytest.approx(0.67)

    def test_noul_uncertainty_bounds(self):
        assert NOUL_UNCERTAINTY_LOW == pytest.approx(0.2)
        assert NOUL_UNCERTAINTY_HIGH == pytest.approx(0.8)
        assert NOUL_UNCERTAINTY_LOW < NOUL_UNCERTAINTY_HIGH


class TestUrgency:
    def test_is_str_enum(self):
        assert isinstance(Urgency.LOW, str)

    def test_members_and_values(self):
        assert [u.value for u in Urgency] == ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    def test_member_count(self):
        assert len(Urgency) == 4

    def test_equality_with_strings(self):
        assert Urgency.LOW == "LOW"
        assert Urgency.MEDIUM == "MEDIUM"
        assert Urgency.HIGH == "HIGH"
        assert Urgency.CRITICAL == "CRITICAL"

    def test_lookup_by_value(self):
        assert Urgency("MEDIUM") is Urgency.MEDIUM

    def test_lookup_by_invalid_value_raises(self):
        with pytest.raises(ValueError):
            Urgency("URGENT")

    def test_str_returns_value(self):
        assert str(Urgency.HIGH) == "HIGH"
        assert f"{Urgency.CRITICAL}" == "CRITICAL"


class TestTicket:
    def test_valid_ticket(self):  # sourcery skip: class-extract-method
        ticket = Ticket(subject="Can't log in", body="It says invalid password.")
        assert ticket.subject == "Can't log in"
        assert ticket.body == "It says invalid password."

    def test_missing_body_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            Ticket(subject="Hi")  # type: ignore
        assert exc_info.value.errors()[0]["type"] == "missing"

    def test_missing_subject_raises(self):
        with pytest.raises(ValidationError):
            Ticket(body="Hi")  # type: ignore

    def test_empty_fields_are_allowed(self):
        ticket = Ticket(subject="", body="")
        assert ticket.subject == ""
        assert ticket.body == ""

    def test_non_string_subject_raises(self):
        with pytest.raises(ValidationError):
            Ticket(subject=42, body="Hi")  # type: ignore

    def test_extra_fields_are_ignored(self):
        ticket = Ticket(subject="a", body="b", priority="high")  # type: ignore
        assert ticket.subject == "a"
        assert not hasattr(ticket, "priority")

    def test_model_dump_round_trip(self):
        ticket = Ticket(subject="a", body="b")
        assert Ticket.model_validate(ticket.model_dump()) == ticket


class TestTicketResponse:
    def test_valid_response_from_dicts(self, answers):
        response = TicketResponse.model_validate(answers)
        assert isinstance(response.department, ChoiceAnswer)
        assert isinstance(response.urgency, ScoreAnswer)
        assert isinstance(response.refund_requested, NoulAnswer)
        assert response.department.choice == "billing"
        assert response.urgency.score == pytest.approx(2.4)
        assert response.refund_requested.noul == pytest.approx(0.93)

    def test_missing_field_raises(self, answers):
        del answers["urgency"]
        with pytest.raises(ValidationError):
            TicketResponse.model_validate(answers)

    def test_missing_answer_field_raises(self, answers):
        del answers["department"]["choice"]
        with pytest.raises(ValidationError):
            TicketResponse.model_validate(answers)

    def test_wrong_answer_type_raises(self, answers):
        answers["department"]["type"] = "noul"
        with pytest.raises(ValidationError):
            TicketResponse.model_validate(answers)

    def test_invalid_confidence_type_raises(self, answers):
        answers["department"]["confidence"] = "very sure"
        with pytest.raises(ValidationError):
            TicketResponse.model_validate(answers)

    def test_extra_fields_are_ignored(self, answers):
        answers["unexpected"] = "value"
        answers["department"]["unexpected"] = 1
        response = TicketResponse.model_validate(answers)
        assert response.department.choice == "billing"

    def test_string_legend_keys_rejected_in_strict_mode(self, answers):
        answers["urgency"]["legend"] = {"0": "Low", "1": "High"}
        with pytest.raises(ValidationError):
            TicketResponse.model_validate(answers)

    def test_model_dump_round_trip(self, answers):
        response = TicketResponse.model_validate(answers)
        assert TicketResponse.model_validate(response.model_dump()) == response


class TestTicketEvaluation:
    def test_valid_evaluation(self):
        evaluation = TicketEvaluation(
            department="Billing",
            urgency=Urgency.HIGH,
            refund_requested=True,
        )
        assert evaluation.department == "Billing"
        assert evaluation.urgency is Urgency.HIGH
        assert evaluation.refund_requested is True

    def test_urgency_coerced_from_string(self):
        evaluation = TicketEvaluation(
            department="General",
            urgency="LOW",  # type: ignore
            refund_requested=False,
        )
        assert evaluation.urgency is Urgency.LOW

    def test_invalid_urgency_raises(self):
        with pytest.raises(ValidationError):
            TicketEvaluation(
                department="General",
                urgency="URGENT",  # type: ignore
                refund_requested=False,
            )

    def test_missing_field_raises(self):
        with pytest.raises(ValidationError):
            TicketEvaluation(department="General", urgency=Urgency.LOW)  # type: ignore

    def test_invalid_bool_raises(self):
        with pytest.raises(ValidationError):
            TicketEvaluation(
                department="General",
                urgency=Urgency.LOW,
                refund_requested="sometimes",  # type: ignore
            )

    def test_extra_fields_ignored(self):
        evaluation = TicketEvaluation(
            department="General",
            urgency=Urgency.LOW,
            refund_requested=False,
            notes="ignored",  # type: ignore
        )
        assert not hasattr(evaluation, "notes")

    def test_model_dump_json_serializes_urgency_as_string(self):
        evaluation = TicketEvaluation(
            department="Billing",
            urgency=Urgency.CRITICAL,
            refund_requested=True,
        )
        assert evaluation.model_dump(mode="json") == {
            "department": "Billing",
            "urgency": "CRITICAL",
            "refund_requested": True,
        }
        assert '"urgency":"CRITICAL"' in evaluation.model_dump_json()
