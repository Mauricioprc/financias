"""Calendário combinado de contas a vencer: faturas de cartão não pagas
com vencimento na janela + próximas ocorrências de recorrências ativas.
Nenhuma persistência — cálculo on-the-fly, sem tabela nova."""

from datetime import date, timedelta

from app.extensions import db
from app.models.credit_card import CreditCard
from app.models.invoice import Invoice
from app.models.recurring_transaction import RecurringTransaction
from app.services.exceptions import ValidationError
from app.services.recurring_transaction_service import next_occurrence

MAX_DAYS = 90


def list_upcoming_bills(user_id: int, days: int = 30) -> list[dict]:
    if days > MAX_DAYS:
        raise ValidationError(f"days não pode ser maior que {MAX_DAYS}.")

    today = date.today()
    horizon = today + timedelta(days=days)

    bills: list[dict] = []

    # Faturas de cartão não pagas vencendo na janela. Join manual (não há
    # relationship() nos models deste projeto) só pra pegar o nome do
    # cartão sem uma query extra por fatura.
    invoice_rows = (
        db.session.query(Invoice, CreditCard.name)
        .join(CreditCard, CreditCard.id == Invoice.credit_card_id)
        .filter(
            Invoice.user_id == user_id,
            Invoice.status != "paid",
            Invoice.due_date >= today,
            Invoice.due_date <= horizon,
        )
        .all()
    )
    for invoice, card_name in invoice_rows:
        bills.append(
            {
                "type": "invoice",
                "date": invoice.due_date,
                "label": card_name,
                "amount": invoice.total_amount - invoice.paid_amount,
                "reference_id": invoice.id,
            }
        )

    # Próximas ocorrências de recorrências ativas — mesmo loop de
    # insights_service.forecast_account_balance, reaproveitando
    # next_occurrence (não duplica a lógica de cálculo de data).
    recurrings = (
        db.session.query(RecurringTransaction).filter_by(user_id=user_id, is_active=True).all()
    )
    for recurring in recurrings:
        cursor = recurring.last_generated
        while True:
            occurrence = next_occurrence(recurring, cursor)
            if occurrence > horizon:
                break
            if recurring.end_date is not None and occurrence > recurring.end_date:
                break
            if occurrence >= today:
                signed_amount = (
                    recurring.amount if recurring.type == "income" else -recurring.amount
                )
                bills.append(
                    {
                        "type": "recurring",
                        "date": occurrence,
                        "label": recurring.description,
                        "amount": signed_amount,
                        "reference_id": recurring.id,
                    }
                )
            cursor = occurrence

    bills.sort(key=lambda bill: bill["date"])
    return bills
