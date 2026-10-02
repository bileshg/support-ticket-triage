import logging

from dotenv import load_dotenv
from fastapi import FastAPI

from src.models import Ticket, TicketEvaluation
from src.ticket_classifier import classify_ticket

load_dotenv()

logger = logging.getLogger("APP")
logging.basicConfig(level=logging.DEBUG)

app = FastAPI()


@app.post("/ticket/classify")
async def classify_tickets(ticket: Ticket) -> TicketEvaluation:
    return classify_ticket(ticket)
