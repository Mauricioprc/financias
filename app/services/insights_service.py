"""Insights financeiros — análise descritiva pura sobre o dado do próprio
usuário (nunca recomendação de investimento/alocação). Cada função devolve
dado estruturado (números, componentes explícitos) — nenhuma mensagem de
texto pronta é gerada aqui; formatação/copy fica pro frontend.
"""

import calendar
import math
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import case, func

from app.extensions import db
from app.models.account import Account
from app.models.category import Category
from app.models.credit_card import CreditCard
from app.models.invoice import Invoice
from app.models.recurring_transaction import RecurringTransaction
from app.models.transaction import Transaction
from app.services import account_service, goal_service, invoice_service
from app.services.recurring_transaction_service import next_occurrence
from app.utils.datetime_utils import add_months, clamped_date

CENTS = Decimal("0.01")

# Heurística simples (não z-score/desvio padrão): histórico de finança
# pessoal costuma ser curto demais (poucos meses) pra estatística mais
# sofisticada ser confiável — um categoria com 3-4 meses de dado não dá
# amostra suficiente pra calcular desvio padrão com significância. Um
# limiar percentual fixo sobre a média é mais legível e igualmente honesto
# sobre suas limitações. Decisão deliberada, não simplificação por preguiça.
ANOMALY_THRESHOLD_PCT = Decimal("1.4")  # 40% acima da média trailing = severidade "alta"
ANOMALY_MODERATE_THRESHOLD_PCT = Decimal("1.2")  # 20% acima = severidade "moderada"

# Mesma heurística de limiar percentual fixo, aplicada à projeção de fatura.
INVOICE_TREND_THRESHOLD_PCT = Decimal("1.3")


def _money(value) -> Decimal:
    return Decimal(value).quantize(CENTS)


def _pct(new_value: Decimal, base_value: Decimal) -> Decimal | None:
    """Variação percentual de `base_value` pra `new_value` (ex.: 12.50 =
    +12,5%). `None` quando `base_value` é zero — variação percentual não é
    definida nesse caso, não faz sentido inventar um número."""
    if base_value == 0:
        return None
    return _money(((new_value - base_value) / base_value) * 100)


def _end_of_month(reference: date) -> date:
    last_day = calendar.monthrange(reference.year, reference.month)[1]
    return date(reference.year, reference.month, last_day)


def _months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)


def month_period_bounds(reference: date, months_back: int) -> tuple[date, date]:
    """(início, fim) do "recorte de dia equivalente" do mês `months_back`
    meses antes de `reference`: do dia 1 até o dia `reference.day` daquele
    mês (com clamp — ex.: dia 31 vira o último dia real do mês em questão).
    `months_back=0` dá o mês corrente, do dia 1 até hoje.

    Pública porque `budget_service.get_budget_progress` reaproveita o
    mesmo recorte (mês corrente, dia 1 até hoje) pra somar gasto por
    categoria — mesmo motivo de `next_occurrence` ser pública em
    `recurring_transaction_service`."""
    year, month = add_months(reference.year, reference.month, -months_back)
    start = date(year, month, 1)
    end = clamped_date(year, month, reference.day)
    return start, end


# ---------- 1. Previsão de saldo ----------


