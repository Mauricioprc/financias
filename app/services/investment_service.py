from datetime import date
from decimal import Decimal

from app.extensions import db
from app.models.investment import Investment
from app.services.exceptions import NotFoundError


def list_investments(user_id: int) -> list[Investment]:
    return (
        db.session.query(Investment)
        .filter_by(user_id=user_id)
        .order_by(Investment.created_at.desc())
        .all()
    )


def get_investment(user_id: int, investment_id: int) -> Investment:
    investment = db.session.query(Investment).filter_by(id=investment_id, user_id=user_id).first()
    if investment is None:
        raise NotFoundError("Investimento não encontrado.")
    return investment


def create_investment(
    user_id: int,
    name: str,
    type: str,
    broker: str | None,
    invested_amount: Decimal,
    current_amount: Decimal | None,
    acquired_at: date,
    notes: str | None,
) -> Investment:
    investment = Investment(
        user_id=user_id,
        name=name,
        type=type,
        broker=broker,
        invested_amount=invested_amount,
        current_amount=current_amount if current_amount is not None else invested_amount,
        acquired_at=acquired_at,
        notes=notes,
    )
    db.session.add(investment)
    db.session.commit()
    return investment


def update_investment(user_id: int, investment_id: int, **fields) -> Investment:
    investment = get_investment(user_id, investment_id)
    for key, value in fields.items():
        if value is not None:
            setattr(investment, key, value)
    db.session.commit()
    return investment


def delete_investment(user_id: int, investment_id: int) -> None:
    investment = get_investment(user_id, investment_id)
    db.session.delete(investment)
    db.session.commit()
