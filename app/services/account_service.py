from decimal import Decimal

from app.extensions import db
from app.models.account import Account
from app.models.transaction import Transaction
from app.services.exceptions import ConflictError, NotFoundError


def list_accounts(user_id: int) -> list[Account]:
    return (
        db.session.query(Account)
        .filter_by(user_id=user_id)
        .order_by(Account.created_at.desc())
        .all()
    )


def get_account(user_id: int, account_id: int) -> Account:
    account = db.session.query(Account).filter_by(id=account_id, user_id=user_id).first()
    if account is None:
        raise NotFoundError("Conta não encontrada.")
    return account


def create_account(
    user_id: int, name: str, type: str, initial_balance: Decimal, currency: str
) -> Account:
    account = Account(
        user_id=user_id,
        name=name,
        type=type,
        initial_balance=initial_balance,
        current_balance=initial_balance,
        currency=currency,
    )
    db.session.add(account)
    db.session.commit()
    return account


def update_account(user_id: int, account_id: int, **fields) -> Account:
    account = get_account(user_id, account_id)
    for key, value in fields.items():
        if value is not None:
            setattr(account, key, value)
    db.session.commit()
    return account


def delete_account(user_id: int, account_id: int) -> None:
    account = get_account(user_id, account_id)

    has_transactions = (
        db.session.query(Transaction)
        .filter_by(account_id=account_id, user_id=user_id)
        .first()
        is not None
    )
    if has_transactions:
        raise ConflictError(
            "Esta conta possui transações vinculadas e não pode ser excluída. "
            "Arquive a conta (is_archived=True) em vez de excluí-la."
        )

    db.session.delete(account)
    db.session.commit()
