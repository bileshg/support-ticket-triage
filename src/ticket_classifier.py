import json
import logging
from typing import Any

from typesafe_sdk import ChoiceAnswer, NoulAnswer, ScoreAnswer, TypeSafeClient

from src.constants import (
    CONFIDENCE_THRESHOLD,
    NOUL_UNCERTAINTY_HIGH,
    NOUL_UNCERTAINTY_LOW,
    Urgency,
)
from src.models import Ticket, TicketEvaluation, TicketResponse
from src.schemas import TICKET_CLASSIFICATION_SCHEMA

logger = logging.getLogger("TICKET CLASSIFIER")


def decide_department(answer: ChoiceAnswer) -> str:
    if answer.confidence < CONFIDENCE_THRESHOLD:
        logger.warning(
            "Low confidence for department choice: %s (%.2f)",
            answer.choice,
            answer.confidence,
        )
    return answer.choice.capitalize()


def normalize_urgency_value(value: Any) -> Urgency:
    value_str = str(value).split("-")[0].strip().upper()
    for urgency in Urgency:
        if urgency.value in value_str:
            return urgency
    raise ValueError(f"Unknown urgency value: {value}")


def decide_urgency(answer: ScoreAnswer) -> Urgency:
    urgency_score = round(answer.score)
    urgency_score = min(max(urgency_score, 0), len(Urgency) - 1)
    urgency = normalize_urgency_value(answer.legend[urgency_score])

    if answer.confidence < CONFIDENCE_THRESHOLD:
        logger.warning(
            "Low confidence for urgency choice: %s (%.2f)",
            urgency,
            answer.confidence,
        )

    return urgency


def decide_refund_requested(answer: NoulAnswer) -> bool:
    if NOUL_UNCERTAINTY_LOW < answer.noul < NOUL_UNCERTAINTY_HIGH:
        logger.warning(
            "Uncertainty determining if a refund was requested: %.2f", answer.noul
        )
    return answer.noul >= 0.5


def evaluate_response(response: TicketResponse) -> TicketEvaluation:
    department = decide_department(response.department)
    urgency = decide_urgency(response.urgency)
    refund_requested = decide_refund_requested(response.refund_requested)

    return TicketEvaluation(
        department=department,
        urgency=urgency,
        refund_requested=refund_requested,
    )


def classify_ticket(ticket: Ticket) -> TicketEvaluation:
    logger.info("Classifying ticket: %s", ticket.subject)
    try:
        with TypeSafeClient() as client:
            response = client.system_one(
                state=ticket.model_dump(),
                questions=TICKET_CLASSIFICATION_SCHEMA,
            )

            response = TicketResponse.model_validate(response.answers)
            logger.debug(
                "Received response:\n%s", json.dumps(response.model_dump_json(indent=4))
            )
            return evaluate_response(response)
    except Exception as e:
        logger.error("Failed to classify ticket: %s", e)
        raise
