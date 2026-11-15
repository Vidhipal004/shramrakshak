"""Add marketplace listing details, coordinates, and applications.

Revision ID: 0002_job_marketplace
Revises: 0001_initial_schema
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_job_marketplace"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workers", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("workers", sa.Column("longitude", sa.Float(), nullable=True))
    with op.batch_alter_table("workers") as batch:
        batch.create_check_constraint(
            "ck_workers_coordinate_pair",
            "(latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL AND longitude IS NOT NULL)",
        )
        batch.create_check_constraint("ck_workers_latitude_range", "latitude IS NULL OR latitude BETWEEN -90 AND 90")
        batch.create_check_constraint("ck_workers_longitude_range", "longitude IS NULL OR longitude BETWEEN -180 AND 180")

    op.add_column("jobs", sa.Column("occupation", sa.String(length=120), nullable=True))
    op.add_column("jobs", sa.Column("skill", sa.String(length=120), nullable=True))
    op.add_column("jobs", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("jobs", sa.Column("longitude", sa.Float(), nullable=True))
    op.add_column("jobs", sa.Column("working_hours", sa.String(length=100), nullable=True))
    op.add_column("jobs", sa.Column("payment_terms", sa.String(length=500), nullable=True))
    op.add_column("jobs", sa.Column("start_date", sa.Date(), nullable=True))

    # Backfill the original starter listing rows before enforcing the fields
    # required by newly created marketplace listings.
    op.execute(sa.text("UPDATE jobs SET occupation = title WHERE occupation IS NULL"))
    op.execute(sa.text("UPDATE jobs SET working_hours = 'unspecified' WHERE working_hours IS NULL"))
    op.execute(sa.text("UPDATE jobs SET payment_terms = 'unspecified' WHERE payment_terms IS NULL"))
    op.execute(sa.text("UPDATE jobs SET start_date = CURRENT_DATE WHERE start_date IS NULL"))
    with op.batch_alter_table("jobs") as batch:
        for column in ("occupation", "working_hours", "payment_terms", "start_date"):
            batch.alter_column(column, nullable=False)
        batch.create_check_constraint(
            "ck_jobs_coordinate_pair",
            "(latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL AND longitude IS NOT NULL)",
        )
        batch.create_check_constraint("ck_jobs_latitude_range", "latitude IS NULL OR latitude BETWEEN -90 AND 90")
        batch.create_check_constraint("ck_jobs_longitude_range", "longitude IS NULL OR longitude BETWEEN -180 AND 180")

    op.create_table(
        "job_applications",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("job_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("worker_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'accepted', 'rejected', 'withdrawn')", name="ck_job_applications_status"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "worker_id", name="uq_job_applications_job_worker"),
    )
    op.create_index("ix_job_applications_job_id", "job_applications", ["job_id"])
    op.create_index("ix_job_applications_worker_id", "job_applications", ["worker_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text("ALTER TABLE public.job_applications ENABLE ROW LEVEL SECURITY"))


def downgrade() -> None:
    op.drop_index("ix_job_applications_worker_id", table_name="job_applications")
    op.drop_index("ix_job_applications_job_id", table_name="job_applications")
    op.drop_table("job_applications")
    with op.batch_alter_table("jobs") as batch:
        for name in ("ck_jobs_longitude_range", "ck_jobs_latitude_range", "ck_jobs_coordinate_pair"):
            batch.drop_constraint(name, type_="check")
        for column in ("start_date", "payment_terms", "working_hours", "longitude", "latitude", "skill", "occupation"):
            batch.drop_column(column)
    with op.batch_alter_table("workers") as batch:
        for name in ("ck_workers_longitude_range", "ck_workers_latitude_range", "ck_workers_coordinate_pair"):
            batch.drop_constraint(name, type_="check")
        batch.drop_column("longitude")
        batch.drop_column("latitude")
