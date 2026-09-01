from marshmallow import Schema, fields


class ForecastComponentsSchema(Schema):
    recurring_expected = fields.Decimal(as_string=True)
    upcoming_invoice_debits = fields.Decimal(as_string=True)
    variable_spending_estimate = fields.Decimal(as_string=True)


class BalanceForecastSchema(Schema):
    account_id = fields.Integer()
    current_balance = fields.Decimal(as_string=True)
    projected_end_of_month_balance = fields.Decimal(as_string=True)
    days_remaining = fields.Integer()
    components = fields.Nested(ForecastComponentsSchema)


class CategoryComparisonItemSchema(Schema):
    category_id = fields.Integer(allow_none=True)
    category_name = fields.String()
    current_month_total = fields.Decimal(as_string=True)
    same_period_last_month_total = fields.Decimal(as_string=True)
    trailing_3_month_avg = fields.Decimal(as_string=True)
    pct_change_vs_last_month = fields.Decimal(as_string=True, allow_none=True)
    pct_change_vs_avg = fields.Decimal(as_string=True, allow_none=True)


class SpendingAnomalySchema(Schema):
    category_id = fields.Integer(allow_none=True)
    category_name = fields.String()
    current_month_total = fields.Decimal(as_string=True)
    projected_month_total = fields.Decimal(as_string=True)
    trailing_3_month_avg = fields.Decimal(as_string=True)
    pct_above_avg = fields.Decimal(as_string=True)
    severity = fields.String()


class InvoiceTrendAlertSchema(Schema):
    card_id = fields.Integer()
    card_name = fields.String()
    current_total = fields.Decimal(as_string=True)
    projected_total = fields.Decimal(as_string=True)
    avg_of_last_3 = fields.Decimal(as_string=True)
    pct_above_average = fields.Decimal(as_string=True)


class GoalProjectionSchema(Schema):
    goal_id = fields.Integer()
    current_amount = fields.Decimal(as_string=True)
    target_amount = fields.Decimal(as_string=True)
    target_date = fields.Date(allow_none=True)
    projected_completion_date = fields.Date(allow_none=True)
    avg_monthly_contribution = fields.Decimal(as_string=True)
    is_rough_estimate = fields.Boolean()
    on_track = fields.Boolean(allow_none=True)
    reason = fields.String(allow_none=True)


class InsightsSummarySchema(Schema):
    balance_forecasts = fields.List(fields.Nested(BalanceForecastSchema))
    category_comparison = fields.List(fields.Nested(CategoryComparisonItemSchema))
    spending_anomalies = fields.List(fields.Nested(SpendingAnomalySchema))
    invoice_trends = fields.List(fields.Nested(InvoiceTrendAlertSchema))
