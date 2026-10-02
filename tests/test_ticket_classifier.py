import json
import logging

import pytest
from pydantic import ValidationError
from typesafe_sdk import TypeSafeError

from src.constants import (
    CONFIDENCE_THRESHOLD,
    NOUL_UNCERTAINTY_HIGH,
    NOUL_UNCERTAINTY_LOW,
    Urgency,
)
from src.models import Ticket, TicketEvaluation
from src.schemas import TICKET_CLASSIFICATION_SCHEMA
from src.ticket_classifier import (
    classify_ticket,
    decide_department,
    decide_refund_requested,
    decide_urgency,
    evaluate_response,
    normalize_urgency_value,
)


def warnings(record):
    return [r for r in record if r.levelno == logging.WARNING]


class TestDecideDepartment:
    @pytest.mark.parametrize(
        ("choice", "expected"),
        [
            ("billing", "Billing"),
            ("technical", "Technical"),
            ("account", "Account"),
            ("general", "General"),
        ],
    )
    def test_capitalizes_known_labels(self, make_choice_answer, choice, expected):
        answer = make_choice_answer(choice=choice, confidence=0.9)
        assert decide_department(answer) == expected

    @pytest.mark.parametrize(
        ("choice", "expected"),
        [
            ("BILLING", "Billing"),
            ("General", "General"),
            ("aCCOunt", "Account"),
        ],
    )
    def test_capitalize_handles_casing(self, make_choice_answer, choice, expected):
        answer = make_choice_answer(choice=choice, confidence=0.9)
        assert decide_department(answer) == expected

    @pytest.mark.parametrize(
        "confidence",
        [0.0, 0.1, CONFIDENCE_THRESHOLD - 0.01, 0.66],
    )
    def test_low_confidence_logs_warning(self, make_choice_answer, caplog, confidence):
        caplog.set_level(logging.WARNING, logger="TICKET CLASSIFIER")
        answer = make_choice_answer(choice="billing", confidence=confidence)
        decide_department(answer)
        logs = warnings(caplog.records)
        assert len(logs) == 1
        assert "Low confidence for department choice" in logs[0].getMessage()
        assert "billing" in logs[0].getMessage()

    @pytest.mark.parametrize(
        "confidence",
        [CONFIDENCE_THRESHOLD, 0.68, 1.0],
    )
    def test_high_confidence_does_not_log_warning(
        self, make_choice_answer, caplog, confidence
    ):
        caplog.set_level(logging.WARNING, logger="TICKET CLASSIFIER")
        answer = make_choice_answer(choice="billing", confidence=confidence)
        decide_department(answer)
        assert warnings(caplog.records) == []

    def test_return_value_is_string(self, make_choice_answer):
        assert isinstance(decide_department(make_choice_answer()), str)


class TestNormalizeUrgencyValue:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("LOW", Urgency.LOW),
            ("MEDIUM", Urgency.MEDIUM),
            ("HIGH", Urgency.HIGH),
            ("CRITICAL", Urgency.CRITICAL),
            ("low", Urgency.LOW),
            ("Critical", Urgency.CRITICAL),
            ("Low - no immediate action required.", Urgency.LOW),
            ("Medium - should be handled soon.", Urgency.MEDIUM),
            ("High - requires prompt attention.", Urgency.HIGH),
            ("Critical - requires immediate attention.", Urgency.CRITICAL),
            ("lowish", Urgency.LOW),
            ("high priority now", Urgency.HIGH),
        ],
    )
    def test_known_values(self, value, expected):
        assert normalize_urgency_value(value) is expected

    @pytest.mark.parametrize(
        "value",
        ["urgent", "URGENT", "", "  ", "normal", "priority", 0, 42, 3.5],
    )
    def test_unknown_values_raise(self, value):
        with pytest.raises(ValueError) as exc_info:
            normalize_urgency_value(value)
        assert "Unknown urgency value" in str(exc_info.value)

    def test_error_message_contains_original_value(self):
        with pytest.raises(ValueError, match="Unknown urgency value: urgentish"):
            normalize_urgency_value("urgentish")

    def test_none_raises(self):
        with pytest.raises(ValueError):
            normalize_urgency_value(None)

    def test_splits_on_hyphen_taking_first_part(self):
        assert normalize_urgency_value("HIGH priority ticket now") is Urgency.HIGH

    def test_trims_whitespace(self):
        assert normalize_urgency_value("   MEDIUM   ") is Urgency.MEDIUM


