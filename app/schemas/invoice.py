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
    created_at = fields.DateTime()
    updated_at = fields.DateTime()


class InvoiceListQuerySchema(Schema):
    credit_card_id = fields.Integer(required=False)
    status = fields.String(
        required=False, validate=validate.OneOf(("open", "closed", "paid"))
    )
