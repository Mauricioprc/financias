from flask import Blueprint, jsonify

from app.api.decorators import require_user, validate_json
from app.schemas.investment import (
    InvestmentCreateSchema,
    InvestmentOutSchema,
    InvestmentUpdateSchema,
)
from app.services import investment_service

bp = Blueprint("investments", __name__)

create_schema = InvestmentCreateSchema()
update_schema = InvestmentUpdateSchema()
out_schema = InvestmentOutSchema()


@bp.route("", methods=["GET"])
@require_user
def list_investments_route(user_id):
    investments = investment_service.list_investments(user_id)
    return jsonify(
        {"data": out_schema.dump(investments, many=True), "meta": {"total": len(investments)}}
    )


@bp.route("", methods=["POST"])
@require_user
@validate_json(create_schema)
def create_investment_route(payload, user_id):
    investment = investment_service.create_investment(
        user_id=user_id,
        name=payload["name"],
        type=payload["type"],
        broker=payload["broker"],
        invested_amount=payload["invested_amount"],
        current_amount=payload["current_amount"],
        acquired_at=payload["acquired_at"],
        notes=payload["notes"],
    )
    return jsonify({"data": out_schema.dump(investment), "meta": {}}), 201


@bp.route("/<int:investment_id>", methods=["GET"])
@require_user
def get_investment_route(user_id, investment_id):
    investment = investment_service.get_investment(user_id, investment_id)
    return jsonify({"data": out_schema.dump(investment), "meta": {}})


@bp.route("/<int:investment_id>", methods=["PATCH"])
@require_user
@validate_json(update_schema)
def update_investment_route(payload, user_id, investment_id):
    investment = investment_service.update_investment(user_id, investment_id, **payload)
    return jsonify({"data": out_schema.dump(investment), "meta": {}})


@bp.route("/<int:investment_id>", methods=["DELETE"])
@require_user
def delete_investment_route(user_id, investment_id):
    investment_service.delete_investment(user_id, investment_id)
    return "", 204
