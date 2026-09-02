import uuid
from datetime import date
from decimal import ROUND_DOWN, Decimal
from typing import Any

from app.extensions import db
from app.models.account import Account
from app.models.category import Category
from app.models.credit_card import CreditCard
from app.models.transaction import Transaction
from app.services import category_suggestion_service, invoice_service
from app.services.exceptions import NotFoundError, ValidationError
from app.services.ledger_utils import adjust_account_balance
from app.utils.datetime_utils import shift_date


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
    invoice_id: int | None = None,
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
    if invoice_id is not None:
        query = query.filter(Transaction.invoice_id == invoice_id)
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
        adjust_account_balance(account.id, _signed_amount(type, amount))

    db.session.add(transaction)
    # Aprendizado automático e silencioso do padrão descrição->categoria —
    # não é uma decisão do usuário, só alimenta sugestões futuras (ver
    # category_suggestion_service.suggest_category).
    category_suggestion_service.record_pattern(user_id, description, category_id)
    db.session.commit()
    return transaction


MIN_INSTALLMENTS = 2
MAX_INSTALLMENTS = 24


def create_installment_purchase(
    user_id: int,
    account_id: int,
    credit_card_id: int,
    category_id: int | None,
    description: str,
    total_amount: Decimal,
    installments: int,
    date: date,
    notes: str | None = None,
) -> list[Transaction]:
    """Compra parcelada no cartão de crédito: cria uma `Transaction` por
    parcela, cada uma na fatura do mês correspondente (mesma regra de
    fechamento de `invoice_service.compute_invoice_period`, só aplicada N
    vezes a partir de `date`). Todas compartilham `purchase_group_id`, o que
    permite no futuro editar/cancelar a compra inteira de uma vez.

    Se qualquer parcela cair numa fatura já fechada (raro — só acontece se
    alguém fechar manualmente uma fatura de mês futuro antes da hora), a
    operação inteira falha sem commitar nada: nenhuma parcela fica "solta".
    """
    if installments < MIN_INSTALLMENTS or installments > MAX_INSTALLMENTS:
        raise ValidationError(
            f"installments deve estar entre {MIN_INSTALLMENTS} e {MAX_INSTALLMENTS}."
        )

    _get_owned_account(user_id, account_id)
    _get_owned_category(user_id, category_id)
    card = _get_owned_credit_card(user_id, credit_card_id)
    if card is None:
        raise ValidationError("credit_card_id é obrigatório para compra parcelada.")

    purchase_group_id = uuid.uuid4()
    amounts = _split_installment_amounts(total_amount, installments)

    created: list[Transaction] = []
    try:
        for index, amount in enumerate(amounts):
            installment_date = shift_date(date, index)
            invoice = invoice_service.get_or_create_open_invoice(user_id, card, installment_date)
            invoice_service.assert_invoice_open(invoice)
            invoice_service.add_amount(invoice, amount)

            transaction = Transaction(
                user_id=user_id,
                account_id=account_id,
                category_id=category_id,
                credit_card_id=credit_card_id,
                invoice_id=invoice.id,
                type="expense",
                description=description,
                amount=amount,
                date=installment_date,
                is_paid=True,
                installment_number=index + 1,
                installment_total=installments,
                purchase_group_id=purchase_group_id,
                notes=notes,
            )
            db.session.add(transaction)
            created.append(transaction)
    except Exception:
        # Atomicidade explícita: uma parcela em qualquer mês (ex.: fatura
        # futura já fechada manualmente) invalida a compra inteira. Não dá
        # pra confiar só no rollback automático de fim de request — as
        # faturas/parcelas de meses anteriores nesse mesmo loop já foram
        # flushadas (get_or_create_open_invoice usa flush pra pegar o id),
        # então sem esse rollback explícito elas ficariam "soltas" até o
        # encerramento da sessão.
        db.session.rollback()
        raise

    db.session.commit()
    return created


def _split_installment_amounts(total_amount: Decimal, installments: int) -> list[Decimal]:
    """N-1 parcelas iguais (arredondadas pra baixo em centavos); a última
    absorve o resto, garantindo que a soma bate exatamente com o total."""
    cents = int((total_amount * 100).to_integral_value(rounding=ROUND_DOWN))
    base_cents = cents // installments
    amounts = [Decimal(base_cents) / 100] * (installments - 1)
    last_cents = cents - base_cents * (installments - 1)
    amounts.append(Decimal(last_cents) / 100)
    return amounts


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

    assert transaction.invoice_id is not None  # garantido por create_transaction
    invoice = invoice_service.get_invoice(user_id, transaction.invoice_id)
    invoice_service.assert_invoice_open(invoice)

    new_amount = fields.get("amount", transaction.amount)
    if new_amount != transaction.amount:
        invoice_service.remove_amount(invoice, transaction.amount)
        invoice_service.add_amount(invoice, new_amount)

    for key in ("category_id", "description", "amount", "is_paid", "notes"):
        if key in fields and fields[key] is not None:
            setattr(transaction, key, fields[key])

    category_suggestion_service.record_pattern(
        user_id, transaction.description, transaction.category_id
    )
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

    adjust_account_balance(old_account.id, -old_effect)

    for key in ("account_id", "category_id", "description", "amount", "date", "is_paid", "notes"):
        if key in fields and fields[key] is not None:
            setattr(transaction, key, fields[key])

    new_effect = _signed_amount(transaction.type, new_amount) if new_is_paid else Decimal(0)
    adjust_account_balance(new_account.id, new_effect)

    category_suggestion_service.record_pattern(
        user_id, transaction.description, transaction.category_id
    )
    db.session.commit()
    return transaction


def delete_transaction(user_id: int, transaction_id: int) -> None:
    transaction = get_transaction(user_id, transaction_id)

    if transaction.credit_card_id is not None:
        assert transaction.invoice_id is not None  # garantido por create_transaction
        invoice = invoice_service.get_invoice(user_id, transaction.invoice_id)
        invoice_service.assert_invoice_open(invoice)
        invoice_service.remove_amount(invoice, transaction.amount)
    else:
        account = _get_owned_account(user_id, transaction.account_id)
        if transaction.is_paid:
            adjust_account_balance(account.id, -_signed_amount(transaction.type, transaction.amount))

    db.session.delete(transaction)
    db.session.commit()
