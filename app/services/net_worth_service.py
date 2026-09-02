"""Patrimônio líquido: histórico reconstruído (só contas) e "hoje"
(contas + investimentos - faturas em aberto). Tudo calculado on-the-fly a
partir do dado que já existe — sem tabela de snapshot, sem job agendado.
"""

import calendar
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func

from app.extensions import db
from app.models.account import Account
from app.models.credit_card import CreditCard
from app.models.invoice import Invoice
from app.models.investment import Investment
from app.models.transaction import Transaction
from app.models.transfer import Transfer
from app.services.exceptions import ValidationError
from app.utils.datetime_utils import add_months

CENTS = Decimal("0.01")
MIN_MONTHS = 1
MAX_MONTHS = 24


def _money(value) -> Decimal:
    return Decimal(value).quantize(CENTS)


def _end_of_month(reference: date) -> date:
    last_day = calendar.monthrange(reference.year, reference.month)[1]
    return date(reference.year, reference.month, last_day)


def _today() -> date:
    # UTC, não hora local: `Account.created_at` (TimestampMixin) é gravado
    # com `datetime.now(timezone.utc)` — comparar contra `date.today()`
    # (hora local) cria um descompasso de um dia perto da meia-noite pra
    # qualquer usuário em fuso atrás de UTC (ex.: conta criada "hoje" às
    # 23h50 local já apareceria com created_at de "amanhã" em UTC, ficando
    # de fora do corte do mês corrente por engano).
    return datetime.now(timezone.utc).date()


def _month_cutoffs(months: int) -> list[tuple[str, date]]:
    """[(label "YYYY-MM", data de corte), ...] do mais antigo pro mais
    recente. O mês corrente usa hoje como corte (ainda não fechou); os
    anteriores usam o último dia de cada mês."""
    today = _today()
    cutoffs = []
    for i in range(months - 1, -1, -1):
        year, month = add_months(today.year, today.month, -i)
        cutoff = today if i == 0 else _end_of_month(date(year, month, 1))
        cutoffs.append((f"{year:04d}-{month:02d}", cutoff))
    return cutoffs


def _load_balance_events(
    user_id: int, account_ids: list[int]
) -> list[tuple[date, int, Decimal]]:
    """Todo evento que muda o saldo de uma das `account_ids`, como
    (data, account_id, delta), ordenado por data. Carregado UMA VEZ pro
    usuário inteiro (não uma query por conta por mês) — o chamador varre
    essa lista uma única vez, acumulando por conta, amostrando o total nas
    datas de corte de cada mês. Isso troca N contas × M meses queries por
    2 queries + uma varredura em memória.

    Mesmo filtro que `current_balance` usa de verdade (ver
    transaction_service.create_transaction/update_transaction): só
    Transaction sem cartão vinculado (credit_card_id IS NULL) e paga
    (is_paid) mexe em saldo de conta — compra de cartão só afeta a conta
    quando a fatura é paga, o que já vira uma Transaction normal (sem
    credit_card_id) de pagamento.
    """
    account_id_set = set(account_ids)
    events: list[tuple[date, int, Decimal]] = []

    tx_rows = (
        db.session.query(Transaction.date, Transaction.account_id, Transaction.type, Transaction.amount)
        .filter(
            Transaction.user_id == user_id,
            Transaction.account_id.in_(account_ids),
            Transaction.credit_card_id.is_(None),
            Transaction.is_paid.is_(True),
        )
        .all()
    )
    for tx_date, account_id, type_, amount in tx_rows:
        delta = amount if type_ == "income" else -amount
        events.append((tx_date, account_id, delta))

    transfer_rows = (
        db.session.query(Transfer.date, Transfer.from_account_id, Transfer.to_account_id, Transfer.amount)
        .filter(
            Transfer.user_id == user_id,
            (Transfer.from_account_id.in_(account_ids)) | (Transfer.to_account_id.in_(account_ids)),
        )
        .all()
    )
    for transfer_date, from_id, to_id, amount in transfer_rows:
        if from_id in account_id_set:
            events.append((transfer_date, from_id, -amount))
        if to_id in account_id_set:
            events.append((transfer_date, to_id, amount))

    events.sort(key=lambda event: event[0])
    return events


def compute_net_worth_history(user_id: int, months: int = 12) -> list[dict]:
    """Soma de saldo de todas as contas não-arquivadas, reconstruída pro
    fim de cada um dos últimos `months` meses.

    Limitação deliberada: uma conta só entra na soma a partir da data em
    que ela foi *criada* no sistema (`account.created_at`), nunca antes —
    se o usuário cadastrou uma conta em setembro com saldo inicial de
    R$5.000 representando "quanto eu já tinha", não há como saber quanto
    era isso em julho. O histórico não inventa esse dado, só passa a
    incluir a conta a partir de quando ela existe.
    """
    if not (MIN_MONTHS <= months <= MAX_MONTHS):
        raise ValidationError(f"months deve estar entre {MIN_MONTHS} e {MAX_MONTHS}.")

    accounts = db.session.query(Account).filter_by(user_id=user_id, is_archived=False).all()
    cutoffs = _month_cutoffs(months)

    if not accounts:
        return [{"month": label, "total_accounts_balance": Decimal("0.00")} for label, _ in cutoffs]

    account_ids = [a.id for a in accounts]
    balances = {a.id: a.initial_balance for a in accounts}
    created_dates = {a.id: a.created_at.date() for a in accounts}

    events = _load_balance_events(user_id, account_ids)

    results = []
    event_idx = 0
    event_count = len(events)
    for label, cutoff in cutoffs:
        while event_idx < event_count and events[event_idx][0] <= cutoff:
            _, account_id, delta = events[event_idx]
            balances[account_id] += delta
            event_idx += 1

        total = sum(
            (balances[a.id] for a in accounts if created_dates[a.id] <= cutoff),
            Decimal("0.00"),
        )
        results.append({"month": label, "total_accounts_balance": _money(total)})

    return results


def compute_net_worth_today(user_id: int) -> dict:
    """Patrimônio de hoje, completo (ao contrário do histórico mensal, que
    é só contas): contas + investimentos - saldo devedor de faturas em
    aberto. Componentes expostos separados, mesma filosofia de
    transparência de `insights_service.forecast_account_balance`."""
    accounts_total = _money(
        db.session.query(func.coalesce(func.sum(Account.current_balance), 0))
        .filter_by(user_id=user_id, is_archived=False)
        .scalar()
    )
    investments_total = _money(
        db.session.query(func.coalesce(func.sum(Investment.current_amount), 0))
        .filter_by(user_id=user_id)
        .scalar()
    )
    unpaid_invoices_total = _money(
        db.session.query(func.coalesce(func.sum(Invoice.total_amount - Invoice.paid_amount), 0))
        .join(CreditCard, CreditCard.id == Invoice.credit_card_id)
        .filter(
            Invoice.user_id == user_id,
            Invoice.status != "paid",
            CreditCard.is_archived.is_(False),
        )
        .scalar()
    )

    net_worth = _money(accounts_total + investments_total - unpaid_invoices_total)

    return {
        "accounts_total": accounts_total,
        "investments_total": investments_total,
        "unpaid_invoices_total": unpaid_invoices_total,
        "net_worth": net_worth,
    }
