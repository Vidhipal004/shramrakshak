import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.database import get_db
from app.models import (
    Contractor,
    ContractorFeedback,
    Job,
    JobApplication,
    JobOutcomeEvidence,
    Role,
    User,
    WageEvidence,
)

score_router = APIRouter(prefix="/contractors", tags=["JobTrust score"])
admin_router = APIRouter(prefix="/admin", tags=["trust evidence administration"])
feedback_router = APIRouter(tags=["worker feedback"])
AdminUser = Annotated[User, Depends(require_roles(Role.ADMIN))]
WorkerUser = Annotated[User, Depends(require_roles(Role.WORKER))]
AuthenticatedUser = Annotated[User, Depends(require_roles(Role.WORKER, Role.CONTRACTOR, Role.ADMIN))]

WEIGHTS = {
    "contractor_verification": 20,
    "wage_consistency": 25,
    "previous_job_completion": 20,
    "worker_feedback": 20,
    "job_information_completeness": 15,
}
MINIMUM_EVIDENCE_COVERAGE = 50


class ScoreComponent(BaseModel):
    key: str
    label: str
    weight_pct: int
    score: float | None
    available: bool
    evidence_count: int
    excluded_count: int
    reasons: list[str]


class Confidence(BaseModel):
    level: Literal["insufficient", "low", "medium", "high"]
    data_coverage_pct: float
    evidence_count: int
    basis: str


class JobTrustScore(BaseModel):
    contractor_id: uuid.UUID
    status: Literal["scored", "insufficient_data"]
    score: float | None
    score_scale: str = "0–100"
    confidence: Confidence
    components: list[ScoreComponent]
    reasons: list[str]
    policy: str


