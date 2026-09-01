from flask import Blueprint, jsonify

from app.api.decorators import require_user, validate_json, validate_query
from app.schemas.invoice import (
    InvoiceListQuerySchema,
    InvoiceOutSchema,
    InvoicePaymentSchema,
    InvoicePaySchema,
)
from app.services import invoice_service

bp = Blueprint("invoices", __name__)

out_schema = InvoiceOutSchema()
list_query_schema = InvoiceListQuerySchema()
pay_schema = InvoicePaySchema()
payment_schema = InvoicePaymentSchema()


@bp.route("", methods=["GET"])
@require_user
@validate_query(list_query_schema)
def list_invoices_route(query, user_id):
    invoices = invoice_service.list_invoices(
        user_id=user_id,
        credit_card_id=query.get("credit_card_id"),
        status=query.get("status"),
    )
    return jsonify({"data": out_schema.dump(invoices, many=True), "meta": {"total": len(invoices)}})


@bp.route("/<int:invoice_id>", methods=["GET"])
@require_user
def get_invoice_route(user_id, invoice_id):
    invoice = invoice_service.get_invoice(user_id, invoice_id)
    return jsonify({"data": out_schema.dump(invoice), "meta": {}})


@bp.route("/<int:invoice_id>/close", methods=["POST"])
@require_user
def close_invoice_route(user_id, invoice_id):
    invoice = invoice_service.close_invoice(user_id, invoice_id)
    return jsonify({"data": out_schema.dump(invoice), "meta": {}})


@bp.route("/<int:invoice_id>/pay", methods=["POST"])
@require_user
@validate_json(pay_schema)
def pay_invoice_route(payload, user_id, invoice_id):
    invoice = invoice_service.pay_invoice(user_id, invoice_id, account_id=payload["account_id"])
    return jsonify({"data": out_schema.dump(invoice), "meta": {}})


@bp.route("/<int:invoice_id>/payments", methods=["POST"])
@require_user
@validate_json(payment_schema)
def register_invoice_payment_route(payload, user_id, invoice_id):
    invoice = invoice_service.register_payment(
        user_id, invoice_id, account_id=payload["account_id"], amount=payload["amount"]
    )
    return jsonify({"data": out_schema.dump(invoice), "meta": {}})
