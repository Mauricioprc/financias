import calendar
from datetime import date, datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.models.account import Account
from app.models.credit_card import CreditCard
from app.models.invoice import Invoice
from app.models.transaction import Transaction
from app.services.exceptions import ConflictError, NotFoundError, ValidationError


def _add_months(year: int, month: int, months: int) -> tuple[int, int]:
    total = (year * 12) + (month - 1) + months
    return total // 12, (total % 12) + 1


def _clamped_date(year: int, month: int, day: int) -> date:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last_day))


def compute_invoice_period(
    purchase_date: date, closing_day: int, due_day: int
) -> tuple[date, date, date]:
    """Retorna (reference_month, closing_date, due_date) para uma compra.

    Se a compra ocorre até o dia de fechamento do mês, ela entra na fatura
    que fecha naquele mês; caso contrário, entra na fatura do mês seguinte.
    """
    closing_date_this_month = _clamped_date(purchase_date.year, purchase_date.month, closing_day)

    if purchase_date.day <= closing_date_this_month.day:
        ref_year, ref_month = purchase_date.year, purchase_date.month
    else:
        ref_year, ref_month = _add_months(purchase_date.year, purchase_date.month, 1)

    closing_date_ = _clamped_date(ref_year, ref_month, closing_day)

    if due_day <= closing_date_.day:
        due_year, due_month = _add_months(ref_year, ref_month, 1)
    else:
        due_year, due_month = ref_year, ref_month
    due_date_ = _clamped_date(due_year, due_month, due_day)

    reference_month = date(ref_year, ref_month, 1)
    return reference_month, closing_date_, due_date_


def get_or_create_open_invoice(
    user_id: int, credit_card: CreditCard, purchase_date: date
) -> Invoice:
    reference_month, closing_date_, due_date_ = compute_invoice_period(
        purchase_date, credit_card.closing_day, credit_card.due_day
    )

    invoice = (
        db.session.query(Invoice)
        .filter_by(user_id=user_id, credit_card_id=credit_card.id, reference_month=reference_month)
        .first()
    )
    if invoice is not None:
        return invoice

    invoice = Invoice(
        user_id=user_id,
        credit_card_id=credit_card.id,
        reference_month=reference_month,
        closing_date=closing_date_,
        due_date=due_date_,
        total_amount=Decimal(0),
        status="open",
    )
    db.session.add(invoice)
    db.session.flush()
    return invoice


def assert_invoice_open(invoice: Invoice) -> None:
    if invoice.status != "open":
        raise ConflictError(
            "Esta fatura já está fechada ou paga e não aceita novas alterações."
        )


def add_amount(invoice: Invoice, amount: Decimal) -> None:
    invoice.total_amount += amount


def remove_amount(invoice: Invoice, amount: Decimal) -> None:
    invoice.total_amount -= amount


def list_invoices(
    user_id: int, credit_card_id: int | None = None, status: str | None = None
) -> list[Invoice]:
    query = db.session.query(Invoice).filter_by(user_id=user_id)
    if credit_card_id is not None:
        query = query.filter(Invoice.credit_card_id == credit_card_id)
    if status is not None:
        query = query.filter(Invoice.status == status)
    return query.order_by(Invoice.reference_month.desc()).all()


def get_invoice(user_id: int, invoice_id: int) -> Invoice:
    invoice = db.session.query(Invoice).filter_by(id=invoice_id, user_id=user_id).first()
    if invoice is None:
        raise NotFoundError("Fatura não encontrada.")
    return invoice


def close_invoice(user_id: int, invoice_id: int) -> Invoice:
    invoice = get_invoice(user_id, invoice_id)
    if invoice.status != "open":
        raise ConflictError("Apenas faturas abertas podem ser fechadas.")
    invoice.status = "closed"
    db.session.commit()
    return invoice


def pay_invoice(user_id: int, invoice_id: int, account_id: int) -> Invoice:
    invoice = get_invoice(user_id, invoice_id)
    if invoice.status == "open":
        raise ConflictError("Feche a fatura antes de registrar o pagamento.")
    if invoice.status == "paid":
        raise ConflictError("Esta fatura já foi paga.")
    if invoice.total_amount <= 0:
        raise ValidationError("Fatura sem valor a pagar.")

    account = db.session.query(Account).filter_by(id=account_id, user_id=user_id).first()
    if account is None:
        raise ValidationError("account_id inválido para este usuário.")

    payment_transaction = Transaction(
        user_id=user_id,
        account_id=account_id,
        category_id=None,
        credit_card_id=invoice.credit_card_id,
        invoice_id=None,
        type="expense",
        description=f"Pagamento de fatura de cartão (fatura #{invoice.id})",
        amount=invoice.total_amount,
        date=datetime.now(timezone.utc).date(),
        is_paid=True,
        notes=None,
    )
    db.session.add(payment_transaction)
    account.current_balance -= invoice.total_amount

    invoice.status = "paid"
    invoice.paid_at = datetime.now(timezone.utc)
    db.session.commit()
    return invoice
