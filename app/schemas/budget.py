from marshmallow import Schema, fields, validate


class BudgetCreateSchema(Schema):
    category_id = fields.Integer(required=True)
    monthly_limit = fields.Decimal(
        required=True, as_string=False, validate=validate.Range(min=0.01)
    )


class BudgetUpdateSchema(Schema):
    category_id = fields.Integer(required=False)
    monthly_limit = fields.Decimal(
        required=False, as_string=False, validate=validate.Range(min=0.01)
    )


class BudgetOutSchema(Schema):
    id = fields.Integer()
    category_id = fields.Integer()
    monthly_limit = fields.Decimal(as_string=True)
    created_at = fields.DateTime()
    updated_at = fields.DateTime()


class BudgetProgressItemSchema(Schema):
    budget_id = fields.Integer()
    category_id = fields.Integer()
    category_name = fields.String()
    monthly_limit = fields.Decimal(as_string=True)
    current_month_total = fields.Decimal(as_string=True)
    pct_used = fields.Decimal(as_string=True)
    remaining = fields.Decimal(as_string=True)
    is_over_budget = fields.Boolean()
    days_remaining_in_month = fields.Integer()
