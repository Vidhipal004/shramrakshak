"""Add worker offer records and verified contractor trust evidence.

Revision ID: 0003_offer_scanner_trust_score
Revises: 0002_job_marketplace
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_offer_scanner_trust_score"
down_revision = "0002_job_marketplace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contractors", sa.Column("verification_status", sa.String(length=20), nullable=False, server_default="unverified"))
    op.add_column("contractors", sa.Column("verification_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contractors", sa.Column("verification_updated_by", sa.Uuid(as_uuid=True), nullable=True))
    # SQLite cannot ADD constraints with ALTER TABLE. Alembic batch mode
    # rebuilds the table while preserving its existing rows and constraints.
    with op.batch_alter_table("contractors") as batch:
        batch.create_check_constraint("ck_contractors_verification_status", "verification_status IN ('unverified', 'verified')")
        batch.create_foreign_key("fk_contractors_verification_updated_by_users", "users", ["verification_updated_by"], ["id"], ondelete="SET NULL")

    op.create_table(
        "offer_records",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("worker_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("contractor_name", sa.String(length=200), nullable=True),
        sa.Column("occupation", sa.String(length=120), nullable=True),
        sa.Column("wage_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("wage_period", sa.String(length=30), nullable=True),
        sa.Column("working_hours", sa.String(length=150), nullable=True),
        sa.Column("location", sa.String(length=300), nullable=True),
        sa.Column("payment_terms", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("source_type", sa.String(length=12), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("source_type IN ('text', 'image', 'both')", name="ck_offer_records_source_type"),
        sa.CheckConstraint("wage_amount IS NULL OR wage_amount >= 0", name="ck_offer_records_wage_nonnegative"),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_offer_records_worker_id", "offer_records", ["worker_id"])

    op.create_table(
        "wage_evidence",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("application_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("contractor_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("agreed_wage", sa.Numeric(12, 2), nullable=False),
        sa.Column("paid_wage", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_verified", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("dispute_status", sa.String(length=20), server_default="none", nullable=False),
        sa.Column("verified_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("agreed_wage > 0", name="ck_wage_evidence_agreed_positive"),
        sa.CheckConstraint("paid_wage >= 0", name="ck_wage_evidence_paid_nonnegative"),
        sa.CheckConstraint("dispute_status IN ('none', 'unresolved', 'resolved')", name="ck_wage_evidence_dispute_status"),
        sa.ForeignKeyConstraint(["application_id"], ["job_applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contractor_id"], ["contractors.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", name="uq_wage_evidence_application"),
    )
    op.create_index("ix_wage_evidence_contractor_id", "wage_evidence", ["contractor_id"])

    op.create_table(
        "job_outcome_evidence",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("application_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("contractor_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("dispute_status", sa.String(length=20), server_default="none", nullable=False),
        sa.Column("verified_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("dispute_status IN ('none', 'unresolved', 'resolved')", name="ck_job_outcome_dispute_status"),
        sa.ForeignKeyConstraint(["application_id"], ["job_applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contractor_id"], ["contractors.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", name="uq_job_outcome_application"),
    )
    op.create_index("ix_job_outcome_evidence_contractor_id", "job_outcome_evidence", ["contractor_id"])

    op.create_table(
        "contractor_feedback",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("application_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("contractor_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("worker_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("feedback_text", sa.Text(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("dispute_status", sa.String(length=20), server_default="none", nullable=False),
        sa.Column("verified_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_contractor_feedback_rating"),
        sa.CheckConstraint("dispute_status IN ('none', 'unresolved', 'resolved')", name="ck_contractor_feedback_dispute_status"),
        sa.ForeignKeyConstraint(["application_id"], ["job_applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contractor_id"], ["contractors.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", name="uq_contractor_feedback_application"),
    )
    op.create_index("ix_contractor_feedback_contractor_id", "contractor_feedback", ["contractor_id"])

    if op.get_bind().dialect.name == "postgresql":
        for table in ("offer_records", "wage_evidence", "job_outcome_evidence", "contractor_feedback"):
            op.execute(sa.text(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY"))


def downgrade() -> None:
    op.drop_index("ix_contractor_feedback_contractor_id", table_name="contractor_feedback")
    op.drop_table("contractor_feedback")
    op.drop_index("ix_job_outcome_evidence_contractor_id", table_name="job_outcome_evidence")
    op.drop_table("job_outcome_evidence")
    op.drop_index("ix_wage_evidence_contractor_id", table_name="wage_evidence")
    op.drop_table("wage_evidence")
    op.drop_index("ix_offer_records_worker_id", table_name="offer_records")
    op.drop_table("offer_records")
    with op.batch_alter_table("contractors") as batch:
        batch.drop_constraint("fk_contractors_verification_updated_by_users", type_="foreignkey")
        batch.drop_constraint("ck_contractors_verification_status", type_="check")
        batch.drop_column("verification_updated_by")
        batch.drop_column("verification_updated_at")
        batch.drop_column("verification_status")
