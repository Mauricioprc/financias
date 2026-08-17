from flask import Blueprint, jsonify

from app.api.decorators import require_user, validate_json
from app.schemas.credit_card import (
    CreditCardCreateSchema,
    CreditCardOutSchema,
    CreditCardUpdateSchema,
)
from app.services import credit_card_service

bp = Blueprint("credit_cards", __name__)

create_schema = CreditCardCreateSchema()
update_schema = CreditCardUpdateSchema()
out_schema = CreditCardOutSchema()


@bp.route("", methods=["GET"])
@require_user
def list_credit_cards_route(user_id):
    cards = credit_card_service.list_credit_cards(user_id)
    return jsonify({"data": out_schema.dump(cards, many=True), "meta": {"total": len(cards)}})


@bp.route("", methods=["POST"])
@require_user
@validate_json(create_schema)
def create_credit_card_route(payload, user_id):
    card = credit_card_service.create_credit_card(
        user_id=user_id,
        name=payload["name"],
        bank_name=payload["bank_name"],
        credit_limit=payload["credit_limit"],
        closing_day=payload["closing_day"],
        due_day=payload["due_day"],
    )
    return jsonify({"data": out_schema.dump(card), "meta": {}}), 201


@bp.route("/<int:credit_card_id>", methods=["GET"])
@require_user
def get_credit_card_route(user_id, credit_card_id):
    card = credit_card_service.get_credit_card(user_id, credit_card_id)
    return jsonify({"data": out_schema.dump(card), "meta": {}})


@bp.route("/<int:credit_card_id>", methods=["PATCH"])
@require_user
@validate_json(update_schema)
def update_credit_card_route(payload, user_id, credit_card_id):
    card = credit_card_service.update_credit_card(user_id, credit_card_id, **payload)
    return jsonify({"data": out_schema.dump(card), "meta": {}})


@bp.route("/<int:credit_card_id>", methods=["DELETE"])
@require_user
def delete_credit_card_route(user_id, credit_card_id):
    credit_card_service.delete_credit_card(user_id, credit_card_id)
    return "", 204
