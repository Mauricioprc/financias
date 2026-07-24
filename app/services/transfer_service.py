from datetime import date
from decimal import Decimal

from app.extensions import db
from app.models.account import Account
from app.models.transfer import Transfer
from app.services.exceptions import NotFoundError, ValidationError


def _get_owned_account(user_id: int, account_id: int) -> Account:
    account = db.session.query(Account).filter_by(id=account_id, user_id=user_id).first()
    if account is None:
        raise ValidationError("Conta inválida para este usuário.")
    return account


def get_transfer(user_id: int, transfer_id: int) -> Transfer:
    transfer = db.session.query(Transfer).filter_by(id=transfer_id, user_id=user_id).first()
    if transfer is None:
        raise NotFoundError("Transferência não encontrada.")
    return transfer


def list_transfers(
    user_id: int,
    account_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Transfer], int]:
    query = db.session.query(Transfer).filter_by(user_id=user_id)

    if account_id is not None:
        query = query.filter(
            (Transfer.from_account_id == account_id) | (Transfer.to_account_id == account_id)
        )
    if date_from is not None:
        query = query.filter(Transfer.date >= date_from)
    if date_to is not None:
        query = query.filter(Transfer.date <= date_to)

    total = query.count()
    items = (
        query.order_by(Transfer.date.desc(), Transfer.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return items, total


def create_transfer(
    user_id: int,
    from_account_id: int,
    to_account_id: int,
    amount: Decimal,
    date: date,
    description: str | None,
) -> Transfer:
    if from_account_id == to_account_id:
        raise ValidationError("from_account_id e to_account_id devem ser contas diferentes.")

    from_account = _get_owned_account(user_id, from_account_id)
    to_account = _get_owned_account(user_id, to_account_id)

    transfer = Transfer(
        user_id=user_id,
        from_account_id=from_account_id,
        to_account_id=to_account_id,
        amount=amount,
        date=date,
        description=description,
    )
    db.session.add(transfer)

    from_account.current_balance -= amount
    to_account.current_balance += amount

    db.session.commit()
    return transfer


def delete_transfer(user_id: int, transfer_id: int) -> None:
    transfer = get_transfer(user_id, transfer_id)
    from_account = _get_owned_account(user_id, transfer.from_account_id)
    to_account = _get_owned_account(user_id, transfer.to_account_id)

    from_account.current_balance += transfer.amount
    to_account.current_balance -= transfer.amount

    db.session.delete(transfer)
    db.session.commit()
