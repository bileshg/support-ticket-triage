# Support Ticket Triage

A support ticket classifier built with **TypeSafe SDK** that categorizes and prioritizes incoming support tickets.

## What it does

Given a support ticket, the application uses TypeSafe SDK to determine:

- **Department** — Billing, Technical, Account, or General
- **Urgency** — Low, Medium, High, or Critical
- **Refund Request** — whether the customer is explicitly requesting a refund

Example input:

```json
{
  "subject": "Charged twice for my subscription",
  "body": "I was billed twice this month. Please refund the extra charge."
}
```

Example output:

```json
{
  "department": "Billing",
  "urgency": "HIGH",
  "refund_requested": true
}
```

## How it works

The classifier uses three TypeSafe SDK decision primitives:

- **Choice** — selects the appropriate department from predefined options
- **Score** — evaluates urgency on a calibrated scale
- **Noul** — makes a probabilistic yes/no decision for refund requests

## Tech Stack

- Python 3.11+
- FastAPI
- TypeSafe SDK
- Pydantic

## API

```http
POST /ticket/classify
```

The endpoint accepts a support ticket and returns its classification.

### Request Body

```json
{
  "subject": "string",
  "body": "string"
}
```

### Response

```json
{
  "department": "Billing|Technical|Account|General",
  "urgency": "LOW|MEDIUM|HIGH|CRITICAL",
  "refund_requested": boolean
}
```

## Project Structure

```
support-ticket-triage/
├── app.py
├── src/
│   ├── constants.py       # Configuration constants and enums
│   ├── models.py          # Pydantic models for requests/responses
│   ├── schemas.py         # TypeSafe SDK classification schema
│   └── ticket_classifier.py  # Core classification logic
├── pyproject.toml
├── uv.lock
└── README.md
```

## Setup

```bash
# Install dependencies
uv sync

# Run the server
fastapi run app.py
```

## Environment Variables

Create a `.env` file with your TypeSafe API credentials (see `.env.example`).

## Purpose

This project demonstrates how TypeSafe SDK can make structured decisions inside an otherwise deterministic application, using Choice, Score, and Noul primitives for ticket classification.