class TestDecideUrgency:
    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            (0.0, Urgency.LOW),
            (1.0, Urgency.MEDIUM),
            (2.0, Urgency.HIGH),
            (3.0, Urgency.CRITICAL),
            (0.4, Urgency.LOW),
            (1.6, Urgency.HIGH),
            (2.6, Urgency.CRITICAL),
        ],
    )
    def test_rounds_score_and_maps_to_legend(self, make_score_answer, score, expected):
        assert decide_urgency(make_score_answer(score=score)) is expected

    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            (-10.0, Urgency.LOW),
            (-0.4, Urgency.LOW),
            (4.0, Urgency.CRITICAL),
            (99.5, Urgency.CRITICAL),
        ],
    )
    def test_clamps_out_of_range_scores(self, make_score_answer, score, expected):
        assert decide_urgency(make_score_answer(score=score)) is expected

    @pytest.mark.parametrize("confidence", [0.0, 0.5, CONFIDENCE_THRESHOLD - 0.001])
    def test_low_confidence_logs_warning(self, make_score_answer, caplog, confidence):
        caplog.set_level(logging.WARNING, logger="TICKET CLASSIFIER")
        decide_urgency(make_score_answer(score=2.0, confidence=confidence))
        logs = warnings(caplog.records)
        assert len(logs) == 1
        assert "Low confidence for urgency choice" in logs[0].getMessage()

    @pytest.mark.parametrize("confidence", [CONFIDENCE_THRESHOLD, 0.9, 1.0])
    def test_high_confidence_does_not_warn(self, make_score_answer, caplog, confidence):
        caplog.set_level(logging.WARNING, logger="TICKET CLASSIFIER")
        decide_urgency(make_score_answer(score=2.0, confidence=confidence))
        assert warnings(caplog.records) == []

    def test_uses_custom_legend(self, make_score_answer):
        legend = {0: "low load", 1: "medium load", 2: "high load", 3: "critical load"}
        answer = make_score_answer(score=3.0, legend=legend)
        assert decide_urgency(answer) is Urgency.CRITICAL
        answer = make_score_answer(score=0.0, legend=legend)
        assert decide_urgency(answer) is Urgency.LOW

    def test_missing_legend_entry_raises(self, make_score_answer):
        answer = make_score_answer(score=2.0, legend={0: "Low - x"})
        with pytest.raises(KeyError):
            decide_urgency(answer)

    def test_unparseable_legend_value_raises(self, make_score_answer):
        answer = make_score_answer(score=0.0, legend={0: "unknown level"})
        with pytest.raises(ValueError):
            decide_urgency(answer)


class TestDecideRefundRequested:
    @pytest.mark.parametrize(
        ("noul", "expected"),
        [
            (0.0, False),
            (0.1, False),
            (0.49, False),
            (0.4999, False),
            (0.5, True),
            (0.6, True),
            (0.99, True),
            (1.0, True),
        ],
    )
    def test_threshold_at_half(self, make_noul_answer, noul, expected):
        assert decide_refund_requested(make_noul_answer(noul=noul)) is expected

    @pytest.mark.parametrize(
        "noul",
        [
            NOUL_UNCERTAINTY_LOW + 0.001,
            0.3,
            0.5,
            0.7,
            NOUL_UNCERTAINTY_HIGH - 0.001,
        ],
    )
    def test_uncertain_band_logs_warning(self, make_noul_answer, caplog, noul):
        caplog.set_level(logging.WARNING, logger="TICKET CLASSIFIER")
        decide_refund_requested(make_noul_answer(noul=noul))
        logs = warnings(caplog.records)
        assert len(logs) == 1
        assert "Uncertainty determining if a refund was requested" in (
            logs[0].getMessage()
        )

    @pytest.mark.parametrize(
        "noul",
        [0.0, 0.1, NOUL_UNCERTAINTY_LOW, NOUL_UNCERTAINTY_HIGH, 0.9, 1.0],
    )
    def test_confident_values_do_not_warn(self, make_noul_answer, caplog, noul):
        caplog.set_level(logging.WARNING, logger="TICKET CLASSIFIER")
        decide_refund_requested(make_noul_answer(noul=noul))
        assert warnings(caplog.records) == []

    def test_returns_bool(self, make_noul_answer):
        assert isinstance(decide_refund_requested(make_noul_answer()), bool)


class TestEvaluateResponse:
    def test_full_evaluation(self, ticket_response):
        evaluation = evaluate_response(ticket_response)
        assert isinstance(evaluation, TicketEvaluation)
        assert evaluation.department == "Billing"
        assert evaluation.urgency is Urgency.HIGH
        assert evaluation.refund_requested is True

    @pytest.mark.parametrize(
        ("choice", "expected"),
        [
            ("billing", "Billing"),
            ("technical", "Technical"),
            ("account", "Account"),
            ("general", "General"),
        ],
    )
    def test_department_from_response(
        self, make_ticket_response, make_choice_answer, choice, expected
    ):
        response = make_ticket_response(department=make_choice_answer(choice=choice))
        assert evaluate_response(response).department == expected

    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            (0.1, Urgency.LOW),
            (1.2, Urgency.MEDIUM),
            (2.7, Urgency.CRITICAL),
            (-5.0, Urgency.LOW),
            (50.0, Urgency.CRITICAL),
        ],
    )
    def test_urgency_from_response(
        self, make_ticket_response, make_score_answer, score, expected
    ):
        response = make_ticket_response(urgency=make_score_answer(score=score))
        assert evaluate_response(response).urgency is expected

    @pytest.mark.parametrize(
        ("noul", "expected"),
        [(0.05, False), (0.4, False), (0.5, True), (0.99, True)],
    )
    def test_refund_from_response(
        self, make_ticket_response, make_noul_answer, noul, expected
    ):
        response = make_ticket_response(refund_requested=make_noul_answer(noul=noul))
        assert evaluate_response(response).refund_requested is expected

    def test_urgency_is_enum_member(self, ticket_response):
        assert isinstance(evaluate_response(ticket_response).urgency, Urgency)

    def test_all_warnings_are_emitted_when_uncertain(
        self,
        make_ticket_response,
        make_choice_answer,
        make_score_answer,
        make_noul_answer,
        caplog,
    ):
        caplog.set_level(logging.WARNING, logger="TICKET CLASSIFIER")
        response = make_ticket_response(
            department=make_choice_answer(confidence=0.1),
            urgency=make_score_answer(score=1.0, confidence=0.2),
            refund_requested=make_noul_answer(noul=0.5),
        )
        evaluate_response(response)
        logs = warnings(caplog.records)
        assert len(logs) == 3
        messages = [record.getMessage() for record in logs]
        assert any("department" in m for m in messages)
        assert any("urgency" in m for m in messages)
        assert any("refund" in m for m in messages)


