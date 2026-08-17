from flask import Blueprint, jsonify

from app.api.decorators import require_user, validate_query
from app.schemas.report import (
    BalanceHistoryPointSchema,
    BalanceHistoryQuerySchema,
    CategoryBreakdownItemSchema,
    CategoryBreakdownQuerySchema,
    IncomeVsExpenseItemSchema,
    IncomeVsExpenseQuerySchema,
)
from app.services import report_service

bp = Blueprint("reports", __name__)

balance_history_query_schema = BalanceHistoryQuerySchema()
balance_history_out_schema = BalanceHistoryPointSchema()
category_breakdown_query_schema = CategoryBreakdownQuerySchema()
category_breakdown_out_schema = CategoryBreakdownItemSchema()
income_vs_expense_query_schema = IncomeVsExpenseQuerySchema()
income_vs_expense_out_schema = IncomeVsExpenseItemSchema()


@bp.route("/balance-history", methods=["GET"])
@require_user
@validate_query(balance_history_query_schema)
def balance_history_route(query, user_id):
    points = report_service.balance_history(user_id, days=query["days"])
    return jsonify(
        {
            "data": balance_history_out_schema.dump(points, many=True),
            "meta": {"days": query["days"]},
        }
    )


@bp.route("/category-breakdown", methods=["GET"])
@require_user
@validate_query(category_breakdown_query_schema)
def category_breakdown_route(query, user_id):
    items = report_service.category_breakdown(user_id, month=query["month"], type=query["type"])
    return jsonify(
        {
            "data": category_breakdown_out_schema.dump(items, many=True),
            "meta": {"month": query["month"], "type": query["type"]},
        }
    )


@bp.route("/income-vs-expense", methods=["GET"])
@require_user
@validate_query(income_vs_expense_query_schema)
def income_vs_expense_route(query, user_id):
    items = report_service.income_vs_expense_by_month(user_id, months=query["months"])
    return jsonify(
        {
            "data": income_vs_expense_out_schema.dump(items, many=True),
            "meta": {"months": query["months"]},
        }
    )
