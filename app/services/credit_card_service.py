from decimal import Decimal

from app.extensions import db
from app.models.credit_card import CreditCard
from app.models.invoice import Invoice
from app.services.exceptions import ConflictError, NotFoundError


def list_credit_cards(user_id: int) -> list[CreditCard]:
    return (
        db.session.query(CreditCard)
        .filter_by(user_id=user_id)
        .order_by(CreditCard.created_at.desc())
        .all()
    )


def get_credit_card(user_id: int, credit_card_id: int) -> CreditCard:
    card = db.session.query(CreditCard).filter_by(id=credit_card_id, user_id=user_id).first()
    if card is None:
        raise NotFoundError("Cartão de crédito não encontrado.")
    return card


def create_credit_card(
    user_id: int, name: str, credit_limit: Decimal, closing_day: int, due_day: int
) -> CreditCard:
    card = CreditCard(
        user_id=user_id,
        name=name,
        credit_limit=credit_limit,
        closing_day=closing_day,
        due_day=due_day,
    )
    db.session.add(card)
    db.session.commit()
    return card


def update_credit_card(user_id: int, credit_card_id: int, **fields) -> CreditCard:
    card = get_credit_card(user_id, credit_card_id)
    for key, value in fields.items():
        if value is not None:
            setattr(card, key, value)
    db.session.commit()
    return card


def delete_credit_card(user_id: int, credit_card_id: int) -> None:
    card = get_credit_card(user_id, credit_card_id)

    has_invoices = (
        db.session.query(Invoice).filter_by(credit_card_id=credit_card_id, user_id=user_id).first()
        is not None
    )
    if has_invoices:
        raise ConflictError(
            "Este cartão possui faturas vinculadas e não pode ser excluído. "
            "Arquive o cartão (is_archived=True) em vez de excluí-lo."
        )

    db.session.delete(card)
    db.session.commit()