def forecast_account_balance(user_id: int, account_id: int) -> dict:
    account = account_service.get_account(user_id, account_id)
    today = date.today()
    end_of_month = _end_of_month(today)
    days_remaining = (end_of_month - today).days
    current_balance = account.current_balance

    if days_remaining == 0:
        zero = Decimal("0.00")
        return {
            "account_id": account.id,
            "current_balance": _money(current_balance),
            "projected_end_of_month_balance": _money(current_balance),
            "days_remaining": 0,
            "components": {
                "recurring_expected": zero,
                "upcoming_invoice_debits": zero,
                "variable_spending_estimate": zero,
            },
        }

    tomorrow = today + timedelta(days=1)

    # --- recorrências esperadas (amanhã até o fim do mês) ---
    # Só recorrências SEM cartão vinculado: uma recorrência com cartão
    # (assinatura) não debita a conta na hora que ocorre — ela vira compra
    # numa fatura, que só afeta a conta quando paga (due_date). Essa parte
    # já é coberta pelo componente `upcoming_invoice_debits` abaixo, que
    # olha faturas existentes com due_date na janela; incluir a recorrência
    # aqui também contaria o mesmo dinheiro duas vezes (ou na data errada,
    # já que a fatura em geral vence no mês seguinte à compra).
    recurring_expected = Decimal("0.00")
    recurrings = (
        db.session.query(RecurringTransaction)
        .filter_by(user_id=user_id, account_id=account_id, is_active=True)
        .filter(RecurringTransaction.credit_card_id.is_(None))
        .all()
    )
    for recurring in recurrings:
        cursor = recurring.last_generated
        while True:
            occurrence = next_occurrence(recurring, cursor)
            if occurrence > end_of_month:
                break
            if recurring.end_date is not None and occurrence > recurring.end_date:
                break
            if occurrence >= tomorrow:
                signed = recurring.amount if recurring.type == "income" else -recurring.amount
                recurring_expected += signed
            cursor = occurrence

    # --- faturas de cartão vinculadas a essa conta, vencendo até o fim do mês ---
    upcoming_invoice_debits = Decimal("0.00")
    linked_card_ids = [
        c.id
        for c in db.session.query(CreditCard.id)
        .filter_by(user_id=user_id, account_id=account_id)
        .all()
    ]
    if linked_card_ids:
        invoices = (
            db.session.query(Invoice)
            .filter(
                Invoice.user_id == user_id,
                Invoice.credit_card_id.in_(linked_card_ids),
                Invoice.due_date >= today,
                Invoice.due_date <= end_of_month,
                Invoice.status != "paid",
            )
            .all()
        )
        for inv in invoices:
            remaining = inv.total_amount - inv.paid_amount
            upcoming_invoice_debits -= remaining

    # --- média diária de gasto/receita variável (não recorrente, não cartão) ---
    # "Variável" = Transaction com recurring_id IS NULL e credit_card_id IS
    # NULL (ambos os campos existem no model) — exclui tanto o que já foi
    # contabilizado acima (recorrências) quanto compras de cartão (que não
    # tocam current_balance na hora, só no pagamento da fatura).
    current_month_start = date(today.year, today.month, 1)
    three_months_start_year, three_months_start_month = add_months(today.year, today.month, -3)
    three_months_start = date(three_months_start_year, three_months_start_month, 1)
    three_months_end = current_month_start - timedelta(days=1)
    total_days = (three_months_end - three_months_start).days + 1

    variable_spending_estimate = Decimal("0.00")
    if total_days > 0:
        variable_sum = (
            db.session.query(
                func.coalesce(
                    func.sum(
                        case(
                            (Transaction.type == "income", Transaction.amount),
                            else_=-Transaction.amount,
                        )
                    ),
                    0,
                )
            )
            .filter(
                Transaction.user_id == user_id,
                Transaction.account_id == account_id,
                Transaction.recurring_id.is_(None),
                Transaction.credit_card_id.is_(None),
                Transaction.is_paid.is_(True),
                Transaction.date >= three_months_start,
                Transaction.date <= three_months_end,
            )
            .scalar()
        )
        avg_daily = Decimal(variable_sum) / total_days
        variable_spending_estimate = _money(avg_daily * days_remaining)

    projected = _money(
        current_balance + recurring_expected + upcoming_invoice_debits + variable_spending_estimate
    )

    return {
        "account_id": account.id,
        "current_balance": _money(current_balance),
        "projected_end_of_month_balance": projected,
        "days_remaining": days_remaining,
        "components": {
            "recurring_expected": _money(recurring_expected),
            "upcoming_invoice_debits": _money(upcoming_invoice_debits),
            "variable_spending_estimate": variable_spending_estimate,
        },
    }


