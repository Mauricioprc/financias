from flask import Blueprint, jsonify

from app.api.decorators import require_user, validate_json
from app.schemas.account import AccountCreateSchema, AccountOutSchema, AccountUpdateSchema
from app.services import account_service

bp = Blueprint("accounts", __name__)

create_schema = AccountCreateSchema()
update_schema = AccountUpdateSchema()
out_schema = AccountOutSchema()


@bp.route("", methods=["GET"])
@require_user
def list_accounts_route(user_id):
    accounts = account_service.list_accounts(user_id)
    return jsonify({"data": out_schema.dump(accounts, many=True), "meta": {"total": len(accounts)}})


@bp.route("", methods=["POST"])
@require_user
@validate_json(create_schema)
def create_account_route(payload, user_id):
    account = account_service.create_account(
        user_id=user_id,
        name=payload["name"],
        type=payload["type"],
        initial_balance=payload["initial_balance"],
        currency=payload["currency"],
    )
    return jsonify({"data": out_schema.dump(account), "meta": {}}), 201


@bp.route("/<int:account_id>", methods=["GET"])
@require_user
def get_account_route(user_id, account_id):
    account = account_service.get_account(user_id, account_id)
    return jsonify({"data": out_schema.dump(account), "meta": {}})


@bp.route("/<int:account_id>", methods=["PATCH"])
@require_user
@validate_json(update_schema)
def update_account_route(payload, user_id, account_id):
    account = account_service.update_account(user_id, account_id, **payload)
    return jsonify({"data": out_schema.dump(account), "meta": {}})


@bp.route("/<int:account_id>", methods=["DELETE"])
@require_user
def delete_account_route(user_id, account_id):
    account_service.delete_account(user_id, account_id)
    return "", 204
