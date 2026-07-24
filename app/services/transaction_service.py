from datetime import date
from decimal import Decimal
from typing import Any

from app.extensions import db
from app.models.account import Account
from app.models.category import Category
from app.models.credit_card import CreditCard
from app.models.transaction import Transaction
from app.services import invoice_service
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


def _get_owned_credit_card(user_id: int, credit_card_id: int | None) -> CreditCard | None:
    if credit_card_id is None:
        return None
    card = db.session.query(CreditCard).filter_by(id=credit_card_id, user_id=user_id).first()
    if card is None:
        raise ValidationError("credit_card_id inválido para este usuário.")
    return card


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
    credit_card_id: int | None = None,
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
    if credit_card_id is not None:
        query = query.filter(Transaction.credit_card_id == credit_card_id)
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
    credit_card_id: int | None,
    type: str,
    description: str,
    amount: Decimal,
    date: date,
    is_paid: bool,
    notes: str | None,
) -> Transaction:
    account = _get_owned_account(user_id, account_id)
    _get_owned_category(user_id, category_id)
    card = _get_owned_credit_card(user_id, credit_card_id)

    if card is not None and type != "expense":
        raise ValidationError("Transações em cartão de crédito devem ser do tipo expense.")

    transaction = Transaction(
        user_id=user_id,
        account_id=account_id,
        category_id=category_id,
        credit_card_id=credit_card_id,
        type=type,
        description=description,
        amount=amount,
        date=date,
        is_paid=is_paid,
        notes=notes,
    )

    if card is not None:
        invoice = invoice_service.get_or_create_open_invoice(user_id, card, date)
        invoice_service.assert_invoice_open(invoice)
        invoice_service.add_amount(invoice, amount)
        transaction.invoice_id = invoice.id
    elif is_paid:
        account.current_balance += _signed_amount(type, amount)

    db.session.add(transaction)
    db.session.commit()
    return transaction


def update_transaction(user_id: int, transaction_id: int, **fields: Any) -> Transaction:
    transaction = get_transaction(user_id, transaction_id)

    if transaction.credit_card_id is not None:
        return _update_card_transaction(user_id, transaction, fields)
    return _update_regular_transaction(user_id, transaction, fields)


def _update_card_transaction(user_id: int, transaction: Transaction, fields: dict) -> Transaction:
    if "account_id" in fields or "date" in fields:
        raise ValidationError(
            "account_id e date não podem ser alterados em uma transação de cartão de "
            "crédito, pois eles determinam a fatura a que ela pertence."
        )

    invoice = invoice_service.get_invoice(user_id, transaction.invoice_id)
    invoice_service.assert_invoice_open(invoice)

    new_amount = fields.get("amount", transaction.amount)
    if new_amount != transaction.amount:
        invoice_service.remove_amount(invoice, transaction.amount)
        invoice_service.add_amount(invoice, new_amount)

    for key in ("category_id", "description", "amount", "is_paid", "notes"):
        if key in fields and fields[key] is not None:
            setattr(transaction, key, fields[key])

    db.session.commit()
    return transaction


def _update_regular_transaction(
    user_id: int, transaction: Transaction, fields: dict
) -> Transaction:
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

    if transaction.credit_card_id is not None:
        invoice = invoice_service.get_invoice(user_id, transaction.invoice_id)
        invoice_service.assert_invoice_open(invoice)
        invoice_service.remove_amount(invoice, transaction.amount)
    else:
        account = _get_owned_account(user_id, transaction.account_id)
        if transaction.is_paid:
            account.current_balance -= _signed_amount(transaction.type, transaction.amount)

    db.session.delete(transaction)
    db.session.commit()
