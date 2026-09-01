"""link recurring_transaction to credit_card (assinaturas)

Revision ID: e2d5a7c1f486
Revises: c7e4b1a9f032
Create Date: 2026-09-01 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e2d5a7c1f486'
down_revision = 'c7e4b1a9f032'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('recurring_transactions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('credit_card_id', sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f('ix_recurring_transactions_credit_card_id'),
            ['credit_card_id'],
            unique=False,
        )
        batch_op.create_foreign_key(
            'fk_recurring_transactions_credit_card_id_credit_cards',
            'credit_cards',
            ['credit_card_id'],
            ['id'],
        )


def downgrade():
    with op.batch_alter_table('recurring_transactions', schema=None) as batch_op:
        batch_op.drop_constraint(
            'fk_recurring_transactions_credit_card_id_credit_cards', type_='foreignkey'
        )
        batch_op.drop_index(batch_op.f('ix_recurring_transactions_credit_card_id'))
        batch_op.drop_column('credit_card_id')