class ContractorDirectoryItem(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    business_name: str | None
    city: str | None
    state: str | None
    verification_status: str
    verification_updated_at: datetime | None


class VerificationUpdate(BaseModel):
    verification_status: Literal["verified", "unverified"]


class EvidenceDisputeStatus(BaseModel):
    dispute_status: Literal["none", "unresolved", "resolved"] = "none"


class WageEvidenceCreate(EvidenceDisputeStatus):
    application_id: uuid.UUID
    agreed_wage: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    paid_wage: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class JobOutcomeCreate(EvidenceDisputeStatus):
    application_id: uuid.UUID
    completed: bool


class FeedbackCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    feedback_text: str | None = Field(default=None, max_length=2000)


class FeedbackReview(BaseModel):
    is_verified: bool
    dispute_status: Literal["none", "unresolved", "resolved"]


class FeedbackSubmitted(BaseModel):
    id: uuid.UUID
    rating: int
    is_verified: bool
    message: str


def _component(key: str, label: str, score: float | None, evidence_count: int, reasons: list[str], excluded_count: int = 0) -> ScoreComponent:
    return ScoreComponent(
        key=key,
        label=label,
        weight_pct=WEIGHTS[key],
        score=round(score, 1) if score is not None else None,
        available=score is not None,
        evidence_count=evidence_count,
        excluded_count=excluded_count,
        reasons=reasons,
    )


def calculate_jobtrust_score(db: Session, contractor_id: uuid.UUID) -> JobTrustScore:
    contractor = db.get(Contractor, contractor_id)
    if contractor is None:
        raise HTTPException(status_code=404, detail="Contractor not found.")

    wage_all = db.scalars(select(WageEvidence).where(WageEvidence.contractor_id == contractor_id)).all()
    wage_valid = [row for row in wage_all if row.is_verified and row.dispute_status != "unresolved"]
    outcomes_all = db.scalars(select(JobOutcomeEvidence).where(JobOutcomeEvidence.contractor_id == contractor_id)).all()
    outcomes_valid = [row for row in outcomes_all if row.is_verified and row.dispute_status != "unresolved"]
    feedback_all = db.scalars(select(ContractorFeedback).where(ContractorFeedback.contractor_id == contractor_id)).all()
    feedback_valid = [row for row in feedback_all if row.is_verified and row.dispute_status != "unresolved"]
    jobs = db.scalars(select(Job).where(Job.contractor_id == contractor_id)).all()

    verification_score = 100.0 if contractor.verification_status == "verified" else 0.0
    verification_reason = (
        "Contractor verification is confirmed."
        if contractor.verification_status == "verified"
        else "Contractor is currently marked unverified; this is a verification status, not a fraud finding."
    )
    components = [
        _component("contractor_verification", "Contractor verification", verification_score, 1, [verification_reason]),
    ]

    if wage_valid:
        wage_ratios = [min(float(row.paid_wage / row.agreed_wage), 1.0) for row in wage_valid]
        wage_score = 100 * sum(wage_ratios) / len(wage_ratios)
        reasons = [f"Average paid-to-agreed wage ratio across {len(wage_valid)} verified, non-unresolved record(s)."]
        if len(wage_all) > len(wage_valid):
            reasons.append(f"Excluded {len(wage_all) - len(wage_valid)} unverified or unresolved record(s).")
        components.append(_component("wage_consistency", "Wage consistency", wage_score, len(wage_valid), reasons, len(wage_all) - len(wage_valid)))
    else:
        components.append(_component(
            "wage_consistency", "Wage consistency", None, 0,
            ["No verified, non-unresolved wage outcome is available; this component is not scored."], len(wage_all),
        ))

    if outcomes_valid:
        completion_score = 100 * sum(1 for row in outcomes_valid if row.completed) / len(outcomes_valid)
        reasons = [f"{sum(1 for row in outcomes_valid if row.completed)} of {len(outcomes_valid)} verified, non-unresolved job outcome(s) were completed."]
        if len(outcomes_all) > len(outcomes_valid):
            reasons.append(f"Excluded {len(outcomes_all) - len(outcomes_valid)} unverified or unresolved outcome(s).")
        components.append(_component("previous_job_completion", "Previous job completion", completion_score, len(outcomes_valid), reasons, len(outcomes_all) - len(outcomes_valid)))
    else:
        components.append(_component(
            "previous_job_completion", "Previous job completion", None, 0,
            ["No verified, non-unresolved job outcome is available; this component is not scored."], len(outcomes_all),
        ))

    if feedback_valid:
        feedback_score = 20 * sum(row.rating for row in feedback_valid) / len(feedback_valid)
        reasons = [f"Mean rating from {len(feedback_valid)} verified, non-unresolved worker feedback record(s), scaled from 1–5 to 0–100."]
        if len(feedback_all) > len(feedback_valid):
            reasons.append(f"Excluded {len(feedback_all) - len(feedback_valid)} unverified or unresolved feedback record(s).")
        components.append(_component("worker_feedback", "Worker feedback", feedback_score, len(feedback_valid), reasons, len(feedback_all) - len(feedback_valid)))
    else:
        components.append(_component(
            "worker_feedback", "Worker feedback", None, 0,
            ["No verified, non-unresolved worker feedback is available; this component is not scored."], len(feedback_all),
        ))

    if jobs:
        field_checks = (
            ("occupation", lambda job: job.occupation),
            ("wage", lambda job: job.wage_amount),
            ("wage period", lambda job: job.wage_period),
            ("working hours", lambda job: job.working_hours),
            ("location", lambda job: job.location),
            ("payment terms", lambda job: job.payment_terms),
            ("start date", lambda job: job.start_date),
        )
        filled = 0
        for job in jobs:
            for _, getter in field_checks:
                value = getter(job)
                if value is not None and str(value).strip() and str(value).strip().casefold() != "unspecified":
                    filled += 1
        total = len(jobs) * len(field_checks)
        information_score = 100 * filled / total
        reason = f"{filled} of {total} required listing details are present across {len(jobs)} job listing(s). Optional location coordinates are not required."
        components.append(_component("job_information_completeness", "Job information completeness", information_score, len(jobs), [reason]))
    else:
        components.append(_component(
            "job_information_completeness", "Job information completeness", None, 0,
            ["No job listings are available to assess; this component is not scored."],
        ))

    available = [component for component in components if component.available]
    coverage = sum(component.weight_pct for component in available)
    evidence_count = sum(component.evidence_count for component in available)
    enough_evidence = coverage >= MINIMUM_EVIDENCE_COVERAGE and len(available) >= 2
    score = None
    if enough_evidence:
        score = round(sum(component.score * component.weight_pct for component in available) / coverage, 1)

    if not enough_evidence:
        confidence_level = "insufficient"
        reasons = [
            f"Only {coverage}% of weighted components have usable evidence; at least {MINIMUM_EVIDENCE_COVERAGE}% across two components is required to publish a score.",
            "Missing components are excluded rather than treated as zero.",
        ]
    else:
        reasons = [
            f"Score is the weighted average of available components, normalized over {coverage}% evidence coverage; missing components are excluded.",
        ]
        if coverage >= 90 and evidence_count >= 20:
            confidence_level = "high"
        elif coverage >= 70 and evidence_count >= 5:
            confidence_level = "medium"
        else:
            confidence_level = "low"

    return JobTrustScore(
        contractor_id=contractor_id,
        status="scored" if enough_evidence else "insufficient_data",
        score=score,
        confidence=Confidence(
            level=confidence_level,
            data_coverage_pct=float(coverage),
            evidence_count=evidence_count,
            basis="Coverage is the sum of fixed weights with usable data. Confidence level also considers the count of verified, non-unresolved records and job listings.",
        ),
        components=components,
        reasons=reasons,
        policy="Weights: verification 20%, wage consistency 25%, previous job completion 20%, worker feedback 20%, job information completeness 15%. Unverified records and unresolved disputes do not contribute. This is an informational evidence summary, not a guarantee or finding of fraud.",
    )


@score_router.get("/{contractor_id}/jobtrust-score", response_model=JobTrustScore)
def get_jobtrust_score(contractor_id: uuid.UUID, user: AuthenticatedUser, db: Annotated[Session, Depends(get_db)]) -> JobTrustScore:
    return calculate_jobtrust_score(db, contractor_id)


@admin_router.get("/contractors", response_model=list[ContractorDirectoryItem])
def admin_list_contractors(user: AdminUser, db: Annotated[Session, Depends(get_db)]) -> list[ContractorDirectoryItem]:
    rows = db.execute(
        select(Contractor, User)
        .join(User, User.id == Contractor.user_id)
        .order_by(Contractor.verification_status, User.full_name)
    ).all()
    return [
        ContractorDirectoryItem(
            id=contractor.user_id,
            full_name=profile.full_name,
            email=profile.email,
            business_name=contractor.business_name,
            city=contractor.city,
            state=contractor.state,
            verification_status=contractor.verification_status,
            verification_updated_at=contractor.verification_updated_at,
        )
        for contractor, profile in rows
    ]


@admin_router.put("/contractors/{contractor_id}/verification")
def update_verification(
    contractor_id: uuid.UUID,
    payload: VerificationUpdate,
    user: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    contractor = db.get(Contractor, contractor_id)
    if contractor is None:
        raise HTTPException(status_code=404, detail="Contractor not found.")
    contractor.verification_status = payload.verification_status
    contractor.verification_updated_at = datetime.now(UTC)
    contractor.verification_updated_by = user.id
    db.commit()
    return {"contractor_id": contractor_id, "verification_status": contractor.verification_status}


def _accepted_application(db: Session, contractor_id: uuid.UUID, application_id: uuid.UUID) -> JobApplication:
    application = db.scalar(
        select(JobApplication)
        .join(Job, Job.id == JobApplication.job_id)
        .where(
            JobApplication.id == application_id,
            JobApplication.status == "accepted",
            Job.contractor_id == contractor_id,
        )
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Accepted application for this contractor was not found.")
    return application


@admin_router.post("/contractors/{contractor_id}/wage-evidence", status_code=status.HTTP_201_CREATED)
def add_wage_evidence(
    contractor_id: uuid.UUID,
    payload: WageEvidenceCreate,
    user: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    application = _accepted_application(db, contractor_id, payload.application_id)
    evidence = WageEvidence(
        application_id=application.id,
        contractor_id=contractor_id,
        agreed_wage=payload.agreed_wage,
        paid_wage=payload.paid_wage,
        is_verified=True,
        dispute_status=payload.dispute_status,
        verified_by=user.id,
    )
    db.add(evidence)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Wage evidence already exists for this application.") from exc
    return {"id": evidence.id, "is_verified": evidence.is_verified, "dispute_status": evidence.dispute_status}


@admin_router.post("/contractors/{contractor_id}/job-outcomes", status_code=status.HTTP_201_CREATED)
def add_job_outcome(
    contractor_id: uuid.UUID,
    payload: JobOutcomeCreate,
    user: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    application = _accepted_application(db, contractor_id, payload.application_id)
    outcome = JobOutcomeEvidence(
        application_id=application.id,
        contractor_id=contractor_id,
        completed=payload.completed,
        is_verified=True,
        dispute_status=payload.dispute_status,
        verified_by=user.id,
    )
    db.add(outcome)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Job outcome evidence already exists for this application.") from exc
    return {"id": outcome.id, "is_verified": outcome.is_verified, "dispute_status": outcome.dispute_status}


@feedback_router.post("/jobs/{job_id}/feedback", response_model=FeedbackSubmitted, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    job_id: uuid.UUID,
    payload: FeedbackCreate,
    user: WorkerUser,
    db: Annotated[Session, Depends(get_db)],
) -> FeedbackSubmitted:
    application = db.scalar(
        select(JobApplication).where(
            JobApplication.job_id == job_id,
            JobApplication.worker_id == user.id,
            JobApplication.status == "accepted",
        )
    )
    if application is None:
        raise HTTPException(status_code=403, detail="Feedback is available only for an accepted job application.")
    job = db.get(Job, job_id)
    feedback = ContractorFeedback(
        application_id=application.id,
        contractor_id=job.contractor_id,
        worker_id=user.id,
        rating=payload.rating,
        feedback_text=payload.feedback_text,
        is_verified=False,
        dispute_status="none",
    )
    db.add(feedback)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Feedback was already submitted for this application.") from exc
    return FeedbackSubmitted(id=feedback.id, rating=feedback.rating, is_verified=False, message="Feedback received. It is excluded from JobTrust scores until verified.")


@admin_router.patch("/feedback/{feedback_id}/review")
def review_feedback(
    feedback_id: uuid.UUID,
    payload: FeedbackReview,
    user: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    feedback = db.get(ContractorFeedback, feedback_id)
    if feedback is None:
        raise HTTPException(status_code=404, detail="Feedback not found.")
    feedback.is_verified = payload.is_verified
    feedback.dispute_status = payload.dispute_status
    feedback.verified_by = user.id if payload.is_verified else None
    db.commit()
    return {"id": feedback.id, "is_verified": feedback.is_verified, "dispute_status": feedback.dispute_status}
