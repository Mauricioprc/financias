from datetime import date, datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.models.account import Account
from app.models.credit_card import CreditCard
from app.models.invoice import Invoice
from app.models.transaction import Transaction
from app.services.exceptions import ConflictError, NotFoundError, ValidationError
from app.utils.datetime_utils import add_months, clamped_date


def compute_invoice_period(
    purchase_date: date, closing_day: int, due_day: int
) -> tuple[date, date, date]:
    """Retorna (reference_month, closing_date, due_date) para uma compra.

    Se a compra ocorre antes do dia de fechamento do mês, ela entra na
    fatura que fecha naquele mês; no próprio dia de fechamento (ou depois),
    já entra na fatura do mês seguinte — o dia do fechamento é o primeiro
    dia do novo ciclo, não o último do que está fechando.
    """
    closing_date_this_month = clamped_date(purchase_date.year, purchase_date.month, closing_day)

    if purchase_date.day < closing_date_this_month.day:
        ref_year, ref_month = purchase_date.year, purchase_date.month
    else:
        ref_year, ref_month = add_months(purchase_date.year, purchase_date.month, 1)

    closing_date_ = clamped_date(ref_year, ref_month, closing_day)

    if due_day <= closing_date_.day:
        due_year, due_month = add_months(ref_year, ref_month, 1)
    else:
        due_year, due_month = ref_year, ref_month
    due_date_ = clamped_date(due_year, due_month, due_day)

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

    # Se pagamentos parciais feitos ainda com a fatura aberta (register_payment)
    # já cobriram o total antes mesmo do fechamento, ela nasce fechada já paga
    # — sem isso, ficaria "closed" com saldo zero pra sempre, nunca virando "paid".
    if invoice.paid_amount >= invoice.total_amount and invoice.total_amount > 0:
        invoice.status = "paid"
        invoice.paid_at = datetime.now(timezone.utc)

    db.session.commit()
    return invoice


def register_payment(user_id: int, invoice_id: int, account_id: int, amount: Decimal) -> Invoice:
    """Pagamento (total ou parcial) de uma fatura `open` ou `closed`. Abate
    de `paid_amount` sem mexer em `total_amount` (que continua sendo só a
    soma das compras) e sempre gera uma `Transaction` de histórico — mesmo
    padrão de rastreabilidade que `pay_invoice` já usava, só que sem exigir
    que a fatura esteja fechada nem que o valor seja o total inteiro.

    Uma fatura `open` que recebe pagamento igual ao total corrente **não**
    vira `paid` na hora — ela ainda pode receber novas compras até fechar;
    ver `close_invoice` para a reavaliação nesse momento.
    """
    invoice = get_invoice(user_id, invoice_id)
    if invoice.status == "paid":
        raise ConflictError("Esta fatura já foi paga.")
    if amount <= 0:
        raise ValidationError("O valor do pagamento deve ser maior que zero.")

    remaining = invoice.total_amount - invoice.paid_amount
    if amount > remaining:
        raise ValidationError(
            f"O valor do pagamento não pode ser maior que o saldo devedor da fatura ({remaining})."
        )

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
        amount=amount,
        date=datetime.now(timezone.utc).date(),
        is_paid=True,
        notes=None,
    )
    db.session.add(payment_transaction)
    account.current_balance -= amount
    invoice.paid_amount += amount

    if invoice.status == "closed" and invoice.paid_amount >= invoice.total_amount:
        invoice.status = "paid"
        invoice.paid_at = datetime.now(timezone.utc)

    db.session.commit()
    return invoice


def pay_invoice(user_id: int, invoice_id: int, account_id: int) -> Invoice:
    """Pagamento integral do saldo restante — só permitido com a fatura já
    fechada (mesma regra de sempre). Pra pagar parte do valor com a fatura
    ainda aberta, ver `register_payment`."""
    invoice = get_invoice(user_id, invoice_id)
    if invoice.status == "open":
        raise ConflictError("Feche a fatura antes de registrar o pagamento.")
    if invoice.status == "paid":
        raise ConflictError("Esta fatura já foi paga.")

    remaining = invoice.total_amount - invoice.paid_amount
    if remaining <= 0:
        raise ValidationError("Fatura sem valor a pagar.")

    return register_payment(user_id, invoice_id, account_id, remaining)
