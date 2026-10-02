"""Initial migration for 7 core entities

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-02 15:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create Users Table
    op.create_table(
        'users',
        sa.Column('UserID', sa.UUID(), nullable=False),
        sa.Column('Email', sa.String(length=255), nullable=False),
        sa.Column('PasswordHash', sa.String(length=255), nullable=False),
        sa.Column(
            'Role',
            sa.Enum('Customer', 'Merchant', 'Bank Admin', name='user_role_enum'),
            nullable=False,
            server_default='Customer',
        ),
        sa.Column('CreatedAt', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('UserID')
    )
    op.create_index(op.f('ix_users_UserID'), 'users', ['UserID'], unique=False)
    op.create_index(op.f('ix_users_Email'), 'users', ['Email'], unique=True)

    # 2. Create Accounts Table
    op.create_table(
        'accounts',
        sa.Column('AccountID', sa.UUID(), nullable=False),
        sa.Column('UserID', sa.UUID(), nullable=False),
        sa.Column(
            'AccountType',
            sa.Enum('Checking', 'Savings', 'Business', name='account_type_enum'),
            nullable=False,
            server_default='Checking',
        ),
        sa.Column('Balance', sa.Numeric(precision=18, scale=2), nullable=False, server_default='0.00'),
        sa.Column(
            'KYCStatus',
            sa.Enum('Pending', 'Verified', 'Rejected', name='kyc_status_enum'),
            nullable=False,
            server_default='Pending',
        ),
        sa.Column('CreatedAt', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['UserID'], ['users.UserID'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('AccountID')
    )
    op.create_index(op.f('ix_accounts_AccountID'), 'accounts', ['AccountID'], unique=False)
    op.create_index(op.f('ix_accounts_UserID'), 'accounts', ['UserID'], unique=False)

    # 3. Create Devices Table
    op.create_table(
        'devices',
        sa.Column('DeviceID', sa.UUID(), nullable=False),
        sa.Column('UserID', sa.UUID(), nullable=False),
        sa.Column('DeviceFingerprint', sa.String(length=255), nullable=False),
        sa.Column('DeviceType', sa.String(length=100), nullable=False, server_default='Unknown'),
        sa.Column('LastUsedIP', sa.String(length=64), nullable=False, server_default='127.0.0.1'),
        sa.Column('UpdatedAt', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['UserID'], ['users.UserID'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('DeviceID')
    )
    op.create_index(op.f('ix_devices_DeviceID'), 'devices', ['DeviceID'], unique=False)
    op.create_index(op.f('ix_devices_UserID'), 'devices', ['UserID'], unique=False)
    op.create_index(op.f('ix_devices_DeviceFingerprint'), 'devices', ['DeviceFingerprint'], unique=False)

    # 4. Create Sessions Table
    op.create_table(
        'sessions',
        sa.Column('SessionID', sa.UUID(), nullable=False),
        sa.Column('UserID', sa.UUID(), nullable=False),
        sa.Column('DeviceID', sa.UUID(), nullable=False),
        sa.Column('LoginTime', sa.DateTime(timezone=True), nullable=False),
        sa.Column('IPAddress', sa.String(length=64), nullable=False),
        sa.Column('Location', sa.String(length=255), nullable=False, server_default='Unknown'),
        sa.Column('IsActive', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['DeviceID'], ['devices.DeviceID'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['UserID'], ['users.UserID'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('SessionID')
    )
    op.create_index(op.f('ix_sessions_SessionID'), 'sessions', ['SessionID'], unique=False)
    op.create_index(op.f('ix_sessions_UserID'), 'sessions', ['UserID'], unique=False)
    op.create_index(op.f('ix_sessions_DeviceID'), 'sessions', ['DeviceID'], unique=False)
    op.create_index(op.f('ix_sessions_IsActive'), 'sessions', ['IsActive'], unique=False)

    # 5. Create Auth Tokens Table
    op.create_table(
        'auth_tokens',
        sa.Column('TokenID', sa.UUID(), nullable=False),
        sa.Column('UserID', sa.UUID(), nullable=False),
        sa.Column('RefreshToken', sa.String(length=512), nullable=False),
        sa.Column('IsRevoked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('ExpiresAt', sa.DateTime(timezone=True), nullable=False),
        sa.Column('CreatedAt', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['UserID'], ['users.UserID'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('TokenID')
    )
    op.create_index(op.f('ix_auth_tokens_TokenID'), 'auth_tokens', ['TokenID'], unique=False)
    op.create_index(op.f('ix_auth_tokens_UserID'), 'auth_tokens', ['UserID'], unique=False)
    op.create_index(op.f('ix_auth_tokens_RefreshToken'), 'auth_tokens', ['RefreshToken'], unique=True)
    op.create_index(op.f('ix_auth_tokens_IsRevoked'), 'auth_tokens', ['IsRevoked'], unique=False)
    op.create_index(op.f('ix_auth_tokens_ExpiresAt'), 'auth_tokens', ['ExpiresAt'], unique=False)

    # 6. Create Transactions Table
    op.create_table(
        'transactions',
        sa.Column('TransactionID', sa.UUID(), nullable=False),
        sa.Column('AccountID', sa.UUID(), nullable=False),
        sa.Column('Amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column(
            'TransactionType',
            sa.Enum('Transfer', 'Deposit', 'Withdrawal', 'Payment', name='transaction_type_enum'),
            nullable=False,
            server_default='Transfer',
        ),
        sa.Column('SenderAccount', sa.String(length=64), nullable=False),
        sa.Column('ReceiverAccount', sa.String(length=64), nullable=False),
        sa.Column(
            'Status',
            sa.Enum('Approved', 'Pending', 'Blocked', name='transaction_status_enum'),
            nullable=False,
            server_default='Pending',
        ),
        sa.Column('Timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['AccountID'], ['accounts.AccountID'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('TransactionID')
    )
    op.create_index(op.f('ix_transactions_TransactionID'), 'transactions', ['TransactionID'], unique=False)
    op.create_index(op.f('ix_transactions_AccountID'), 'transactions', ['AccountID'], unique=False)
    op.create_index(op.f('ix_transactions_SenderAccount'), 'transactions', ['SenderAccount'], unique=False)
    op.create_index(op.f('ix_transactions_ReceiverAccount'), 'transactions', ['ReceiverAccount'], unique=False)
    op.create_index(op.f('ix_transactions_Status'), 'transactions', ['Status'], unique=False)
    op.create_index(op.f('ix_transactions_Timestamp'), 'transactions', ['Timestamp'], unique=False)

    # 7. Create Fraud Alerts Table
    op.create_table(
        'fraud_alerts',
        sa.Column('AlertID', sa.UUID(), nullable=False),
        sa.Column('TransactionID', sa.UUID(), nullable=False),
        sa.Column('RiskScore', sa.Float(), nullable=False),
        sa.Column(
            'AlertLevel',
            sa.Enum('Low', 'Medium', 'High', name='alert_level_enum'),
            nullable=False,
            server_default='Low',
        ),
        sa.Column(
            'Decision',
            sa.Enum('Approved', 'Step-Up Required', 'Blocked', name='alert_decision_enum'),
            nullable=False,
            server_default='Approved',
        ),
        sa.Column('Explanations', sa.JSON(), nullable=True),
        sa.Column('CreatedAt', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['TransactionID'], ['transactions.TransactionID'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('AlertID'),
        sa.UniqueConstraint('TransactionID')
    )
    op.create_index(op.f('ix_fraud_alerts_AlertID'), 'fraud_alerts', ['AlertID'], unique=False)
    op.create_index(op.f('ix_fraud_alerts_TransactionID'), 'fraud_alerts', ['TransactionID'], unique=True)
    op.create_index(op.f('ix_fraud_alerts_RiskScore'), 'fraud_alerts', ['RiskScore'], unique=False)
    op.create_index(op.f('ix_fraud_alerts_AlertLevel'), 'fraud_alerts', ['AlertLevel'], unique=False)
    op.create_index(op.f('ix_fraud_alerts_Decision'), 'fraud_alerts', ['Decision'], unique=False)
    op.create_index(op.f('ix_fraud_alerts_CreatedAt'), 'fraud_alerts', ['CreatedAt'], unique=False)


def downgrade() -> None:
    op.drop_table('fraud_alerts')
    op.drop_table('transactions')
    op.drop_table('auth_tokens')
    op.drop_table('sessions')
    op.drop_table('devices')
    op.drop_table('accounts')
    op.drop_table('users')

    # Drop ENUM types
    sa.Enum(name='alert_decision_enum').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='alert_level_enum').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='transaction_status_enum').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='transaction_type_enum').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='kyc_status_enum').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='account_type_enum').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='user_role_enum').drop(op.get_bind(), checkfirst=True)