# ---------- 2. Comparação de gastos por categoria ----------


def compare_category_spending(user_id: int) -> list[dict]:
    today = date.today()
    four_months_start_year, four_months_start_month = add_months(today.year, today.month, -3)
    four_months_start = date(four_months_start_year, four_months_start_month, 1)

    eligible_category_ids = {
        row[0]
        for row in db.session.query(Transaction.category_id)
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == "expense",
            Transaction.category_id.isnot(None),
            Transaction.date >= four_months_start,
        )
        .distinct()
        .all()
    }
    if not eligible_category_ids:
        return []

    def period_sums(months_back: int) -> dict[int, Decimal]:
        start, end = month_period_bounds(today, months_back)
        rows = (
            db.session.query(
                Transaction.category_id, func.coalesce(func.sum(Transaction.amount), 0)
            )
            .filter(
                Transaction.user_id == user_id,
                Transaction.type == "expense",
                Transaction.category_id.in_(eligible_category_ids),
                Transaction.date >= start,
                Transaction.date <= end,
            )
            .group_by(Transaction.category_id)
            .all()
        )
        return {cat_id: Decimal(total) for cat_id, total in rows}

    current = period_sums(0)
    last_month = period_sums(1)
    trailing = [period_sums(k) for k in (2, 3, 4)]

    category_names = {
        c.id: c.name
        for c in db.session.query(Category).filter(Category.id.in_(eligible_category_ids)).all()
    }

    results = []
    for cat_id in eligible_category_ids:
        cur = current.get(cat_id, Decimal("0.00"))
        last = last_month.get(cat_id, Decimal("0.00"))
        trailing_vals = [t.get(cat_id, Decimal("0.00")) for t in trailing]
        avg3 = sum(trailing_vals) / 3

        results.append(
            {
                "category_id": cat_id,
                "category_name": category_names.get(cat_id, ""),
                "current_month_total": _money(cur),
                "same_period_last_month_total": _money(last),
                "trailing_3_month_avg": _money(avg3),
                "pct_change_vs_last_month": _pct(cur, last),
                "pct_change_vs_avg": _pct(cur, avg3),
            }
        )

    results.sort(key=lambda r: r["current_month_total"], reverse=True)
    return results


# ---------- 3. Alertas de gasto fora do padrão ----------


def detect_spending_anomalies(user_id: int) -> list[dict]:
    today = date.today()
    days_elapsed = today.day
    days_in_month = calendar.monthrange(today.year, today.month)[1]

    anomalies = []
    for item in compare_category_spending(user_id):
        avg3 = item["trailing_3_month_avg"]
        if avg3 <= 0:
            continue

        projected = _money((item["current_month_total"] / days_elapsed) * days_in_month)
        ratio = projected / avg3

        if ratio > ANOMALY_THRESHOLD_PCT:
            severity = "alta"
        elif ratio > ANOMALY_MODERATE_THRESHOLD_PCT:
            severity = "moderada"
        else:
            continue

        anomalies.append(
            {
                "category_id": item["category_id"],
                "category_name": item["category_name"],
                "current_month_total": item["current_month_total"],
                "projected_month_total": projected,
                "trailing_3_month_avg": avg3,
                "pct_above_avg": _money((ratio - 1) * 100),
                "severity": severity,
            }
        )

    return anomalies


# ---------- 4. Alerta de fatura subindo rápido ----------


