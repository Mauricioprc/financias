from marshmallow import Schema, fields, validate


class InvoicePaySchema(Schema):
    account_id = fields.Integer(required=True)


class InvoicePaymentSchema(Schema):
    account_id = fields.Integer(required=True)
    amount = fields.Decimal(required=True, as_string=False, validate=validate.Range(min=0.01))


class InvoiceOutSchema(Schema):
    id = fields.Integer()
    credit_card_id = fields.Integer()
    reference_month = fields.Date()
    closing_date = fields.Date()
    due_date = fields.Date()
    total_amount = fields.Decimal(as_string=True)
    paid_amount = fields.Decimal(as_string=True)
    status = fields.String()
    paid_at = fields.DateTime(allow_none=True)
    created_at = fields.DateTime(allow_none=True)
    updated_at = fields.DateTime(allow_none=True)
    # dump_default=True: toda fatura persistida de verdade (a imensa
    # maioria dos usos deste schema) é `persisted=True` sem precisar setar
    # nada explicitamente — só o preview de invoice_service.py
    # (get_current_invoice_preview) passa `persisted=False` de propósito.
    persisted = fields.Boolean(dump_default=True)


class InvoiceListQuerySchema(Schema):
    credit_card_id = fields.Integer(required=False)
    status = fields.String(
        required=False, validate=validate.OneOf(("open", "closed", "paid"))
    )
