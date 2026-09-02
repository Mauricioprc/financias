from flask import Blueprint, jsonify

from app.api.decorators import require_user, validate_json
from app.schemas.budget import BudgetCreateSchema, BudgetOutSchema, BudgetProgressItemSchema, BudgetUpdateSchema
from app.services import budget_service

bp = Blueprint("budgets", __name__)

create_schema = BudgetCreateSchema()
update_schema = BudgetUpdateSchema()
out_schema = BudgetOutSchema()
progress_schema = BudgetProgressItemSchema()


@bp.route("", methods=["GET"])
@require_user
def list_budgets_route(user_id):
    budgets = budget_service.list_budgets(user_id)
    return jsonify({"data": out_schema.dump(budgets, many=True), "meta": {"total": len(budgets)}})


@bp.route("", methods=["POST"])
@require_user
@validate_json(create_schema)
def create_budget_route(payload, user_id):
    budget = budget_service.create_budget(
        user_id=user_id,
        category_id=payload["category_id"],
        monthly_limit=payload["monthly_limit"],
    )
    return jsonify({"data": out_schema.dump(budget), "meta": {}}), 201


@bp.route("/progress", methods=["GET"])
@require_user
def budget_progress_route(user_id):
    progress = budget_service.get_budget_progress(user_id)
    return jsonify(
        {"data": progress_schema.dump(progress, many=True), "meta": {"total": len(progress)}}
    )


@bp.route("/<int:budget_id>", methods=["PATCH"])
@require_user
@validate_json(update_schema)
def update_budget_route(payload, user_id, budget_id):
    budget = budget_service.update_budget(user_id, budget_id, **payload)
    return jsonify({"data": out_schema.dump(budget), "meta": {}})


@bp.route("/<int:budget_id>", methods=["DELETE"])
@require_user
def delete_budget_route(user_id, budget_id):
    budget_service.delete_budget(user_id, budget_id)
    return "", 204
