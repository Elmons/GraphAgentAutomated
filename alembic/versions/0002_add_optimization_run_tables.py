"""add optimization run tables

Revision ID: 0002_add_optimization_run_tables
Revises: 0001_init_schema
Create Date: 2026-02-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002_add_optimization_run_tables"
down_revision = "0001_init_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "optimization_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("task_desc", sa.Text(), nullable=False),
        sa.Column("dataset_report_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("best_blueprint_id", sa.String(length=128), nullable=False),
        sa.Column("best_train_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("best_val_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("best_test_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("artifact_dir", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_optimization_runs_run_id", "optimization_runs", ["run_id"], unique=True)

    op.create_table(
        "optimization_round_traces",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("round_num", sa.Integer(), nullable=False),
        sa.Column("selected_node_id", sa.String(length=64), nullable=False),
        sa.Column("selected_blueprint_id", sa.String(length=128), nullable=False),
        sa.Column("mutation", sa.String(length=256), nullable=False),
        sa.Column("train_objective", sa.Float(), nullable=False, server_default="0"),
        sa.Column("val_objective", sa.Float(), nullable=False, server_default="0"),
        sa.Column("best_train_objective", sa.Float(), nullable=False, server_default="0"),
        sa.Column("best_val_objective", sa.Float(), nullable=False, server_default="0"),
        sa.Column("improvement", sa.Float(), nullable=False, server_default="0"),
        sa.Column("regret", sa.Float(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["run_id"], ["optimization_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    with op.batch_alter_table("agent_versions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("run_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_agent_versions_run_id_optimization_runs",
            "optimization_runs",
            ["run_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("agent_versions", schema=None) as batch_op:
        batch_op.drop_constraint("fk_agent_versions_run_id_optimization_runs", type_="foreignkey")
        batch_op.drop_column("run_id")

    op.drop_table("optimization_round_traces")
    op.drop_index("ix_optimization_runs_run_id", table_name="optimization_runs")
    op.drop_table("optimization_runs")
