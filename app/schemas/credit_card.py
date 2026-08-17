from marshmallow import Schema, fields, validate


class CreditCardCreateSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    bank_name = fields.String(
        required=False, load_default=None, allow_none=True, validate=validate.Length(max=60)
    )
    credit_limit = fields.Decimal(required=True, as_string=False, validate=validate.Range(min=0.01))
    closing_day = fields.Integer(required=True, validate=validate.Range(min=1, max=31))
    due_day = fields.Integer(required=True, validate=validate.Range(min=1, max=31))


class CreditCardUpdateSchema(Schema):
    name = fields.String(required=False, validate=validate.Length(min=1, max=100))
    bank_name = fields.String(required=False, allow_none=True, validate=validate.Length(max=60))
    credit_limit = fields.Decimal(
        required=False, as_string=False, validate=validate.Range(min=0.01)
    )
    closing_day = fields.Integer(required=False, validate=validate.Range(min=1, max=31))
    due_day = fields.Integer(required=False, validate=validate.Range(min=1, max=31))
    is_archived = fields.Boolean(required=False)


class CreditCardOutSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    bank_name = fields.String(allow_none=True)
    credit_limit = fields.Decimal(as_string=True)
    closing_day = fields.Integer()
    due_day = fields.Integer()
    is_archived = fields.Boolean()
    created_at = fields.DateTime()
    updated_at = fields.DateTime()
