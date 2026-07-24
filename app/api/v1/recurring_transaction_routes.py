from flask import Blueprint, jsonify

from app.api.decorators import require_user, validate_json, validate_query
from app.schemas.recurring_transaction import (
    GenerateTransactionsQuerySchema,
    RecurringTransactionCreateSchema,
    RecurringTransactionOutSchema,
    RecurringTransactionUpdateSchema,
)
from app.schemas.transaction import TransactionOutSchema
from app.services import recurring_transaction_service

bp = Blueprint("recurring_transactions", __name__)

create_schema = RecurringTransactionCreateSchema()
update_schema = RecurringTransactionUpdateSchema()
out_schema = RecurringTransactionOutSchema()
generate_query_schema = GenerateTransactionsQuerySchema()
transaction_out_schema = TransactionOutSchema()


@bp.route("", methods=["GET"])
@require_user
def list_recurring_transactions_route(user_id):
    items = recurring_transaction_service.list_recurring_transactions(user_id)
    return jsonify({"data": out_schema.dump(items, many=True), "meta": {"total": len(items)}})


@bp.route("", methods=["POST"])
@require_user
@validate_json(create_schema)
def create_recurring_transaction_route(payload, user_id):
    recurring = recurring_transaction_service.create_recurring_transaction(
        user_id=user_id,
        account_id=payload["account_id"],
        category_id=payload["category_id"],
        description=payload["description"],
        type=payload["type"],
        amount=payload["amount"],
        frequency=payload["frequency"],
        day_of_month=payload["day_of_month"],
        start_date=payload["start_date"],
        end_date=payload["end_date"],
    )
    return jsonify({"data": out_schema.dump(recurring), "meta": {}}), 201


@bp.route("/<int:recurring_id>", methods=["GET"])
@require_user
def get_recurring_transaction_route(user_id, recurring_id):
    recurring = recurring_transaction_service.get_recurring_transaction(user_id, recurring_id)
    return jsonify({"data": out_schema.dump(recurring), "meta": {}})


@bp.route("/<int:recurring_id>", methods=["PATCH"])
@require_user
@validate_json(update_schema)
def update_recurring_transaction_route(payload, user_id, recurring_id):
    recurring = recurring_transaction_service.update_recurring_transaction(
        user_id, recurring_id, **payload
    )
    return jsonify({"data": out_schema.dump(recurring), "meta": {}})


@bp.route("/<int:recurring_id>", methods=["DELETE"])
@require_user
def delete_recurring_transaction_route(user_id, recurring_id):
    recurring_transaction_service.delete_recurring_transaction(user_id, recurring_id)
    return "", 204


@bp.route("/<int:recurring_id>/generate", methods=["POST"])
@require_user
@validate_query(generate_query_schema)
def generate_recurring_transaction_route(query, user_id, recurring_id):
    transactions = recurring_transaction_service.generate_due_transactions(
        user_id, recurring_id, until=query.get("until")
    )
    return jsonify(
        {
            "data": transaction_out_schema.dump(transactions, many=True),
            "meta": {"total": len(transactions)},
        }
    )
