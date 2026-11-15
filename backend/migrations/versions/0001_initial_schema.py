"""Create user profiles and ShramRakshak core tables.

Revision ID: 0001_initial_schema
Revises:
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Supabase's auth.users table exists only on PostgreSQL. Local SQLite
    # development keeps the application profile table self-contained.
    auth_user_fk = (
        [sa.ForeignKeyConstraint(["id"], ["auth.users.id"], ondelete="CASCADE")]
        if op.get_bind().dialect.name == "postgresql"
        else []
    )
    # Supabase Auth owns auth.users. The public profile uses the Auth UUID as
    # its primary key and is deleted when that Auth user is deleted.
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('worker', 'contractor', 'admin')", name="ck_users_role"),
        *auth_user_fk,
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "workers",
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("state", sa.String(length=120), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "contractors",
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("business_name", sa.String(length=200), nullable=True),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("state", sa.String(length=120), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("contractor_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=300), nullable=False),
        sa.Column("wage_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("wage_period", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("wage_amount >= 0", name="ck_jobs_wage_nonnegative"),
        sa.CheckConstraint("status IN ('open', 'filled', 'cancelled')", name="ck_jobs_status"),
        sa.ForeignKeyConstraint(["contractor_id"], ["contractors.user_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_contractor_id", "jobs", ["contractor_id"])

    # These tables are managed through the backend API. Enable RLS without
    # client policies so browser/mobile clients cannot query records directly.
    if op.get_bind().dialect.name == "postgresql":
        for table in ("users", "workers", "contractors", "jobs"):
            op.execute(sa.text(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY"))


def downgrade() -> None:
    op.drop_index("ix_jobs_contractor_id", table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("contractors")
    op.drop_table("workers")
    op.drop_table("users")
