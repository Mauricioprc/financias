from flask import Blueprint, jsonify

from app.api.decorators import require_user, validate_json, validate_query
from app.schemas.transfer import TransferCreateSchema, TransferListQuerySchema, TransferOutSchema
from app.services import transfer_service

bp = Blueprint("transfers", __name__)

create_schema = TransferCreateSchema()
out_schema = TransferOutSchema()
list_query_schema = TransferListQuerySchema()


@bp.route("", methods=["GET"])
@require_user
@validate_query(list_query_schema)
def list_transfers_route(query, user_id):
    items, total = transfer_service.list_transfers(
        user_id=user_id,
        account_id=query.get("account_id"),
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
def create_transfer_route(payload, user_id):
    transfer = transfer_service.create_transfer(
        user_id=user_id,
        from_account_id=payload["from_account_id"],
        to_account_id=payload["to_account_id"],
        amount=payload["amount"],
        date=payload["date"],
        description=payload["description"],
    )
    return jsonify({"data": out_schema.dump(transfer), "meta": {}}), 201


@bp.route("/<int:transfer_id>", methods=["GET"])
@require_user
def get_transfer_route(user_id, transfer_id):
    transfer = transfer_service.get_transfer(user_id, transfer_id)
    return jsonify({"data": out_schema.dump(transfer), "meta": {}})


@bp.route("/<int:transfer_id>", methods=["DELETE"])
@require_user
def delete_transfer_route(user_id, transfer_id):
    transfer_service.delete_transfer(user_id, transfer_id)
    return "", 204
