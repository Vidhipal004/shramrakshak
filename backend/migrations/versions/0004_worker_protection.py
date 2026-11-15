"""Add wage agreements, travel checks, work reality, and complaints.

Revision ID: 0004_worker_protection
Revises: 0003_offer_scanner_trust_score
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_worker_protection"
down_revision = "0003_offer_scanner_trust_score"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wage_agreements",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("application_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("job_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("worker_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("contractor_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["job_applications.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.user_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["contractor_id"], ["contractors.user_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id"),
    )
    for column in ("job_id", "worker_id", "contractor_id"):
        op.create_index(f"ix_wage_agreements_{column}", "wage_agreements", [column])

    op.create_table(
        "wage_agreement_versions",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("agreement_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("accepted_wage", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), server_default="INR", nullable=False),
        sa.Column("wage_period", sa.String(length=30), nullable=False),
        sa.Column("working_hours", sa.String(length=150), nullable=False),
        sa.Column("location", sa.String(length=300), nullable=False),
        sa.Column("payment_terms", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("proposed_by", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("proposed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("worker_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contractor_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("version_number >= 1", name="ck_agreement_version_number_positive"),
        sa.CheckConstraint("accepted_wage > 0", name="ck_agreement_version_wage_positive"),
        sa.CheckConstraint("status IN ('pending', 'accepted', 'rejected')", name="ck_agreement_version_status"),
        sa.ForeignKeyConstraint(["agreement_id"], ["wage_agreements.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["proposed_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agreement_id", "version_number", name="uq_agreement_version_number"),
    )
    op.create_index("ix_wage_agreement_versions_agreement_id", "wage_agreement_versions", ["agreement_id"])

    op.create_table(
        "travel_confirmations",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("agreement_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("agreement_version_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("worker_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("contractor_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("travel_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="requested", nullable=False),
        sa.Column("reconfirmed_terms", sa.JSON(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("departure_recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('requested', 'confirmed', 'terms_changed')", name="ck_travel_confirmation_status"),
        sa.ForeignKeyConstraint(["agreement_id"], ["wage_agreements.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["agreement_version_id"], ["wage_agreement_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.user_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["contractor_id"], ["contractors.user_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_travel_confirmations_agreement_id", "travel_confirmations", ["agreement_id"])
    op.create_index("ix_travel_confirmations_worker_id", "travel_confirmations", ["worker_id"])
    op.create_index("ix_travel_confirmations_contractor_id", "travel_confirmations", ["contractor_id"])

    op.create_table(
        "work_reality_reports",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("agreement_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("agreement_version_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("worker_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("contractor_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("actual_wage", sa.Numeric(12, 2), nullable=True),
        sa.Column("actual_hours", sa.Float(), nullable=True),
        sa.Column("payment_status", sa.String(length=20), nullable=False),
        sa.Column("worker_notes", sa.Text(), nullable=True),
        sa.Column("reported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("actual_wage IS NULL OR actual_wage >= 0", name="ck_reality_actual_wage_nonnegative"),
        sa.CheckConstraint("actual_hours IS NULL OR actual_hours >= 0", name="ck_reality_actual_hours_nonnegative"),
        sa.CheckConstraint("payment_status IN ('paid', 'partially_paid', 'unpaid', 'pending')", name="ck_reality_payment_status"),
        sa.ForeignKeyConstraint(["agreement_id"], ["wage_agreements.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["agreement_version_id"], ["wage_agreement_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.user_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["contractor_id"], ["contractors.user_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agreement_version_id", "work_date", name="uq_reality_version_work_date"),
    )
    op.create_index("ix_work_reality_reports_agreement_id", "work_reality_reports", ["agreement_id"])
    op.create_index("ix_work_reality_reports_worker_id", "work_reality_reports", ["worker_id"])
    op.create_index("ix_work_reality_reports_contractor_id", "work_reality_reports", ["contractor_id"])

    op.create_table(
        "protection_complaints",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("worker_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("contractor_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("job_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("agreement_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("reality_report_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="submitted", nullable=False),
        sa.Column("resolution_outcome", sa.String(length=30), nullable=True),
        sa.Column("resolution_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("category IN ('wage', 'hours', 'job_mismatch', 'payment', 'safety', 'other')", name="ck_complaints_category"),
        sa.CheckConstraint("status IN ('submitted', 'contractor_responded', 'under_review', 'resolved', 'dismissed')", name="ck_complaints_status"),
        sa.CheckConstraint("resolution_outcome IS NULL OR resolution_outcome IN ('worker_upheld', 'contractor_upheld', 'inconclusive')", name="ck_complaints_outcome"),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.user_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["contractor_id"], ["contractors.user_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["agreement_id"], ["wage_agreements.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reality_report_id"], ["work_reality_reports.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_protection_complaints_worker_id", "protection_complaints", ["worker_id"])
    op.create_index("ix_protection_complaints_contractor_id", "protection_complaints", ["contractor_id"])

    op.create_table(
        "complaint_responses",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("complaint_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("author_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["complaint_id"], ["protection_complaints.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_complaint_responses_complaint_id", "complaint_responses", ["complaint_id"])

    op.create_table(
        "complaint_evidence",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("complaint_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["complaint_id"], ["protection_complaints.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_complaint_evidence_complaint_id", "complaint_evidence", ["complaint_id"])

    op.create_table(
        "complaint_reviews",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("complaint_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("admin_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("outcome", sa.String(length=30), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["complaint_id"], ["protection_complaints.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["admin_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_complaint_reviews_complaint_id", "complaint_reviews", ["complaint_id"])

    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        for table in (
            "wage_agreements", "wage_agreement_versions", "travel_confirmations", "work_reality_reports",
            "protection_complaints", "complaint_responses", "complaint_evidence", "complaint_reviews",
        ):
            op.execute(sa.text(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY"))

        # Acceptance metadata may change; the original agreement terms cannot.
        op.execute(sa.text("""
            CREATE FUNCTION public.prevent_agreement_version_terms_change() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
              IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Agreement versions are immutable';
              END IF;
              IF ROW(OLD.agreement_id, OLD.version_number, OLD.accepted_wage, OLD.currency,
                     OLD.wage_period, OLD.working_hours, OLD.location, OLD.payment_terms,
                     OLD.start_date, OLD.proposed_by, OLD.proposed_at)
                 IS DISTINCT FROM
                 ROW(NEW.agreement_id, NEW.version_number, NEW.accepted_wage, NEW.currency,
                     NEW.wage_period, NEW.working_hours, NEW.location, NEW.payment_terms,
                     NEW.start_date, NEW.proposed_by, NEW.proposed_at) THEN
                RAISE EXCEPTION 'Agreement version terms are immutable; add a new version';
              END IF;
              RETURN NEW;
            END;
            $$
        """))
        op.execute(sa.text("""
            CREATE TRIGGER trg_agreement_versions_immutable
            BEFORE UPDATE OR DELETE ON public.wage_agreement_versions
            FOR EACH ROW EXECUTE FUNCTION public.prevent_agreement_version_terms_change()
        """))
    elif dialect == "sqlite":
        op.execute(sa.text("""
            CREATE TRIGGER trg_agreement_versions_immutable
            BEFORE UPDATE ON wage_agreement_versions
            WHEN OLD.agreement_id IS NOT NEW.agreement_id
              OR OLD.version_number IS NOT NEW.version_number
              OR OLD.accepted_wage IS NOT NEW.accepted_wage
              OR OLD.currency IS NOT NEW.currency
              OR OLD.wage_period IS NOT NEW.wage_period
              OR OLD.working_hours IS NOT NEW.working_hours
              OR OLD.location IS NOT NEW.location
              OR OLD.payment_terms IS NOT NEW.payment_terms
              OR OLD.start_date IS NOT NEW.start_date
              OR OLD.proposed_by IS NOT NEW.proposed_by
              OR OLD.proposed_at IS NOT NEW.proposed_at
            BEGIN
              SELECT RAISE(ABORT, 'Agreement version terms are immutable; add a new version');
            END
        """))
        op.execute(sa.text("""
            CREATE TRIGGER trg_agreement_versions_no_delete
            BEFORE DELETE ON wage_agreement_versions
            BEGIN
              SELECT RAISE(ABORT, 'Agreement versions are immutable');
            END
        """))


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(sa.text("DROP TRIGGER IF EXISTS trg_agreement_versions_immutable ON public.wage_agreement_versions"))
        op.execute(sa.text("DROP FUNCTION IF EXISTS public.prevent_agreement_version_terms_change()"))
    elif dialect == "sqlite":
        op.execute(sa.text("DROP TRIGGER IF EXISTS trg_agreement_versions_immutable"))
        op.execute(sa.text("DROP TRIGGER IF EXISTS trg_agreement_versions_no_delete"))
    op.drop_index("ix_complaint_reviews_complaint_id", table_name="complaint_reviews")
    op.drop_table("complaint_reviews")
    op.drop_index("ix_complaint_evidence_complaint_id", table_name="complaint_evidence")
    op.drop_table("complaint_evidence")
    op.drop_index("ix_complaint_responses_complaint_id", table_name="complaint_responses")
    op.drop_table("complaint_responses")
    op.drop_index("ix_protection_complaints_contractor_id", table_name="protection_complaints")
    op.drop_index("ix_protection_complaints_worker_id", table_name="protection_complaints")
    op.drop_table("protection_complaints")
    op.drop_index("ix_work_reality_reports_contractor_id", table_name="work_reality_reports")
    op.drop_index("ix_work_reality_reports_worker_id", table_name="work_reality_reports")
    op.drop_index("ix_work_reality_reports_agreement_id", table_name="work_reality_reports")
    op.drop_table("work_reality_reports")
    op.drop_index("ix_travel_confirmations_contractor_id", table_name="travel_confirmations")
    op.drop_index("ix_travel_confirmations_worker_id", table_name="travel_confirmations")
    op.drop_index("ix_travel_confirmations_agreement_id", table_name="travel_confirmations")
    op.drop_table("travel_confirmations")
    op.drop_index("ix_wage_agreement_versions_agreement_id", table_name="wage_agreement_versions")
    op.drop_table("wage_agreement_versions")
    op.drop_index("ix_wage_agreements_contractor_id", table_name="wage_agreements")
    op.drop_index("ix_wage_agreements_worker_id", table_name="wage_agreements")
    op.drop_index("ix_wage_agreements_job_id", table_name="wage_agreements")
    op.drop_table("wage_agreements")
