from marshmallow import Schema, fields, validate

GOAL_STATUSES = ("in_progress", "achieved", "abandoned")


class GoalCreateSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=120))
    target_amount = fields.Decimal(
        required=True, as_string=False, validate=validate.Range(min=0.01)
    )
    target_date = fields.Date(required=False, load_default=None, allow_none=True)


class GoalUpdateSchema(Schema):
    name = fields.String(required=False, validate=validate.Length(min=1, max=120))
    target_amount = fields.Decimal(
        required=False, as_string=False, validate=validate.Range(min=0.01)
    )
    target_date = fields.Date(required=False, allow_none=True)
    status = fields.String(required=False, validate=validate.OneOf(GOAL_STATUSES))


class GoalContributeSchema(Schema):
    amount = fields.Decimal(required=True, as_string=False, validate=validate.Range(min=0.01))


class GoalOutSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    target_amount = fields.Decimal(as_string=True)
    current_amount = fields.Decimal(as_string=True)
    target_date = fields.Date(allow_none=True)
    status = fields.String()
    created_at = fields.DateTime()
    updated_at = fields.DateTime()
