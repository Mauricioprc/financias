"""Orçamento por categoria: um limite mensal recorrente (não por mês
específico — vale até o usuário mudar, mesma filosofia de
RecurringTransaction)."""

import calendar
from datetime import date
from decimal import Decimal

from sqlalchemy import func

from app.extensions import db
from app.models.budget import Budget
from app.models.category import Category
from app.models.transaction import Transaction
from app.services import category_service
from app.services.exceptions import ConflictError, NotFoundError
from app.services.insights_service import month_period_bounds

CENTS = Decimal("0.01")


def list_budgets(user_id: int) -> list[Budget]:
    return db.session.query(Budget).filter_by(user_id=user_id).order_by(Budget.id).all()


def get_budget(user_id: int, budget_id: int) -> Budget:
    budget = db.session.query(Budget).filter_by(id=budget_id, user_id=user_id).first()
    if budget is None:
        raise NotFoundError("Orçamento não encontrado.")
    return budget


def create_budget(user_id: int, category_id: int, monthly_limit: Decimal) -> Budget:
    category_service.get_category(user_id, category_id)  # 404 se não for do usuário

    existing = (
        db.session.query(Budget).filter_by(user_id=user_id, category_id=category_id).first()
    )
    if existing is not None:
        # Checagem explícita em vez de deixar a UniqueConstraint estourar
        # um IntegrityError cru — mesmo padrão de auth_service.register_user
        # pra email duplicado: erro tratado (409), não um 500.
        raise ConflictError("Já existe um orçamento cadastrado para esta categoria.")

    budget = Budget(user_id=user_id, category_id=category_id, monthly_limit=monthly_limit)
    db.session.add(budget)
    db.session.commit()
    return budget


def update_budget(user_id: int, budget_id: int, **fields) -> Budget:
    budget = get_budget(user_id, budget_id)
    if fields.get("category_id") is not None and fields["category_id"] != budget.category_id:
        category_service.get_category(user_id, fields["category_id"])
        clash = (
            db.session.query(Budget)
            .filter_by(user_id=user_id, category_id=fields["category_id"])
            .first()
        )
        if clash is not None:
            raise ConflictError("Já existe um orçamento cadastrado para esta categoria.")
    for key, value in fields.items():
        if value is not None:
            setattr(budget, key, value)
    db.session.commit()
    return budget


def delete_budget(user_id: int, budget_id: int) -> None:
    budget = get_budget(user_id, budget_id)
    db.session.delete(budget)
    db.session.commit()


def get_budget_progress(user_id: int) -> list[dict]:
    """Pra cada Budget do usuário, quanto já foi gasto na categoria no mês
    corrente (dia 1 até hoje) frente ao limite mensal."""
    budgets = list_budgets(user_id)
    if not budgets:
        return []

    today = date.today()
    start, end = month_period_bounds(today, months_back=0)
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_remaining_in_month = days_in_month - today.day

    category_ids = [b.category_id for b in budgets]
    rows = (
        db.session.query(Transaction.category_id, func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == "expense",
            Transaction.category_id.in_(category_ids),
            Transaction.date >= start,
            Transaction.date <= end,
        )
        .group_by(Transaction.category_id)
        .all()
    )
    spent_by_category = {cat_id: Decimal(total) for cat_id, total in rows}

    category_names = {
        c.id: c.name
        for c in db.session.query(Category).filter(Category.id.in_(category_ids)).all()
    }

    progress = []
    for budget in budgets:
        spent = spent_by_category.get(budget.category_id, Decimal("0.00")).quantize(CENTS)
        limit = budget.monthly_limit
        remaining = (limit - spent).quantize(CENTS)
        pct_used = (spent / limit * 100).quantize(CENTS) if limit > 0 else Decimal("0.00")

        progress.append(
            {
                "budget_id": budget.id,
                "category_id": budget.category_id,
                "category_name": category_names.get(budget.category_id, ""),
                "monthly_limit": limit,
                "current_month_total": spent,
                "pct_used": pct_used,
                "remaining": remaining,
                "is_over_budget": spent > limit,
                "days_remaining_in_month": days_remaining_in_month,
            }
        )

    return progress
