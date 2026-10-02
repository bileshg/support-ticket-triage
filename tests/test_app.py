import pytest
from fastapi.testclient import TestClient

import app as app_module
from src.schemas import TICKET_CLASSIFICATION_SCHEMA

client = TestClient(app_module.app, raise_server_exceptions=False)


@pytest.fixture
def wire(mock_type_safe_client, answers):
    result_client = mock_type_safe_client.return_value.__enter__.return_value
    from types import SimpleNamespace

    result_client.system_one.return_value = SimpleNamespace(answers=answers)
    return mock_type_safe_client


class TestAppSetup:
    def test_app_is_fastapi_instance(self):
        from fastapi import FastAPI

        assert isinstance(app_module.app, FastAPI)

    def test_classify_route_is_registered(self):
        paths = {route.path for route in app_module.app.routes}  # type: ignore
        assert "/ticket/classify" in paths

    def test_module_exposes_classify_tickets_endpoint(self):
        assert callable(app_module.classify_tickets)


class TestClassifyEndpoint:
    def test_successful_classification_returns_evaluation(self, wire):
        response = client.post(
            "/ticket/classify",
            json={"subject": "Charged twice", "body": "Please refund me"},
        )
        assert response.status_code == 200
        assert response.json() == {
            "department": "Billing",
            "urgency": "HIGH",
            "refund_requested": True,
        }

    @pytest.mark.parametrize(
        ("choice", "expected_department"),
        [
            ("billing", "Billing"),
            ("technical", "Technical"),
            ("account", "Account"),
            ("general", "General"),
        ],
    )
    def test_department_variants(
        self, wire, mock_type_safe_client, answers, choice, expected_department
    ):
        answers["department"]["choice"] = choice
        response = client.post(
            "/ticket/classify",
            json={"subject": "s", "body": "b"},
        )
        assert response.status_code == 200
        assert response.json()["department"] == expected_department

    @pytest.mark.parametrize(
        ("score", "expected_urgency"),
        [
            (0.2, "LOW"),
            (1.1, "MEDIUM"),
            (2.8, "CRITICAL"),
        ],
    )
    def test_urgency_variants(self, wire, answers, score, expected_urgency):
        answers["urgency"]["score"] = score
        response = client.post(
            "/ticket/classify",
            json={"subject": "s", "body": "b"},
        )
        assert response.status_code == 200
        assert response.json()["urgency"] == expected_urgency

    @pytest.mark.parametrize(
        ("noul", "expected_refund"),
        [(0.1, False), (0.75, True)],
    )
    def test_refund_variants(self, wire, answers, noul, expected_refund):
        answers["refund_requested"]["noul"] = noul
        response = client.post(
            "/ticket/classify",
            json={"subject": "s", "body": "b"},
        )
        assert response.status_code == 200
        assert response.json()["refund_requested"] is expected_refund

    def test_forwards_ticket_state_to_client(self, wire, mock_type_safe_client):
        payload = {"subject": "Login broken", "body": "500 on login"}
        response = client.post("/ticket/classify", json=payload)
        assert response.status_code == 200
        client_mock = mock_type_safe_client.return_value.__enter__.return_value
        state = client_mock.system_one.call_args.kwargs["state"]
        assert state == payload
        questions = client_mock.system_one.call_args.kwargs["questions"]
        assert questions is TICKET_CLASSIFICATION_SCHEMA

    def test_low_confidence_response_still_returns_200(self, wire, answers):
        answers["department"]["confidence"] = 0.1
        answers["urgency"]["confidence"] = 0.05
        response = client.post(
            "/ticket/classify",
            json={"subject": "s", "body": "b"},
        )
        assert response.status_code == 200
        assert response.json()["department"] == "Billing"


class TestClassifyEndpointValidation:
    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"subject": "only subject"},
            {"body": "only body"},
            {"subject": 1, "body": "b"},
            {"subject": "s", "body": 42},
            {"subject": None, "body": None},
        ],
    )
    def test_invalid_payloads_return_422(self, payload):
        response = client.post("/ticket/classify", json=payload)
        assert response.status_code == 422

    def test_extra_payload_fields_are_accepted(self, wire):
        response = client.post(
            "/ticket/classify",
            json={"subject": "s", "body": "b", "priority": "high"},
        )
        assert response.status_code == 200

    def test_malformed_json_returns_422(self):
        response = client.post(
            "/ticket/classify",
            content=b"{not json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422


class TestClassifyEndpointFailures:
    def test_client_failure_returns_500(self, mock_type_safe_client):
        client_mock = mock_type_safe_client.return_value.__enter__.return_value
        client_mock.system_one.side_effect = RuntimeError("api unavailable")
        response = client.post(
            "/ticket/classify",
            json={"subject": "s", "body": "b"},
        )
        assert response.status_code == 500

    def test_invalid_answers_return_500(self, wire, answers):
        del answers["department"]
        response = client.post(
            "/ticket/classify",
            json={"subject": "s", "body": "b"},
        )
        assert response.status_code == 500

    def test_endpoint_uses_context_manager(self, wire, mock_type_safe_client):
        client.post("/ticket/classify", json={"subject": "s", "body": "b"})
        mock_type_safe_client.return_value.__exit__.assert_called_once()


class TestOtherHttpMethods:
    def test_get_classify_not_allowed(self):
        response = client.get("/ticket/classify")
        assert response.status_code == 405

    def test_unknown_path_returns_404(self):
        response = client.post("/unknown", json={})
        assert response.status_code == 404
