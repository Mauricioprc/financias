"""Calendário combinado de contas a vencer: faturas de cartão não pagas
com vencimento na janela + próximas ocorrências de recorrências ativas.
Nenhuma persistência — cálculo on-the-fly, sem tabela nova."""

from datetime import date, timedelta

from app.extensions import db
from app.models.credit_card import CreditCard
from app.models.invoice import Invoice
from app.models.recurring_transaction import RecurringTransaction
from app.services.exceptions import ValidationError
from app.services.invoice_service import compute_invoice_period
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

    # Cartões carregados sob demanda (só recorrências com credit_card_id
    # precisam) — mesmo padrão de join manual usado acima pras faturas.
    cards_by_id: dict[int, CreditCard] = {}

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
                if recurring.credit_card_id is None:
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
                else:
                    # Recorrência lançada no cartão: não mostra como
                    # "vencimento" solto (duplicaria a fatura, que já é
                    # surfaced acima) — mostra que ela vai entrar na fatura
                    # que fecha na data calculada, e só se essa fatura ainda
                    # não existir de verdade (senão o loop de faturas já
                    # cobre esse valor).
                    card = cards_by_id.get(recurring.credit_card_id)
                    if card is None:
                        card = db.session.get(CreditCard, recurring.credit_card_id)
                        cards_by_id[recurring.credit_card_id] = card
                    reference_month, closing_date, _due_date = compute_invoice_period(
                        occurrence, card.closing_day, card.due_day
                    )
                    existing_invoice = (
                        db.session.query(Invoice.id)
                        .filter_by(
                            user_id=user_id,
                            credit_card_id=card.id,
                            reference_month=reference_month,
                        )
                        .first()
                    )
                    if existing_invoice is None:
                        bills.append(
                            {
                                "type": "recurring_on_invoice",
                                "date": closing_date,
                                "label": (
                                    f"{recurring.description} entrará na fatura {card.name} "
                                    f"(fecha {closing_date.strftime('%d/%m')})"
                                ),
                                "amount": recurring.amount,
                                "reference_id": recurring.id,
                            }
                        )
            cursor = occurrence

    bills.sort(key=lambda bill: bill["date"])
    return bills
