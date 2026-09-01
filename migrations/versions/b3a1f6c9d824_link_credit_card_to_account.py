"""link credit_card to account

Revision ID: b3a1f6c9d824
Revises: 042672a46330
Create Date: 2026-09-01 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b3a1f6c9d824'
down_revision = '042672a46330'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('credit_cards', schema=None) as batch_op:
        batch_op.add_column(sa.Column('account_id', sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f('ix_credit_cards_account_id'), ['account_id'], unique=False
        )
        batch_op.create_foreign_key(
            'fk_credit_cards_account_id_accounts', 'accounts', ['account_id'], ['id']
        )


def downgrade():
    with op.batch_alter_table('credit_cards', schema=None) as batch_op:
        batch_op.drop_constraint('fk_credit_cards_account_id_accounts', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_credit_cards_account_id'))
        batch_op.drop_column('account_id')
