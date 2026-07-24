from marshmallow import Schema, fields, validate

INVESTMENT_TYPES = ("fixed_income", "stock", "fund", "crypto", "other")


class InvestmentCreateSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=120))
    type = fields.String(required=True, validate=validate.OneOf(INVESTMENT_TYPES))
    broker = fields.String(required=False, load_default=None, allow_none=True)
    invested_amount = fields.Decimal(
        required=True, as_string=False, validate=validate.Range(min=0.01)
    )
    current_amount = fields.Decimal(
        required=False, load_default=None, as_string=False, validate=validate.Range(min=0)
    )
    acquired_at = fields.Date(required=True)
    notes = fields.String(required=False, load_default=None, allow_none=True)


class InvestmentUpdateSchema(Schema):
    name = fields.String(required=False, validate=validate.Length(min=1, max=120))
    broker = fields.String(required=False, allow_none=True)
    current_amount = fields.Decimal(required=False, as_string=False, validate=validate.Range(min=0))
    notes = fields.String(required=False, allow_none=True)


class InvestmentOutSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    type = fields.String()
    broker = fields.String(allow_none=True)
    invested_amount = fields.Decimal(as_string=True)
    current_amount = fields.Decimal(as_string=True)
    acquired_at = fields.Date()
    notes = fields.String(allow_none=True)
    created_at = fields.DateTime()
    updated_at = fields.DateTime()
