from marshmallow import Schema, fields, validate


class UpcomingBillsQuerySchema(Schema):
    days = fields.Integer(required=False, load_default=30)


class UpcomingBillItemSchema(Schema):
    type = fields.String(validate=validate.OneOf(("invoice", "recurring")))
    date = fields.Date()
    label = fields.String()
    amount = fields.Decimal(as_string=True)
    reference_id = fields.Integer()
