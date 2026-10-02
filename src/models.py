from pydantic import BaseModel
from typesafe_sdk import ChoiceAnswer, NoulAnswer, ScoreAnswer

from src.constants import Urgency


class Ticket(BaseModel):
    subject: str
    body: str


class TicketResponse(BaseModel):
    department: ChoiceAnswer
    urgency: ScoreAnswer
    refund_requested: NoulAnswer


class TicketEvaluation(BaseModel):
    department: str
    urgency: Urgency
    refund_requested: bool
