"""Initial Production Schema & Security Hardening

Revision ID: 001_initial_prod
Revises: 
Create Date: 2026-08-29 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_prod'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tabla users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=100), nullable=False),
        sa.Column('role', sa.String(length=20), server_default='closer', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('failed_login_attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('locked_until', sa.DateTime(), nullable=True),
        sa.Column('must_change_password', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('mfa_secret', sa.String(length=512), nullable=True),
        sa.Column('mfa_enabled', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('mfa_recovery_codes_hash', sa.Text(), nullable=True),
        sa.Column('last_totp_code_used', sa.String(length=10), nullable=True),
        sa.Column('session_token_version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('password_changed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 2. Tabla customers
    op.create_table(
        'customers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('remote_id', sa.String(length=50), nullable=True),
        sa.Column('full_name', sa.String(length=512), nullable=False),
        sa.Column('name_blind_index', sa.String(length=64), nullable=True),
        sa.Column('phone', sa.String(length=512), nullable=False),
        sa.Column('phone_blind_index', sa.String(length=64), nullable=False),
        sa.Column('email', sa.String(length=512), nullable=True),
        sa.Column('company', sa.String(length=512), nullable=True),
        sa.Column('document_id', sa.String(length=512), nullable=True),
        sa.Column('province', sa.String(length=80), nullable=True),
        sa.Column('locality', sa.String(length=100), nullable=True),
        sa.Column('region', sa.String(length=80), nullable=True),
        sa.Column('product_line', sa.String(length=80), nullable=True),
        sa.Column('lead_score', sa.Integer(), server_default='50', nullable=False),
        sa.Column('segment', sa.String(length=30), server_default='WARM', nullable=False),
        sa.Column('status', sa.String(length=40), server_default='NUEVO', nullable=False),
        sa.Column('assigned_user_id', sa.Integer(), nullable=True),
        sa.Column('first_contact_at', sa.DateTime(), nullable=True),
        sa.Column('last_contact_at', sa.DateTime(), nullable=True),
        sa.Column('next_follow_up_at', sa.DateTime(), nullable=True),
        sa.Column('total_contacts', sa.Integer(), server_default='1', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['assigned_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_customers_phone_blind_index'), 'customers', ['phone_blind_index'], unique=False)
    op.create_index(op.f('ix_customers_name_blind_index'), 'customers', ['name_blind_index'], unique=False)

    # 3. Tabla opportunities
    op.create_table(
        'opportunities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=150), nullable=False),
        sa.Column('product', sa.String(length=80), nullable=False),
        sa.Column('amount_ars', sa.Float(), server_default='0', nullable=False),
        sa.Column('stage', sa.String(length=50), server_default='PROSPECCION', nullable=False),
        sa.Column('probability_pct', sa.Integer(), server_default='20', nullable=False),
        sa.Column('expected_close_date', sa.Date(), nullable=True),
        sa.Column('assigned_closer_id', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['assigned_closer_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # 4. Tabla tasks
    op.create_table(
        'tasks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('opportunity_id', sa.Integer(), nullable=True),
        sa.Column('assigned_user_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=150), nullable=False),
        sa.Column('task_type', sa.String(length=40), server_default='WHATSAPP', nullable=False),
        sa.Column('priority', sa.String(length=20), server_default='MEDIA', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='PENDIENTE', nullable=False),
        sa.Column('due_date', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['assigned_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    # 5. Tabla activity_logs
    op.create_table(
        'activity_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('channel', sa.String(length=30), server_default='WHATSAPP', nullable=False),
        sa.Column('direction', sa.String(length=10), server_default='OUTBOUND', nullable=False),
        sa.Column('summary', sa.String(length=255), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    # 6. Tabla audit_logs
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('username', sa.String(length=50), server_default='system', nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.String(length=50), nullable=True),
        sa.Column('old_data_json', sa.Text(), nullable=True),
        sa.Column('new_data_json', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('prev_hash', sa.String(length=64), nullable=True),
        sa.Column('entry_hash', sa.String(length=64), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    # 7. Tabla assignment_rules
    op.create_table(
        'assignment_rules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('product_line', sa.String(length=80), nullable=True),
        sa.Column('province_or_region', sa.String(length=80), nullable=True),
        sa.Column('min_lead_score', sa.Integer(), server_default='0', nullable=False),
        sa.Column('assigned_user_id', sa.Integer(), nullable=False),
        sa.Column('priority_order', sa.Integer(), server_default='1', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['assigned_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # 8. Tabla whatsapp_queue
    op.create_table(
        'whatsapp_queue',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('phone', sa.String(length=30), nullable=False),
        sa.Column('message_text', sa.Text(), nullable=False),
        sa.Column('media_path', sa.String(length=255), nullable=True),
        sa.Column('priority', sa.Integer(), server_default='5', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='PENDING', nullable=False),
        sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('max_attempts', sa.Integer(), server_default='3', nullable=False),
        sa.Column('next_retry_at', sa.DateTime(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('whatsapp_queue')
    op.drop_table('assignment_rules')
    op.drop_table('audit_logs')
    op.drop_table('activity_logs')
    op.drop_table('tasks')
    op.drop_table('opportunities')
    op.drop_table('customers')
    op.drop_table('users')
