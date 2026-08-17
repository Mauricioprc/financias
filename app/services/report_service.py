"""Agregações para a tela de Relatórios e os gráficos da Home.

Substitui os cálculos que antes eram feitos no client (ver static/js/reportData.js)
— a mesma lógica migra para cá para poder ser reaproveitada pelo bot do WhatsApp
no futuro. Agregação é feita em Python (não em SQL específico do dialeto) para
manter os services portáveis entre o Postgres de produção e o SQLite usado nos
testes.
"""

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from app.extensions import db
from app.models.account import Account
from app.models.category import Category
from app.models.transaction import Transaction


def _signed_amount(type_: str, amount: Decimal) -> Decimal:
    return amount if type_ == "income" else -amount


def _month_start(year: int, month: int) -> date:
    return date(year, month, 1)


def _add_months(start: date, offset: int) -> date:
    month_index = start.month - 1 + offset
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def balance_history(user_id: int, days: int = 30) -> list[dict]:
    """Saldo total (soma de todas as contas) ao final de cada um dos últimos
    `days` dias, reconstruído a partir do saldo atual e das transações já
    efetivadas (is_paid) nesse período."""
    today = date.today()
    start = today - timedelta(days=days - 1)
    day_list = [start + timedelta(days=i) for i in range(days)]

    total_balance = sum(
        (a.current_balance for a in db.session.query(Account).filter_by(user_id=user_id)),
        Decimal("0.00"),
    )

    transactions = (
        db.session.query(Transaction.date, Transaction.type, Transaction.amount)
        .filter(
            Transaction.user_id == user_id,
            Transaction.is_paid.is_(True),
            Transaction.date >= start,
            Transaction.date <= today,
        )
        .all()
    )
    net_by_day: dict[date, Decimal] = {}
    for tx_date, tx_type, amount in transactions:
        net_by_day[tx_date] = net_by_day.get(tx_date, Decimal("0.00")) + _signed_amount(
            tx_type, amount
        )

    balances: list[Decimal] = [Decimal("0.00")] * days
    balances[-1] = total_balance
    for i in range(days - 1, 0, -1):
        balances[i - 1] = balances[i] - net_by_day.get(day_list[i], Decimal("0.00"))

    return [{"date": d, "balance": balances[i]} for i, d in enumerate(day_list)]


def category_breakdown(user_id: int, month: str, type: str = "expense") -> list[dict]:
    """Total gasto (ou recebido) por categoria em um mês `YYYY-MM`, do maior
    para o menor."""
    year_str, month_str = month.split("-")
    year, mo = int(year_str), int(month_str)
    start = _month_start(year, mo)
    end = date(year, mo, monthrange(year, mo)[1])

    rows = (
        db.session.query(Transaction.category_id, Transaction.amount)
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == type,
            Transaction.date >= start,
            Transaction.date <= end,
        )
        .all()
    )

    totals: dict[int | None, Decimal] = {}
    for category_id, amount in rows:
        totals[category_id] = totals.get(category_id, Decimal("0.00")) + amount

    category_ids = [cid for cid in totals if cid is not None]
    names = {}
    if category_ids:
        names = {
            c.id: c.name
            for c in db.session.query(Category).filter(Category.id.in_(category_ids))
        }

    breakdown = [
        {
            "category_id": category_id,
            "category_name": names.get(category_id, "Sem categoria"),
            "total": total,
        }
        for category_id, total in totals.items()
    ]
    breakdown.sort(key=lambda item: item["total"], reverse=True)
    return breakdown


def income_vs_expense_by_month(user_id: int, months: int = 12) -> list[dict]:
    """Receita x despesa por mês, últimos `months` meses (incluindo o atual)."""
    today = date.today()
    current_start = _month_start(today.year, today.month)
    month_starts = [_add_months(current_start, -offset) for offset in range(months - 1, -1, -1)]
    range_start = month_starts[0]

    rows = (
        db.session.query(Transaction.date, Transaction.type, Transaction.amount)
        .filter(Transaction.user_id == user_id, Transaction.date >= range_start)
        .all()
    )

    totals = {ms: {"income": Decimal("0.00"), "expense": Decimal("0.00")} for ms in month_starts}
    for tx_date, tx_type, amount in rows:
        key = _month_start(tx_date.year, tx_date.month)
        if key in totals and tx_type in ("income", "expense"):
            totals[key][tx_type] += amount

    return [
        {"month": ms.strftime("%Y-%m"), "income": totals[ms]["income"], "expense": totals[ms]["expense"]}
        for ms in month_starts
    ]
