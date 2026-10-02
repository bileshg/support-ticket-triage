from typesafe_sdk import Choice, Noul, Score

TICKET_CLASSIFICATION_SCHEMA = {
    "department": Choice(
        instructions="Which department should handle this support ticket?",
        criteria={
            "billing": "Payments, charges, invoices, subscriptions, or refunds.",
            "technical": "Bugs, errors, outages, or technical problems.",
            "account": "Login, profile, permissions, or account management issues.",
            "general": "Requests that do not fit the other categories.",
        },
    ),
    "urgency": Score(
        instructions="How urgent is this support ticket?",
        criteria=[
            "Low - no immediate action required.",
            "Medium - should be handled soon.",
            "High - requires prompt attention.",
            "Critical - requires immediate attention.",
        ],
    ),
    "refund_requested": Noul(
        instructions="Is the customer explicitly requesting a refund?",
    ),
}
