from marshmallow import Schema, ValidationError, fields, validate, validates_schema


class TransferCreateSchema(Schema):
    from_account_id = fields.Integer(required=True)
    to_account_id = fields.Integer(required=True)
    amount = fields.Decimal(required=True, as_string=False, validate=validate.Range(min=0.01))
    date = fields.Date(required=True)
    description = fields.String(required=False, load_default=None, allow_none=True)

    @validates_schema
    def validate_distinct_accounts(self, data, **kwargs):
        if data.get("from_account_id") == data.get("to_account_id"):
            raise ValidationError(
                "from_account_id e to_account_id devem ser contas diferentes.",
                field_name="to_account_id",
            )


class TransferOutSchema(Schema):
    id = fields.Integer()
    from_account_id = fields.Integer()
    to_account_id = fields.Integer()
    amount = fields.Decimal(as_string=True)
    date = fields.Date()
    description = fields.String(allow_none=True)
    created_at = fields.DateTime()


class TransferListQuerySchema(Schema):
    account_id = fields.Integer(required=False)
    date_from = fields.Date(required=False)
    date_to = fields.Date(required=False)
    page = fields.Integer(required=False, load_default=1, validate=validate.Range(min=1))
    per_page = fields.Integer(
        required=False, load_default=20, validate=validate.Range(min=1, max=100)
    )
