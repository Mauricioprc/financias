from marshmallow import Schema, fields, validate

TRANSACTION_TYPES = ("income", "expense")


class TransactionCreateSchema(Schema):
    account_id = fields.Integer(required=True)
    category_id = fields.Integer(required=False, load_default=None, allow_none=True)
    credit_card_id = fields.Integer(required=False, load_default=None, allow_none=True)
    type = fields.String(required=True, validate=validate.OneOf(TRANSACTION_TYPES))
    description = fields.String(required=True, validate=validate.Length(min=1, max=255))
    amount = fields.Decimal(required=True, as_string=False, validate=validate.Range(min=0.01))
    date = fields.Date(required=True)
    is_paid = fields.Boolean(required=False, load_default=True)
    notes = fields.String(required=False, load_default=None, allow_none=True)


class InstallmentPurchaseCreateSchema(Schema):
    account_id = fields.Integer(required=True)
    credit_card_id = fields.Integer(required=True)
    category_id = fields.Integer(required=False, load_default=None, allow_none=True)
    description = fields.String(required=True, validate=validate.Length(min=1, max=255))
    total_amount = fields.Decimal(required=True, as_string=False, validate=validate.Range(min=0.01))
    installments = fields.Integer(required=True, validate=validate.Range(min=2, max=24))
    date = fields.Date(required=True)
    notes = fields.String(required=False, load_default=None, allow_none=True)


class TransactionUpdateSchema(Schema):
    account_id = fields.Integer(required=False)
    category_id = fields.Integer(required=False, allow_none=True)
    description = fields.String(required=False, validate=validate.Length(min=1, max=255))
    amount = fields.Decimal(required=False, as_string=False, validate=validate.Range(min=0.01))
    date = fields.Date(required=False)
    is_paid = fields.Boolean(required=False)
    notes = fields.String(required=False, allow_none=True)


class TransactionOutSchema(Schema):
    id = fields.Integer()
    account_id = fields.Integer()
    category_id = fields.Integer(allow_none=True)
    credit_card_id = fields.Integer(allow_none=True)
    invoice_id = fields.Integer(allow_none=True)
    type = fields.String()
    description = fields.String()
    amount = fields.Decimal(as_string=True)
    date = fields.Date()
    is_paid = fields.Boolean()
    installment_number = fields.Integer(allow_none=True)
    installment_total = fields.Integer(allow_none=True)
    purchase_group_id = fields.UUID(allow_none=True)
    notes = fields.String(allow_none=True)
    created_at = fields.DateTime()
    updated_at = fields.DateTime()


class SuggestCategoryQuerySchema(Schema):
    description = fields.String(required=True, validate=validate.Length(min=1))


class TransactionListQuerySchema(Schema):
    account_id = fields.Integer(required=False)
    category_id = fields.Integer(required=False)
    credit_card_id = fields.Integer(required=False)
    invoice_id = fields.Integer(required=False)
    type = fields.String(required=False, validate=validate.OneOf(TRANSACTION_TYPES))
    date_from = fields.Date(required=False)
    date_to = fields.Date(required=False)
    page = fields.Integer(required=False, load_default=1, validate=validate.Range(min=1))
    per_page = fields.Integer(
        required=False, load_default=20, validate=validate.Range(min=1, max=100)
    )
