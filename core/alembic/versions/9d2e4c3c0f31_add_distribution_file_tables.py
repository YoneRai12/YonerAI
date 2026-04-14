"""Add distribution file tables

Revision ID: 9d2e4c3c0f31
Revises: 3db9d455434e
Create Date: 2026-04-10 14:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9d2e4c3c0f31"
down_revision: Union[str, Sequence[str], None] = "3db9d455434e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tool_calls",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("tool_name", sa.String(), nullable=False),
        sa.Column("args_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("artifact_ref", sa.String(), nullable=True),
        sa.Column("lease_token", sa.String(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "id", name="uq_tool_call_user_id"),
    )
    with op.batch_alter_table("tool_calls", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_tool_calls_run_id"), ["run_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_tool_calls_user_id"), ["user_id"], unique=False)

    op.create_table(
        "distribution_files",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("owner_user_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=True),
        sa.Column("tool_call_id", sa.String(), nullable=True),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("media_type", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.ForeignKeyConstraint(["tool_call_id"], ["tool_calls.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("distribution_files", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_distribution_files_owner_user_id"), ["owner_user_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_distribution_files_run_id"), ["run_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_distribution_files_tool_call_id"), ["tool_call_id"], unique=False)

    op.create_table(
        "distribution_file_tickets",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("file_id", sa.String(), nullable=False),
        sa.Column("owner_user_id", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["file_id"], ["distribution_files.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("distribution_file_tickets", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_distribution_file_tickets_file_id"), ["file_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_distribution_file_tickets_owner_user_id"), ["owner_user_id"], unique=False)

    op.create_table(
        "distribution_file_audit",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("file_id", sa.String(), nullable=False),
        sa.Column("owner_user_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("ticket_id", sa.String(), nullable=True),
        sa.Column("remote_address", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["file_id"], ["distribution_files.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["distribution_file_tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("distribution_file_audit", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_distribution_file_audit_file_id"), ["file_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_distribution_file_audit_owner_user_id"), ["owner_user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("distribution_file_audit", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_distribution_file_audit_owner_user_id"))
        batch_op.drop_index(batch_op.f("ix_distribution_file_audit_file_id"))
    op.drop_table("distribution_file_audit")

    with op.batch_alter_table("distribution_file_tickets", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_distribution_file_tickets_owner_user_id"))
        batch_op.drop_index(batch_op.f("ix_distribution_file_tickets_file_id"))
    op.drop_table("distribution_file_tickets")

    with op.batch_alter_table("distribution_files", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_distribution_files_tool_call_id"))
        batch_op.drop_index(batch_op.f("ix_distribution_files_run_id"))
        batch_op.drop_index(batch_op.f("ix_distribution_files_owner_user_id"))
    op.drop_table("distribution_files")

    with op.batch_alter_table("tool_calls", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_tool_calls_user_id"))
        batch_op.drop_index(batch_op.f("ix_tool_calls_run_id"))
    op.drop_table("tool_calls")