def detect_invoice_trend_alerts(user_id: int) -> list[dict]:
    today = date.today()
    cards = db.session.query(CreditCard).filter_by(user_id=user_id, is_archived=False).all()

    alerts = []
    for card in cards:
        last_three = (
            db.session.query(Invoice)
            .filter(
                Invoice.user_id == user_id,
                Invoice.credit_card_id == card.id,
                Invoice.status.in_(("closed", "paid")),
            )
            .order_by(Invoice.reference_month.desc())
            .limit(3)
            .all()
        )
        if len(last_three) < 3:
            continue
        avg_of_last_3 = _money(sum((inv.total_amount for inv in last_three), Decimal(0)) / 3)
        if avg_of_last_3 <= 0:
            continue

        current_invoice = (
            db.session.query(Invoice)
            .filter_by(user_id=user_id, credit_card_id=card.id, status="open")
            .order_by(Invoice.reference_month.desc())
            .first()
        )
        if current_invoice is None or current_invoice.total_amount <= 0:
            continue

        reference_month, closing_date_, _due_date = invoice_service.compute_invoice_period(
            today, card.closing_day, card.due_day
        )
        # A fatura "open" tem que ser mesmo a do ciclo atual (evita
        # projetar em cima de uma fatura futura já com compras adiantadas).
        if current_invoice.reference_month != reference_month:
            continue

        prev_year, prev_month = add_months(closing_date_.year, closing_date_.month, -1)
        cycle_start = clamped_date(prev_year, prev_month, card.closing_day)
        total_days = (closing_date_ - cycle_start).days or 1
        elapsed_days = max(1, min((today - cycle_start).days, total_days))

        projected_total = _money((current_invoice.total_amount / elapsed_days) * total_days)
        ratio = projected_total / avg_of_last_3
        if ratio <= INVOICE_TREND_THRESHOLD_PCT:
            continue

        alerts.append(
            {
                "card_id": card.id,
                "card_name": card.name,
                "current_total": _money(current_invoice.total_amount),
                "projected_total": projected_total,
                "avg_of_last_3": avg_of_last_3,
                "pct_above_average": _money((ratio - 1) * 100),
            }
        )

    return alerts


# ---------- 5. Projeção de meta ----------


def project_goal_completion(user_id: int, goal_id: int) -> dict:
    """Aproximação grosseira: não existe histórico de contribuição
    (Goal.current_amount é só um valor acumulado, sem série temporal), então
    a "contribuição média mensal" é estimada dividindo o total acumulado
    pelo número de meses desde a criação da meta — não sabemos se o
    progresso foi constante, concentrado no início ou no fim.
    `is_rough_estimate` vem sempre `True` de propósito, pra essa limitação
    nunca ficar escondida do consumidor da API.
    """
    goal = goal_service.get_goal(user_id, goal_id)
    today = date.today()

    created = goal.created_at.date()
    months_elapsed = max(1, _months_between(created, today))
    avg_monthly_contribution = _money(goal.current_amount / months_elapsed)

    base = {
        "goal_id": goal.id,
        "current_amount": _money(goal.current_amount),
        "target_amount": _money(goal.target_amount),
        "target_date": goal.target_date,
        "avg_monthly_contribution": avg_monthly_contribution,
        "is_rough_estimate": True,
    }

    if avg_monthly_contribution <= 0:
        return {
            **base,
            "projected_completion_date": None,
            "reason": "sem contribuição detectável ainda",
            "on_track": None,
        }

    remaining = goal.target_amount - goal.current_amount
    months_to_complete = 0 if remaining <= 0 else math.ceil(remaining / avg_monthly_contribution)

    year, month = add_months(today.year, today.month, months_to_complete)
    projected_completion_date = clamped_date(year, month, today.day)

    on_track = None
    if goal.target_date is not None:
        on_track = projected_completion_date <= goal.target_date

    return {
        **base,
        "projected_completion_date": projected_completion_date,
        "reason": None,
        "on_track": on_track,
    }


# ---------- Agregado ----------


def build_insights_summary(user_id: int) -> dict:
    accounts = db.session.query(Account).filter_by(user_id=user_id, is_archived=False).all()
    return {
        "balance_forecasts": [forecast_account_balance(user_id, a.id) for a in accounts],
        "category_comparison": compare_category_spending(user_id),
        "spending_anomalies": detect_spending_anomalies(user_id),
        "invoice_trends": detect_invoice_trend_alerts(user_id),
    }
