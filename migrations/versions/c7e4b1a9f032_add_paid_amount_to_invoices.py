"""add paid_amount to invoices

Revision ID: c7e4b1a9f032
Revises: b3a1f6c9d824
Create Date: 2026-09-01 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7e4b1a9f032'
down_revision = 'b3a1f6c9d824'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('paid_amount', sa.Numeric(14, 2), nullable=False, server_default='0')
        )

    # Faturas já marcadas como pagas antes desta coluna existir: consideramos
    # o valor pago igual ao total cobrado (é a única suposição consistente
    # com "já paga" sem esse histórico).
    op.execute("UPDATE invoices SET paid_amount = total_amount WHERE status = 'paid'")


def downgrade():
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.drop_column('paid_amount')
