from datetime import date
from decimal import Decimal
from typing import Any

from app.extensions import db
from app.models.account import Account
from app.models.category import Category
from app.models.transaction import Transaction
from app.services.exceptions import NotFoundError, ValidationError


def _signed_amount(type_: str, amount: Decimal) -> Decimal:
    return amount if type_ == "income" else -amount


def _get_owned_account(user_id: int, account_id: int) -> Account:
    account = db.session.query(Account).filter_by(id=account_id, user_id=user_id).first()
    if account is None:
        raise ValidationError("account_id inválido para este usuário.")
    return account


def _get_owned_category(user_id: int, category_id: int | None) -> Category | None:
    if category_id is None:
        return None
    category = db.session.query(Category).filter_by(id=category_id, user_id=user_id).first()
    if category is None:
        raise ValidationError("category_id inválido para este usuário.")
    return category


def get_transaction(user_id: int, transaction_id: int) -> Transaction:
    transaction = (
        db.session.query(Transaction).filter_by(id=transaction_id, user_id=user_id).first()
    )
    if transaction is None:
        raise NotFoundError("Transação não encontrada.")
    return transaction


def list_transactions(
    user_id: int,
    account_id: int | None = None,
    category_id: int | None = None,
    type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Transaction], int]:
    query = db.session.query(Transaction).filter_by(user_id=user_id)

    if account_id is not None:
        query = query.filter(Transaction.account_id == account_id)
    if category_id is not None:
        query = query.filter(Transaction.category_id == category_id)
    if type is not None:
        query = query.filter(Transaction.type == type)
    if date_from is not None:
        query = query.filter(Transaction.date >= date_from)
    if date_to is not None:
        query = query.filter(Transaction.date <= date_to)

    total = query.count()
    items = (
        query.order_by(Transaction.date.desc(), Transaction.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return items, total


def create_transaction(
    user_id: int,
    account_id: int,
    category_id: int | None,
    type: str,
    description: str,
    amount: Decimal,
    date: date,
    is_paid: bool,
    notes: str | None,
) -> Transaction:
    account = _get_owned_account(user_id, account_id)
    _get_owned_category(user_id, category_id)

    transaction = Transaction(
        user_id=user_id,
        account_id=account_id,
        category_id=category_id,
        type=type,
        description=description,
        amount=amount,
        date=date,
        is_paid=is_paid,
        notes=notes,
    )
    db.session.add(transaction)

    if is_paid:
        account.current_balance += _signed_amount(type, amount)

    db.session.commit()
    return transaction


def update_transaction(user_id: int, transaction_id: int, **fields: Any) -> Transaction:
    transaction = get_transaction(user_id, transaction_id)
    old_account = _get_owned_account(user_id, transaction.account_id)
    old_effect = (
        _signed_amount(transaction.type, transaction.amount) if transaction.is_paid else Decimal(0)
    )

    new_account_id = fields.get("account_id", transaction.account_id)
    new_category_id = fields.get("category_id", transaction.category_id)
    new_amount = fields.get("amount", transaction.amount)
    new_is_paid = fields.get("is_paid", transaction.is_paid)

    new_account = _get_owned_account(user_id, new_account_id)
    _get_owned_category(user_id, new_category_id)

    old_account.current_balance -= old_effect

    for key in ("account_id", "category_id", "description", "amount", "date", "is_paid", "notes"):
        if key in fields and fields[key] is not None:
            setattr(transaction, key, fields[key])

    new_effect = _signed_amount(transaction.type, new_amount) if new_is_paid else Decimal(0)
    new_account.current_balance += new_effect

    db.session.commit()
    return transaction


def delete_transaction(user_id: int, transaction_id: int) -> None:
    transaction = get_transaction(user_id, transaction_id)
    account = _get_owned_account(user_id, transaction.account_id)

    if transaction.is_paid:
        account.current_balance -= _signed_amount(transaction.type, transaction.amount)

    db.session.delete(transaction)
    db.session.commit()
