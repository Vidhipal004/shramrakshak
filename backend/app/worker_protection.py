import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.database import get_db
from app.models import (
    Job,
    JobApplication,
    Role,
    TravelConfirmation,
    User,
    WageAgreement,
    WageAgreementVersion,
    WorkRealityReport,
)

router = APIRouter(tags=["worker protection"])
WorkerUser = Annotated[User, Depends(require_roles(Role.WORKER))]
ContractorUser = Annotated[User, Depends(require_roles(Role.CONTRACTOR))]
ParticipantUser = Annotated[User, Depends(require_roles(Role.WORKER, Role.CONTRACTOR, Role.ADMIN))]


class AgreementTerms(BaseModel):
    accepted_wage: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(min_length=3, max_length=8)
    wage_period: str = Field(min_length=1, max_length=30)
    working_hours: str = Field(min_length=1, max_length=150)
    location: str = Field(min_length=1, max_length=300)
    payment_terms: str = Field(min_length=1, max_length=5000)
    start_date: date


class AgreementCreate(AgreementTerms):
    application_id: uuid.UUID


class AgreementVersionProposal(BaseModel):
    accepted_wage: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=8)
    wage_period: str | None = Field(default=None, min_length=1, max_length=30)
    working_hours: str | None = Field(default=None, min_length=1, max_length=150)
    location: str | None = Field(default=None, min_length=1, max_length=300)
    payment_terms: str | None = Field(default=None, min_length=1, max_length=5000)
    start_date: date | None = None

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("At least one agreement term change is required")
        return self


class AgreementVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agreement_id: uuid.UUID
    version_number: int
    accepted_wage: Decimal
    currency: str
    wage_period: str
    working_hours: str
    location: str
    payment_terms: str
    start_date: date
    proposed_by: uuid.UUID
    status: str
    proposed_at: datetime
    worker_accepted_at: datetime | None
    contractor_accepted_at: datetime | None


