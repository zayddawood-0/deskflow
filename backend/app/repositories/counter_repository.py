from sqlalchemy import text
from sqlalchemy.orm import Session


def next_ticket_number(db: Session) -> str:
    value = db.execute(
        text("UPDATE counters SET value = value + 1 WHERE name = 'ticket' RETURNING value")
    ).scalar_one()
    return f"TCK-{value}"
