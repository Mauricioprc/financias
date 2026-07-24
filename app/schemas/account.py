from marshmallow import Schema, fields, validate

ACCOUNT_TYPES = ("checking", "savings", "wallet", "other")


class AccountCreateSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    type = fields.String(required=True, validate=validate.OneOf(ACCOUNT_TYPES))
    initial_balance = fields.Decimal(required=False, load_default=0, as_string=False)
    currency = fields.String(required=False, load_default="BRL", validate=validate.Length(equal=3))


class AccountUpdateSchema(Schema):
    name = fields.String(required=False, validate=validate.Length(min=1, max=100))
    type = fields.String(required=False, validate=validate.OneOf(ACCOUNT_TYPES))
    is_archived = fields.Boolean(required=False)


class AccountOutSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    type = fields.String()
    initial_balance = fields.Decimal(as_string=True)
    current_balance = fields.Decimal(as_string=True)
    currency = fields.String()
    is_archived = fields.Boolean()
    created_at = fields.DateTime()
    updated_at = fields.DateTime()
