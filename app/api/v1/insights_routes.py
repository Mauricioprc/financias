from flask import Blueprint, jsonify

from app.api.decorators import require_user
from app.schemas.insights import (
    BalanceForecastSchema,
    CategoryComparisonItemSchema,
    GoalProjectionSchema,
    InsightsSummarySchema,
    InvoiceTrendAlertSchema,
    SpendingAnomalySchema,
)
from app.services import insights_service

bp = Blueprint("insights", __name__)

balance_forecast_schema = BalanceForecastSchema()
category_comparison_schema = CategoryComparisonItemSchema()
spending_anomaly_schema = SpendingAnomalySchema()
invoice_trend_schema = InvoiceTrendAlertSchema()
goal_projection_schema = GoalProjectionSchema()
summary_schema = InsightsSummarySchema()


@bp.route("/balance-forecast/<int:account_id>", methods=["GET"])
@require_user
def balance_forecast_route(user_id, account_id):
    forecast = insights_service.forecast_account_balance(user_id, account_id)
    return jsonify({"data": balance_forecast_schema.dump(forecast), "meta": {}})


@bp.route("/category-comparison", methods=["GET"])
@require_user
def category_comparison_route(user_id):
    items = insights_service.compare_category_spending(user_id)
    return jsonify(
        {"data": category_comparison_schema.dump(items, many=True), "meta": {"total": len(items)}}
    )


@bp.route("/spending-anomalies", methods=["GET"])
@require_user
def spending_anomalies_route(user_id):
    items = insights_service.detect_spending_anomalies(user_id)
    return jsonify(
        {"data": spending_anomaly_schema.dump(items, many=True), "meta": {"total": len(items)}}
    )


@bp.route("/invoice-trends", methods=["GET"])
@require_user
def invoice_trends_route(user_id):
    items = insights_service.detect_invoice_trend_alerts(user_id)
    return jsonify(
        {"data": invoice_trend_schema.dump(items, many=True), "meta": {"total": len(items)}}
    )


@bp.route("/goal-projection/<int:goal_id>", methods=["GET"])
@require_user
def goal_projection_route(user_id, goal_id):
    projection = insights_service.project_goal_completion(user_id, goal_id)
    return jsonify({"data": goal_projection_schema.dump(projection), "meta": {}})


@bp.route("/summary", methods=["GET"])
@require_user
def insights_summary_route(user_id):
    summary = insights_service.build_insights_summary(user_id)
    return jsonify({"data": summary_schema.dump(summary), "meta": {}})
