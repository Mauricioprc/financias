from flask import Blueprint, jsonify

from app.api.decorators import require_user, validate_json, validate_query
from app.schemas.transaction import (
    TransactionCreateSchema,
    TransactionListQuerySchema,
    TransactionOutSchema,
    TransactionUpdateSchema,
)
from app.services import transaction_service

bp = Blueprint("transactions", __name__)

create_schema = TransactionCreateSchema()
update_schema = TransactionUpdateSchema()
out_schema = TransactionOutSchema()
list_query_schema = TransactionListQuerySchema()


@bp.route("", methods=["GET"])
@require_user
@validate_query(list_query_schema)
def list_transactions_route(query, user_id):
    items, total = transaction_service.list_transactions(
        user_id=user_id,
        account_id=query.get("account_id"),
        category_id=query.get("category_id"),
        credit_card_id=query.get("credit_card_id"),
        type=query.get("type"),
        date_from=query.get("date_from"),
        date_to=query.get("date_to"),
        page=query["page"],
        per_page=query["per_page"],
    )
    return jsonify(
        {
            "data": out_schema.dump(items, many=True),
            "meta": {"page": query["page"], "per_page": query["per_page"], "total": total},
        }
    )


@bp.route("", methods=["POST"])
@require_user
@validate_json(create_schema)
def create_transaction_route(payload, user_id):
    transaction = transaction_service.create_transaction(
        user_id=user_id,
        account_id=payload["account_id"],
        category_id=payload["category_id"],
        credit_card_id=payload["credit_card_id"],
        type=payload["type"],
        description=payload["description"],
        amount=payload["amount"],
        date=payload["date"],
        is_paid=payload["is_paid"],
        notes=payload["notes"],
    )
    return jsonify({"data": out_schema.dump(transaction), "meta": {}}), 201


@bp.route("/<int:transaction_id>", methods=["GET"])
@require_user
def get_transaction_route(user_id, transaction_id):
    transaction = transaction_service.get_transaction(user_id, transaction_id)
    return jsonify({"data": out_schema.dump(transaction), "meta": {}})


@bp.route("/<int:transaction_id>", methods=["PATCH"])
@require_user
@validate_json(update_schema)
def update_transaction_route(payload, user_id, transaction_id):
    transaction = transaction_service.update_transaction(user_id, transaction_id, **payload)
    return jsonify({"data": out_schema.dump(transaction), "meta": {}})


@bp.route("/<int:transaction_id>", methods=["DELETE"])
@require_user
def delete_transaction_route(user_id, transaction_id):
    transaction_service.delete_transaction(user_id, transaction_id)
    return "", 204