class AgreementOut(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    job_id: uuid.UUID
    worker_id: uuid.UUID
    contractor_id: uuid.UUID
    created_at: datetime
    current_accepted_version: int | None
    versions: list[AgreementVersionOut]


class TravelRequest(BaseModel):
    travel_date: date


class TravelConfirmationOut(BaseModel):
    id: uuid.UUID
    agreement_id: uuid.UUID
    agreement_version_id: uuid.UUID
    worker_id: uuid.UUID
    contractor_id: uuid.UUID
    travel_date: date
    status: str
    reconfirmed_terms: dict | None
    requested_at: datetime
    confirmed_at: datetime | None
    departure_recorded_at: datetime | None
    agreed_terms: AgreementVersionOut


class ReconfirmTerms(AgreementTerms):
    pass


class WorkRealityCreate(BaseModel):
    agreement_version_id: uuid.UUID
    work_date: date
    actual_wage: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    actual_hours: float | None = Field(default=None, ge=0, le=24)
    payment_status: Literal["paid", "partially_paid", "unpaid", "pending"]
    worker_notes: str | None = Field(default=None, max_length=5000)


class WorkRealityOut(BaseModel):
    id: uuid.UUID
    agreement_id: uuid.UUID
    agreement_version_id: uuid.UUID
    worker_id: uuid.UUID
    contractor_id: uuid.UUID
    work_date: date
    actual_wage: Decimal | None
    actual_hours: float | None
    payment_status: str
    worker_notes: str | None
    reported_at: datetime
    promised_terms: AgreementVersionOut


def _agreement(db: Session, agreement_id: uuid.UUID) -> WageAgreement:
    agreement = db.get(WageAgreement, agreement_id)
    if agreement is None:
        raise HTTPException(status_code=404, detail="Wage agreement not found.")
    return agreement


def _ensure_participant(agreement: WageAgreement, user: User) -> None:
    if user.role == Role.ADMIN.value:
        return
    if user.role == Role.WORKER.value and agreement.worker_id == user.id:
        return
    if user.role == Role.CONTRACTOR.value and agreement.contractor_id == user.id:
        return
    raise HTTPException(status_code=404, detail="Wage agreement not found.")


def _latest_version(db: Session, agreement_id: uuid.UUID) -> WageAgreementVersion | None:
    return db.scalar(
        select(WageAgreementVersion)
        .where(WageAgreementVersion.agreement_id == agreement_id)
        .order_by(WageAgreementVersion.version_number.desc())
    )


def _current_accepted_version(db: Session, agreement_id: uuid.UUID) -> WageAgreementVersion | None:
    return db.scalar(
        select(WageAgreementVersion)
        .where(WageAgreementVersion.agreement_id == agreement_id, WageAgreementVersion.status == "accepted")
        .order_by(WageAgreementVersion.version_number.desc())
    )


def _agreement_out(db: Session, agreement: WageAgreement) -> AgreementOut:
    versions = db.scalars(
        select(WageAgreementVersion)
        .where(WageAgreementVersion.agreement_id == agreement.id)
        .order_by(WageAgreementVersion.version_number)
    ).all()
    current = next((version.version_number for version in reversed(versions) if version.status == "accepted"), None)
    return AgreementOut(
        id=agreement.id,
        application_id=agreement.application_id,
        job_id=agreement.job_id,
        worker_id=agreement.worker_id,
        contractor_id=agreement.contractor_id,
        created_at=agreement.created_at,
        current_accepted_version=current,
        versions=[AgreementVersionOut.model_validate(version) for version in versions],
    )


def _travel_out(db: Session, travel: TravelConfirmation) -> TravelConfirmationOut:
    version = db.get(WageAgreementVersion, travel.agreement_version_id)
    return TravelConfirmationOut(
        id=travel.id,
        agreement_id=travel.agreement_id,
        agreement_version_id=travel.agreement_version_id,
        worker_id=travel.worker_id,
        contractor_id=travel.contractor_id,
        travel_date=travel.travel_date,
        status=travel.status,
        reconfirmed_terms=travel.reconfirmed_terms,
        requested_at=travel.requested_at,
        confirmed_at=travel.confirmed_at,
        departure_recorded_at=travel.departure_recorded_at,
        agreed_terms=AgreementVersionOut.model_validate(version),
    )


def _reality_out(db: Session, report: WorkRealityReport) -> WorkRealityOut:
    version = db.get(WageAgreementVersion, report.agreement_version_id)
    return WorkRealityOut(
        id=report.id,
        agreement_id=report.agreement_id,
        agreement_version_id=report.agreement_version_id,
        worker_id=report.worker_id,
        contractor_id=report.contractor_id,
        work_date=report.work_date,
        actual_wage=report.actual_wage,
        actual_hours=report.actual_hours,
        payment_status=report.payment_status,
        worker_notes=report.worker_notes,
        reported_at=report.reported_at,
        promised_terms=AgreementVersionOut.model_validate(version),
    )


@router.post("/agreements", response_model=AgreementOut, status_code=status.HTTP_201_CREATED)
def create_agreement(payload: AgreementCreate, user: ContractorUser, db: Annotated[Session, Depends(get_db)]) -> AgreementOut:
    application = db.get(JobApplication, payload.application_id)
    if application is None or application.status != "accepted":
        raise HTTPException(status_code=404, detail="Accepted job application not found.")
    job = db.get(Job, application.job_id)
    if job.contractor_id != user.id:
        raise HTTPException(status_code=404, detail="Accepted job application not found.")
    if db.scalar(select(WageAgreement.id).where(WageAgreement.application_id == application.id)):
        raise HTTPException(status_code=409, detail="A wage agreement already exists for this application.")

    agreement = WageAgreement(
        application_id=application.id,
        job_id=job.id,
        worker_id=application.worker_id,
        contractor_id=user.id,
    )
    db.add(agreement)
    db.flush()
    now = datetime.now(UTC)
    version = WageAgreementVersion(
        agreement_id=agreement.id,
        version_number=1,
        proposed_by=user.id,
        status="pending",
        contractor_accepted_at=now,
        **payload.model_dump(exclude={"application_id"}),
    )
    db.add(version)
    db.commit()
    db.refresh(agreement)
    return _agreement_out(db, agreement)


@router.get("/agreements/mine", response_model=list[AgreementOut])
def my_agreements(user: ParticipantUser, db: Annotated[Session, Depends(get_db)]) -> list[AgreementOut]:
    if user.role == Role.ADMIN.value:
        agreements = db.scalars(select(WageAgreement).order_by(WageAgreement.created_at.desc())).all()
    elif user.role == Role.WORKER.value:
        agreements = db.scalars(select(WageAgreement).where(WageAgreement.worker_id == user.id).order_by(WageAgreement.created_at.desc())).all()
    else:
        agreements = db.scalars(select(WageAgreement).where(WageAgreement.contractor_id == user.id).order_by(WageAgreement.created_at.desc())).all()
    return [_agreement_out(db, agreement) for agreement in agreements]


@router.get("/agreements/{agreement_id}", response_model=AgreementOut)
def get_agreement(agreement_id: uuid.UUID, user: ParticipantUser, db: Annotated[Session, Depends(get_db)]) -> AgreementOut:
    agreement = _agreement(db, agreement_id)
    _ensure_participant(agreement, user)
    return _agreement_out(db, agreement)


@router.post("/agreements/{agreement_id}/versions", response_model=AgreementVersionOut, status_code=status.HTTP_201_CREATED)
def propose_agreement_version(
    agreement_id: uuid.UUID,
    payload: AgreementVersionProposal,
    user: ParticipantUser,
    db: Annotated[Session, Depends(get_db)],
) -> AgreementVersionOut:
    agreement = _agreement(db, agreement_id)
    _ensure_participant(agreement, user)
    if user.role == Role.ADMIN.value:
        raise HTTPException(status_code=403, detail="Admins cannot propose agreement terms.")
    latest = _latest_version(db, agreement.id)
    if latest is None or latest.status == "pending":
        raise HTTPException(status_code=409, detail="Resolve the pending agreement version before proposing another.")
    base = _current_accepted_version(db, agreement.id)
    if base is None and latest.status == "rejected":
        base = latest
    if base is None:
        raise HTTPException(status_code=409, detail="An accepted agreement version, or rejected version to revise, is required.")

    values = {
        field: getattr(base, field)
        for field in ("accepted_wage", "currency", "wage_period", "working_hours", "location", "payment_terms", "start_date")
    }
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        if value is None:
            raise HTTPException(status_code=422, detail="Agreement terms cannot be cleared; provide a replacement value.")
        values[field] = value
    now = datetime.now(UTC)
    version = WageAgreementVersion(
        agreement_id=agreement.id,
        version_number=latest.version_number + 1,
        proposed_by=user.id,
        status="pending",
        worker_accepted_at=now if user.role == Role.WORKER.value else None,
        contractor_accepted_at=now if user.role == Role.CONTRACTOR.value else None,
        **values,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return AgreementVersionOut.model_validate(version)


@router.post("/agreements/{agreement_id}/versions/{version_id}/accept", response_model=AgreementVersionOut)
def accept_agreement_version(
    agreement_id: uuid.UUID,
    version_id: uuid.UUID,
    user: ParticipantUser,
    db: Annotated[Session, Depends(get_db)],
) -> AgreementVersionOut:
    agreement = _agreement(db, agreement_id)
    _ensure_participant(agreement, user)
    version = db.scalar(
        select(WageAgreementVersion).where(
            WageAgreementVersion.id == version_id,
            WageAgreementVersion.agreement_id == agreement.id,
        )
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Agreement version not found.")
    if version.status != "pending":
        raise HTTPException(status_code=409, detail="Only pending agreement versions can be accepted.")
    if version.proposed_by == user.id:
        raise HTTPException(status_code=409, detail="The other party must accept the proposed version.")
    now = datetime.now(UTC)
    if user.role == Role.WORKER.value:
        version.worker_accepted_at = now
    elif user.role == Role.CONTRACTOR.value:
        version.contractor_accepted_at = now
    else:
        raise HTTPException(status_code=403, detail="Admins cannot accept agreement terms.")
    version.status = "accepted"
    db.commit()
    db.refresh(version)
    return AgreementVersionOut.model_validate(version)


@router.post("/agreements/{agreement_id}/versions/{version_id}/reject", response_model=AgreementVersionOut)
def reject_agreement_version(
    agreement_id: uuid.UUID,
    version_id: uuid.UUID,
    user: ParticipantUser,
    db: Annotated[Session, Depends(get_db)],
) -> AgreementVersionOut:
    agreement = _agreement(db, agreement_id)
    _ensure_participant(agreement, user)
    if user.role == Role.ADMIN.value:
        raise HTTPException(status_code=403, detail="Admins cannot reject agreement terms.")
    version = db.scalar(select(WageAgreementVersion).where(WageAgreementVersion.id == version_id, WageAgreementVersion.agreement_id == agreement.id))
    if version is None:
        raise HTTPException(status_code=404, detail="Agreement version not found.")
    if version.status != "pending" or version.proposed_by == user.id:
        raise HTTPException(status_code=409, detail="Only the other party may reject a pending version.")
    version.status = "rejected"
    db.commit()
    db.refresh(version)
    return AgreementVersionOut.model_validate(version)


@router.post("/agreements/{agreement_id}/travel-confirmations", response_model=TravelConfirmationOut, status_code=status.HTTP_201_CREATED)
def request_travel_confirmation(
    agreement_id: uuid.UUID,
    payload: TravelRequest,
    user: WorkerUser,
    db: Annotated[Session, Depends(get_db)],
) -> TravelConfirmationOut:
    agreement = _agreement(db, agreement_id)
    _ensure_participant(agreement, user)
    latest = _latest_version(db, agreement.id)
    current = _current_accepted_version(db, agreement.id)
    if current is None or latest is None or latest.status == "pending":
        raise HTTPException(status_code=409, detail="A latest accepted agreement version is required before travel confirmation.")
    confirmation = TravelConfirmation(
        agreement_id=agreement.id,
        agreement_version_id=current.id,
        worker_id=user.id,
        contractor_id=agreement.contractor_id,
        travel_date=payload.travel_date,
        status="requested",
    )
    db.add(confirmation)
    db.commit()
    db.refresh(confirmation)
    return _travel_out(db, confirmation)


@router.get("/agreements/{agreement_id}/travel-confirmations", response_model=list[TravelConfirmationOut])
def list_travel_confirmations(
    agreement_id: uuid.UUID,
    user: ParticipantUser,
    db: Annotated[Session, Depends(get_db)],
) -> list[TravelConfirmationOut]:
    agreement = _agreement(db, agreement_id)
    _ensure_participant(agreement, user)
    confirmations = db.scalars(
        select(TravelConfirmation).where(TravelConfirmation.agreement_id == agreement.id).order_by(TravelConfirmation.requested_at.desc())
    ).all()
    return [_travel_out(db, confirmation) for confirmation in confirmations]


@router.post("/travel-confirmations/{confirmation_id}/confirm", response_model=TravelConfirmationOut)
def contractor_reconfirm_before_travel(
    confirmation_id: uuid.UUID,
    payload: ReconfirmTerms,
    user: ContractorUser,
    db: Annotated[Session, Depends(get_db)],
) -> TravelConfirmationOut:
    confirmation = db.get(TravelConfirmation, confirmation_id)
    if confirmation is None or confirmation.contractor_id != user.id:
        raise HTTPException(status_code=404, detail="Travel confirmation not found.")
    if confirmation.status != "requested":
        raise HTTPException(status_code=409, detail="Only a pending travel confirmation can be reconfirmed.")
    version = db.get(WageAgreementVersion, confirmation.agreement_version_id)
    latest = _latest_version(db, confirmation.agreement_id)
    current = _current_accepted_version(db, confirmation.agreement_id)
    submitted_terms = payload.model_dump(mode="json")
    accepted_terms = {
        "accepted_wage": version.accepted_wage,
        "currency": version.currency,
        "wage_period": version.wage_period,
        "working_hours": version.working_hours,
        "location": version.location,
        "payment_terms": version.payment_terms,
        "start_date": version.start_date,
    }
    same_terms = all(
        Decimal(str(submitted_terms[field])) == accepted_terms[field] if field == "accepted_wage"
        else submitted_terms[field] == (accepted_terms[field].isoformat() if field == "start_date" else accepted_terms[field])
        for field in accepted_terms
    )
    if current is None or latest is None or latest.status == "pending" or current.id != version.id:
        confirmation.status = "terms_changed"
        confirmation.reconfirmed_terms = submitted_terms
    elif not same_terms:
        confirmation.status = "terms_changed"
        confirmation.reconfirmed_terms = submitted_terms
    else:
        confirmation.status = "confirmed"
        confirmation.confirmed_at = datetime.now(UTC)
        confirmation.reconfirmed_terms = submitted_terms
    db.commit()
    db.refresh(confirmation)
    return _travel_out(db, confirmation)


@router.post("/travel-confirmations/{confirmation_id}/depart", response_model=TravelConfirmationOut)
def record_worker_departure(
    confirmation_id: uuid.UUID,
    user: WorkerUser,
    db: Annotated[Session, Depends(get_db)],
) -> TravelConfirmationOut:
    confirmation = db.get(TravelConfirmation, confirmation_id)
    if confirmation is None or confirmation.worker_id != user.id:
        raise HTTPException(status_code=404, detail="Travel confirmation not found.")
    if confirmation.status != "confirmed":
        raise HTTPException(status_code=409, detail="Contractor reconfirmation is required before departure.")
    current = _current_accepted_version(db, confirmation.agreement_id)
    latest = _latest_version(db, confirmation.agreement_id)
    if current is None or latest is None or latest.status == "pending" or current.id != confirmation.agreement_version_id:
        confirmation.status = "terms_changed"
        db.commit()
        raise HTTPException(status_code=409, detail="Agreement terms changed; request a fresh contractor reconfirmation before departure.")
    if confirmation.departure_recorded_at is not None:
        raise HTTPException(status_code=409, detail="Departure has already been recorded.")
    confirmation.departure_recorded_at = datetime.now(UTC)
    db.commit()
    db.refresh(confirmation)
    return _travel_out(db, confirmation)


@router.post("/agreements/{agreement_id}/reality", response_model=WorkRealityOut, status_code=status.HTTP_201_CREATED)
def record_work_reality(
    agreement_id: uuid.UUID,
    payload: WorkRealityCreate,
    user: WorkerUser,
    db: Annotated[Session, Depends(get_db)],
) -> WorkRealityOut:
    agreement = _agreement(db, agreement_id)
    _ensure_participant(agreement, user)
    version = db.scalar(
        select(WageAgreementVersion).where(
            WageAgreementVersion.id == payload.agreement_version_id,
            WageAgreementVersion.agreement_id == agreement.id,
            WageAgreementVersion.status == "accepted",
        )
    )
    if version is None:
        raise HTTPException(status_code=409, detail="Reality report must reference an accepted agreement version.")
    report = WorkRealityReport(
        agreement_id=agreement.id,
        agreement_version_id=version.id,
        worker_id=user.id,
        contractor_id=agreement.contractor_id,
        **payload.model_dump(exclude={"agreement_version_id"}),
    )
    db.add(report)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A reality report already exists for this agreement version and work date.") from exc
    db.refresh(report)
    return _reality_out(db, report)


@router.get("/agreements/{agreement_id}/reality", response_model=list[WorkRealityOut])
def list_work_reality(
    agreement_id: uuid.UUID,
    user: ParticipantUser,
    db: Annotated[Session, Depends(get_db)],
) -> list[WorkRealityOut]:
    agreement = _agreement(db, agreement_id)
    _ensure_participant(agreement, user)
    reports = db.scalars(
        select(WorkRealityReport).where(WorkRealityReport.agreement_id == agreement.id).order_by(WorkRealityReport.work_date.desc())
    ).all()
    return [_reality_out(db, report) for report in reports]
