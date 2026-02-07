"""add artifact index table and workflow snapshot

Revision ID: 0003_add_artifact_index_and_workflow_snapshot
Revises: 0002_add_optimization_run_tables
Create Date: 2026-02-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0003_add_artifact_index_and_workflow_snapshot"
down_revision = "0002_add_optimization_run_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("agent_versions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("workflow_snapshot", sa.Text(), nullable=False, server_default="")
        )

    op.create_table(
        "optimization_artifacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("uri", sa.String(length=1024), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["optimization_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "artifact_type", name="uq_optimization_artifacts_run_type"),
    )
    op.create_index(
        "ix_optimization_artifacts_run_id",
        "optimization_artifacts",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        "ix_optimization_artifacts_uri",
        "optimization_artifacts",
        ["uri"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_optimization_artifacts_uri", table_name="optimization_artifacts")
    op.drop_index("ix_optimization_artifacts_run_id", table_name="optimization_artifacts")
    op.drop_table("optimization_artifacts")

    with op.batch_alter_table("agent_versions", schema=None) as batch_op:
        batch_op.drop_column("workflow_snapshot")
