import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, LargeBinary, Numeric, String, Text, Uuid, UniqueConstraint, func
from sqlalchemy.types import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Role(str, enum.Enum):
    WORKER = "worker"
    CONTRACTOR = "contractor"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('worker', 'contractor', 'admin')", name="ck_users_role"),
    )

    # IDs are issued by Supabase Auth (auth.users); the Alembic migration adds
    # the cross-schema FK. Keeping it out of metadata allows SQLite unit tests.
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    worker: Mapped["Worker | None"] = relationship(back_populates="user", cascade="all, delete-orphan")
    contractor: Mapped["Contractor | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", foreign_keys="Contractor.user_id"
    )


class Worker(Base):
    __tablename__ = "workers"
    __table_args__ = (
        CheckConstraint("(latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL AND longitude IS NOT NULL)", name="ck_workers_coordinate_pair"),
        CheckConstraint("latitude IS NULL OR latitude BETWEEN -90 AND 90", name="ck_workers_latitude_range"),
        CheckConstraint("longitude IS NULL OR longitude BETWEEN -180 AND 180", name="ck_workers_longitude_range"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    phone: Mapped[str | None] = mapped_column(String(30))
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(120))
    latitude: Mapped[float | None] = mapped_column()
    longitude: Mapped[float | None] = mapped_column()
    user: Mapped[User] = relationship(back_populates="worker")


class Contractor(Base):
    __tablename__ = "contractors"
    __table_args__ = (
        CheckConstraint("verification_status IN ('unverified', 'verified')", name="ck_contractors_verification_status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    business_name: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(30))
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(120))
    verification_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unverified")
    verification_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    user: Mapped[User] = relationship(back_populates="contractor", foreign_keys=[user_id])
    jobs: Mapped[list["Job"]] = relationship(back_populates="contractor")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint("wage_amount >= 0", name="ck_jobs_wage_nonnegative"),
        CheckConstraint("status IN ('open', 'filled', 'cancelled')", name="ck_jobs_status"),
        CheckConstraint("(latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL AND longitude IS NOT NULL)", name="ck_jobs_coordinate_pair"),
        CheckConstraint("latitude IS NULL OR latitude BETWEEN -90 AND 90", name="ck_jobs_latitude_range"),
        CheckConstraint("longitude IS NULL OR longitude BETWEEN -180 AND 180", name="ck_jobs_longitude_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contractor_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("contractors.user_id", ondelete="RESTRICT"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    occupation: Mapped[str] = mapped_column(String(120), nullable=False)
    skill: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str] = mapped_column(String(300), nullable=False)
    latitude: Mapped[float | None] = mapped_column()
    longitude: Mapped[float | None] = mapped_column()
    wage_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    wage_period: Mapped[str] = mapped_column(String(30), nullable=False, default="day")
    working_hours: Mapped[str] = mapped_column(String(100), nullable=False)
    payment_terms: Mapped[str] = mapped_column(String(500), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    contractor: Mapped[Contractor] = relationship(back_populates="jobs")


class JobApplication(Base):
    __tablename__ = "job_applications"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'accepted', 'rejected', 'withdrawn')", name="ck_job_applications_status"),
        UniqueConstraint("job_id", "worker_id", name="uq_job_applications_job_worker"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    worker_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workers.user_id", ondelete="CASCADE"), nullable=False, index=True)
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    job: Mapped[Job] = relationship()
    worker: Mapped[Worker] = relationship()


class OfferRecord(Base):
    """Worker-confirmed structured terms. Original uploads are not retained."""

    __tablename__ = "offer_records"
    __table_args__ = (
        CheckConstraint("source_type IN ('text', 'image', 'both')", name="ck_offer_records_source_type"),
        CheckConstraint("wage_amount IS NULL OR wage_amount >= 0", name="ck_offer_records_wage_nonnegative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workers.user_id", ondelete="CASCADE"), nullable=False, index=True)
    contractor_name: Mapped[str | None] = mapped_column(String(200))
    occupation: Mapped[str | None] = mapped_column(String(120))
    wage_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(8))
    wage_period: Mapped[str | None] = mapped_column(String(30))
    working_hours: Mapped[str | None] = mapped_column(String(150))
    location: Mapped[str | None] = mapped_column(String(300))
    payment_terms: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date | None] = mapped_column(Date)
    source_type: Mapped[str] = mapped_column(String(12), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WageEvidence(Base):
    __tablename__ = "wage_evidence"
    __table_args__ = (
        CheckConstraint("agreed_wage > 0", name="ck_wage_evidence_agreed_positive"),
        CheckConstraint("paid_wage >= 0", name="ck_wage_evidence_paid_nonnegative"),
        CheckConstraint("dispute_status IN ('none', 'unresolved', 'resolved')", name="ck_wage_evidence_dispute_status"),
        UniqueConstraint("application_id", name="uq_wage_evidence_application"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("job_applications.id", ondelete="CASCADE"), nullable=False)
    contractor_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("contractors.user_id", ondelete="CASCADE"), nullable=False, index=True)
    agreed_wage: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    paid_wage: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dispute_status: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    verified_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JobOutcomeEvidence(Base):
    __tablename__ = "job_outcome_evidence"
    __table_args__ = (
        CheckConstraint("dispute_status IN ('none', 'unresolved', 'resolved')", name="ck_job_outcome_dispute_status"),
        UniqueConstraint("application_id", name="uq_job_outcome_application"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("job_applications.id", ondelete="CASCADE"), nullable=False)
    contractor_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("contractors.user_id", ondelete="CASCADE"), nullable=False, index=True)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dispute_status: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    verified_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContractorFeedback(Base):
    __tablename__ = "contractor_feedback"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_contractor_feedback_rating"),
        CheckConstraint("dispute_status IN ('none', 'unresolved', 'resolved')", name="ck_contractor_feedback_dispute_status"),
        UniqueConstraint("application_id", name="uq_contractor_feedback_application"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("job_applications.id", ondelete="CASCADE"), nullable=False)
    contractor_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("contractors.user_id", ondelete="CASCADE"), nullable=False, index=True)
    worker_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workers.user_id", ondelete="CASCADE"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    feedback_text: Mapped[str | None] = mapped_column(Text)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dispute_status: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    verified_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WageAgreement(Base):
    __tablename__ = "wage_agreements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("job_applications.id", ondelete="RESTRICT"), unique=True, nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False, index=True)
    worker_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workers.user_id", ondelete="RESTRICT"), nullable=False, index=True)
    contractor_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("contractors.user_id", ondelete="RESTRICT"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WageAgreementVersion(Base):
    __tablename__ = "wage_agreement_versions"
    __table_args__ = (
        CheckConstraint("version_number >= 1", name="ck_agreement_version_number_positive"),
        CheckConstraint("accepted_wage > 0", name="ck_agreement_version_wage_positive"),
        CheckConstraint("status IN ('pending', 'accepted', 'rejected')", name="ck_agreement_version_status"),
        UniqueConstraint("agreement_id", "version_number", name="uq_agreement_version_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agreement_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("wage_agreements.id", ondelete="RESTRICT"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    accepted_wage: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")
    wage_period: Mapped[str] = mapped_column(String(30), nullable=False)
    working_hours: Mapped[str] = mapped_column(String(150), nullable=False)
    location: Mapped[str] = mapped_column(String(300), nullable=False)
    payment_terms: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    proposed_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    worker_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contractor_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TravelConfirmation(Base):
    __tablename__ = "travel_confirmations"
    __table_args__ = (
        CheckConstraint("status IN ('requested', 'confirmed', 'terms_changed')", name="ck_travel_confirmation_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agreement_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("wage_agreements.id", ondelete="RESTRICT"), nullable=False, index=True)
    agreement_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("wage_agreement_versions.id", ondelete="RESTRICT"), nullable=False)
    worker_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workers.user_id", ondelete="RESTRICT"), nullable=False, index=True)
    contractor_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("contractors.user_id", ondelete="RESTRICT"), nullable=False, index=True)
    travel_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="requested")
    reconfirmed_terms: Mapped[dict | None] = mapped_column(JSON)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    departure_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkRealityReport(Base):
    __tablename__ = "work_reality_reports"
    __table_args__ = (
        CheckConstraint("actual_wage IS NULL OR actual_wage >= 0", name="ck_reality_actual_wage_nonnegative"),
        CheckConstraint("actual_hours IS NULL OR actual_hours >= 0", name="ck_reality_actual_hours_nonnegative"),
        CheckConstraint("payment_status IN ('paid', 'partially_paid', 'unpaid', 'pending')", name="ck_reality_payment_status"),
        UniqueConstraint("agreement_version_id", "work_date", name="uq_reality_version_work_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agreement_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("wage_agreements.id", ondelete="RESTRICT"), nullable=False, index=True)
    agreement_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("wage_agreement_versions.id", ondelete="RESTRICT"), nullable=False)
    worker_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workers.user_id", ondelete="RESTRICT"), nullable=False, index=True)
    contractor_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("contractors.user_id", ondelete="RESTRICT"), nullable=False, index=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_wage: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    actual_hours: Mapped[float | None] = mapped_column()
    payment_status: Mapped[str] = mapped_column(String(20), nullable=False)
    worker_notes: Mapped[str | None] = mapped_column(Text)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProtectionComplaint(Base):
    __tablename__ = "protection_complaints"
    __table_args__ = (
        CheckConstraint("category IN ('wage', 'hours', 'job_mismatch', 'payment', 'safety', 'other')", name="ck_complaints_category"),
        CheckConstraint("status IN ('submitted', 'contractor_responded', 'under_review', 'resolved', 'dismissed')", name="ck_complaints_status"),
        CheckConstraint("resolution_outcome IS NULL OR resolution_outcome IN ('worker_upheld', 'contractor_upheld', 'inconclusive')", name="ck_complaints_outcome"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workers.user_id", ondelete="RESTRICT"), nullable=False, index=True)
    contractor_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("contractors.user_id", ondelete="RESTRICT"), nullable=False, index=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"))
    agreement_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("wage_agreements.id", ondelete="SET NULL"))
    reality_report_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("work_reality_reports.id", ondelete="SET NULL"))
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="submitted")
    resolution_outcome: Mapped[str | None] = mapped_column(String(30))
    resolution_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ComplaintResponse(Base):
    __tablename__ = "complaint_responses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    complaint_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("protection_complaints.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ComplaintEvidence(Base):
    __tablename__ = "complaint_evidence"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    complaint_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("protection_complaints.id", ondelete="CASCADE"), nullable=False, index=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ComplaintReview(Base):
    __tablename__ = "complaint_reviews"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    complaint_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("protection_complaints.id", ondelete="CASCADE"), nullable=False, index=True)
    admin_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(30))
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