class TestClassifyTicket:
    def _wire(self, client_cls, answers):
        client = client_cls.return_value.__enter__.return_value
        client.system_one.return_value = type("R", (), {"answers": answers})()
        return client

    def test_returns_evaluation(self, mock_type_safe_client, answers):
        self._wire(mock_type_safe_client, answers)
        result = classify_ticket(Ticket(subject="Charged twice", body="refund plz"))
        assert isinstance(result, TicketEvaluation)
        assert result.department == "Billing"
        assert result.urgency is Urgency.HIGH
        assert result.refund_requested is True

    def test_calls_system_one_with_ticket_state_and_schema(
        self, mock_type_safe_client, answers
    ):
        client = self._wire(mock_type_safe_client, answers)
        ticket = Ticket(subject="Charged twice", body="refund plz")
        classify_ticket(ticket)
        client.system_one.assert_called_once_with(
            state=ticket.model_dump(),
            questions=TICKET_CLASSIFICATION_SCHEMA,
        )

    def test_client_used_as_context_manager(self, mock_type_safe_client, answers):
        self._wire(mock_type_safe_client, answers)
        client_cls = mock_type_safe_client
        classify_ticket(Ticket(subject="s", body="b"))
        client_cls.assert_called_once_with()
        client_cls.return_value.__enter__.assert_called_once_with()
        client_cls.return_value.__exit__.assert_called_once()

    def test_logs_subject_at_info(
        self, mock_type_safe_client, answers, classifier_logs
    ):
        self._wire(mock_type_safe_client, answers)
        classify_ticket(Ticket(subject="Broken widget", body="b"))
        messages = classifier_logs(logging.INFO)
        assert any("Classifying ticket: Broken widget" in m for m in messages)

    def test_logs_response_at_debug(
        self, mock_type_safe_client, answers, classifier_logs
    ):
        self._wire(mock_type_safe_client, answers)
        classify_ticket(Ticket(subject="s", body="b"))
        messages = classifier_logs(logging.DEBUG)
        debug_messages = [m for m in messages if m.startswith("Received response")]
        assert len(debug_messages) == 1
        payload = json.loads(debug_messages[0].split("\n", 1)[1])
        assert json.loads(payload)["department"]["choice"] == "billing"

    def test_client_error_is_logged_and_reraised(
        self, mock_type_safe_client, classifier_logs
    ):
        client = mock_type_safe_client.return_value.__enter__.return_value
        client.system_one.side_effect = RuntimeError("network down")
        with pytest.raises(RuntimeError, match="network down"):
            classify_ticket(Ticket(subject="s", body="b"))
        messages = classifier_logs(logging.ERROR)
        assert any("Failed to classify ticket: network down" in m for m in messages)

    def test_invalid_answers_are_logged_and_reraised(
        self, mock_type_safe_client, answers, classifier_logs
    ):
        del answers["urgency"]
        self._wire(mock_type_safe_client, answers)
        with pytest.raises(ValidationError):
            classify_ticket(Ticket(subject="s", body="b"))
        messages = classifier_logs(logging.ERROR)
        assert any("Failed to classify ticket" in m for m in messages)

    def test_client_construction_failure_is_reraised(self, mock_type_safe_client):
        mock_type_safe_client.side_effect = TypeSafeError("missing api key")
        with pytest.raises(TypeSafeError, match="missing api key"):
            classify_ticket(Ticket(subject="s", body="b"))

    def test_closes_client_on_success(self, mock_type_safe_client, answers):
        self._wire(mock_type_safe_client, answers)
        classify_ticket(Ticket(subject="s", body="b"))
        mock_type_safe_client.return_value.__exit__.assert_called_once()

    def test_closes_client_on_failure(self, mock_type_safe_client):
        client = mock_type_safe_client.return_value.__enter__.return_value
        client.system_one.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError):
            classify_ticket(Ticket(subject="s", body="b"))
        mock_type_safe_client.return_value.__exit__.assert_called_once()
