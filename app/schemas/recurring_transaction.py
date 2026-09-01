from marshmallow import Schema, ValidationError, fields, validate, validates_schema

FREQUENCIES = ("monthly", "weekly", "yearly")
TRANSACTION_TYPES = ("income", "expense")


class RecurringTransactionCreateSchema(Schema):
    account_id = fields.Integer(required=True)
    category_id = fields.Integer(required=False, load_default=None, allow_none=True)
    credit_card_id = fields.Integer(required=False, load_default=None, allow_none=True)
    description = fields.String(required=True, validate=validate.Length(min=1, max=255))
    type = fields.String(required=True, validate=validate.OneOf(TRANSACTION_TYPES))
    amount = fields.Decimal(required=True, as_string=False, validate=validate.Range(min=0.01))
    frequency = fields.String(required=True, validate=validate.OneOf(FREQUENCIES))
    day_of_month = fields.Integer(
        required=False, load_default=None, allow_none=True, validate=validate.Range(min=1, max=31)
    )
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=False, load_default=None, allow_none=True)

    @validates_schema
    def validate_end_after_start(self, data, **kwargs):
        end_date = data.get("end_date")
        start_date = data.get("start_date")
        if end_date is not None and start_date is not None and end_date < start_date:
            raise ValidationError(
                "end_date deve ser posterior a start_date.", field_name="end_date"
            )

    @validates_schema
    def validate_card_requires_expense(self, data, **kwargs):
        if data.get("credit_card_id") is not None and data.get("type") != "expense":
            raise ValidationError(
                "Recorrências no cartão de crédito devem ser do tipo expense.",
                field_name="credit_card_id",
            )


class RecurringTransactionUpdateSchema(Schema):
    category_id = fields.Integer(required=False, allow_none=True)
    credit_card_id = fields.Integer(required=False, allow_none=True)
    description = fields.String(required=False, validate=validate.Length(min=1, max=255))
    amount = fields.Decimal(required=False, as_string=False, validate=validate.Range(min=0.01))
    day_of_month = fields.Integer(
        required=False, allow_none=True, validate=validate.Range(min=1, max=31)
    )
    end_date = fields.Date(required=False, allow_none=True)
    is_active = fields.Boolean(required=False)


class RecurringTransactionOutSchema(Schema):
    id = fields.Integer()
    account_id = fields.Integer()
    category_id = fields.Integer(allow_none=True)
    credit_card_id = fields.Integer(allow_none=True)
    description = fields.String()
    type = fields.String()
    amount = fields.Decimal(as_string=True)
    frequency = fields.String()
    day_of_month = fields.Integer(allow_none=True)
    start_date = fields.Date()
    end_date = fields.Date(allow_none=True)
    last_generated = fields.Date(allow_none=True)
    is_active = fields.Boolean()
    created_at = fields.DateTime()
    updated_at = fields.DateTime()


class GenerateTransactionsQuerySchema(Schema):
    until = fields.Date(required=False)
