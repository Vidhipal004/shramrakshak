import math
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.database import get_db
from app.models import Contractor, Job, JobApplication, Role, User, Worker

jobs_router = APIRouter(prefix="/jobs", tags=["jobs"])
applications_router = APIRouter(prefix="/applications", tags=["applications"])
WorkerUser = Annotated[User, Depends(require_roles(Role.WORKER))]
ContractorUser = Annotated[User, Depends(require_roles(Role.CONTRACTOR))]
AuthenticatedUser = Annotated[User, Depends(require_roles(Role.WORKER, Role.CONTRACTOR, Role.ADMIN))]


class JobCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    occupation: str = Field(min_length=2, max_length=120)
    skill: str | None = Field(default=None, max_length=120)
    description: str | None = None
    location: str = Field(min_length=2, max_length=300)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    wage_amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    wage_period: Literal["hour", "day", "week", "month", "fixed"] = "day"
    working_hours: str = Field(min_length=1, max_length=100)
    payment_terms: str = Field(min_length=1, max_length=500)
    start_date: date

    @model_validator(mode="after")
    def coordinates_are_a_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class JobPatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    occupation: str | None = Field(default=None, min_length=2, max_length=120)
    skill: str | None = Field(default=None, max_length=120)
    description: str | None = None
    location: str | None = Field(default=None, min_length=2, max_length=300)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    wage_amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    wage_period: Literal["hour", "day", "week", "month", "fixed"] | None = None
    working_hours: str | None = Field(default=None, min_length=1, max_length=100)
    payment_terms: str | None = Field(default=None, min_length=1, max_length=500)
    start_date: date | None = None
    status: Literal["open", "filled", "cancelled"] | None = None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contractor_id: uuid.UUID
    title: str
    occupation: str
    skill: str | None
    description: str | None
    location: str
    latitude: float | None
    longitude: float | None
    wage_amount: Decimal
    wage_period: str
    working_hours: str
    payment_terms: str
    start_date: date
    status: str
    created_at: datetime
    distance_km: float | None = None


class ApplicationCreate(BaseModel):
    message: str | None = Field(default=None, max_length=2000)


class ApplicationStatusUpdate(BaseModel):
    status: Literal["accepted", "rejected"]


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    worker_id: uuid.UUID
    message: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    job: JobOut


class ContractorApplicationOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    worker_id: uuid.UUID
    worker_name: str
    worker_city: str | None
    message: str | None
    status: str
    created_at: datetime


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance using the Haversine formula."""
    earth_radius_km = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    value = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    value = min(1.0, max(0.0, value))
    return earth_radius_km * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def _owned_job(db: Session, job_id: uuid.UUID, contractor_id: uuid.UUID) -> Job:
    job = db.scalar(select(Job).where(Job.id == job_id, Job.contractor_id == contractor_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Job listing not found.")
    return job


@jobs_router.get("/mine", response_model=list[JobOut], name="contractor_jobs")
def contractor_jobs(user: ContractorUser, db: Annotated[Session, Depends(get_db)]) -> list[JobOut]:
    jobs = db.scalars(select(Job).where(Job.contractor_id == user.id).order_by(Job.created_at.desc())).all()
    return [JobOut.model_validate(job) for job in jobs]


@jobs_router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, user: ContractorUser, db: Annotated[Session, Depends(get_db)]) -> JobOut:
    if db.get(Contractor, user.id) is None:
        raise HTTPException(status_code=403, detail="Contractor profile is missing.")
    job = Job(contractor_id=user.id, **payload.model_dump())
    db.add(job)
    db.commit()
    db.refresh(job)
    return JobOut.model_validate(job)


@jobs_router.get("", response_model=list[JobOut])
def browse_jobs(
    user: WorkerUser,
    db: Annotated[Session, Depends(get_db)],
    skill: str | None = Query(default=None, min_length=1, max_length=120),
    location: str | None = Query(default=None, min_length=1, max_length=300),
    min_wage: Decimal | None = Query(default=None, ge=0),
    max_wage: Decimal | None = Query(default=None, ge=0),
    start_date_from: date | None = None,
    start_date_to: date | None = None,
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    radius_km: float = Query(default=5.0, gt=0, le=100),
) -> list[JobOut]:
    if min_wage is not None and max_wage is not None and min_wage > max_wage:
        raise HTTPException(status_code=422, detail="min_wage cannot exceed max_wage.")
    if start_date_from and start_date_to and start_date_from > start_date_to:
        raise HTTPException(status_code=422, detail="start_date_from cannot be after start_date_to.")
    if (latitude is None) != (longitude is None):
        raise HTTPException(status_code=422, detail="latitude and longitude must be provided together.")

    center_lat, center_lon = latitude, longitude
    if center_lat is None:
        worker = db.get(Worker, user.id)
        if worker:
            center_lat, center_lon = worker.latitude, worker.longitude

    query = select(Job).where(Job.status == "open")
    if skill:
        match = f"%{skill.strip()}%"
        query = query.where(or_(Job.skill.ilike(match), Job.occupation.ilike(match), Job.title.ilike(match)))
    if location:
        query = query.where(Job.location.ilike(f"%{location.strip()}%"))
    if min_wage is not None:
        query = query.where(Job.wage_amount >= min_wage)
    if max_wage is not None:
        query = query.where(Job.wage_amount <= max_wage)
    if start_date_from:
        query = query.where(Job.start_date >= start_date_from)
    if start_date_to:
        query = query.where(Job.start_date <= start_date_to)
    candidates = db.scalars(query.order_by(Job.start_date, Job.created_at.desc())).all()

    results: list[JobOut] = []
    for job in candidates:
        distance = None
        if center_lat is not None and center_lon is not None and job.latitude is not None and job.longitude is not None:
            distance = _distance_km(center_lat, center_lon, job.latitude, job.longitude)
            if distance > radius_km:
                continue
        results.append(JobOut.model_validate(job).model_copy(update={"distance_km": round(distance, 2) if distance is not None else None}))
    return results


@jobs_router.get("/{job_id}/applications", response_model=list[ContractorApplicationOut])
def job_applications(job_id: uuid.UUID, user: ContractorUser, db: Annotated[Session, Depends(get_db)]) -> list[ContractorApplicationOut]:
    _owned_job(db, job_id, user.id)
    rows = db.execute(
        select(JobApplication, User, Worker)
        .join(User, User.id == JobApplication.worker_id)
        .join(Worker, Worker.user_id == JobApplication.worker_id)
        .where(JobApplication.job_id == job_id)
        .order_by(JobApplication.created_at.desc())
    ).all()
    return [
        ContractorApplicationOut(
            id=application.id,
            job_id=application.job_id,
            worker_id=worker_user.id,
            worker_name=worker_user.full_name,
            worker_city=worker.city,
            message=application.message,
            status=application.status,
            created_at=application.created_at,
        )
        for application, worker_user, worker in rows
    ]


@jobs_router.patch("/{job_id}/applications/{application_id}", response_model=ContractorApplicationOut)
def review_application(
    job_id: uuid.UUID,
    application_id: uuid.UUID,
    payload: ApplicationStatusUpdate,
    user: ContractorUser,
    db: Annotated[Session, Depends(get_db)],
) -> ContractorApplicationOut:
    _owned_job(db, job_id, user.id)
    application = db.scalar(select(JobApplication).where(JobApplication.id == application_id, JobApplication.job_id == job_id))
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    if application.status != "pending":
        raise HTTPException(status_code=409, detail="Only pending applications can be reviewed.")
    application.status = payload.status
    db.commit()
    db.refresh(application)
    worker_user = db.get(User, application.worker_id)
    worker = db.get(Worker, application.worker_id)
    return ContractorApplicationOut(
        id=application.id,
        job_id=application.job_id,
        worker_id=application.worker_id,
        worker_name=worker_user.full_name,
        worker_city=worker.city if worker else None,
        message=application.message,
        status=application.status,
        created_at=application.created_at,
    )


@jobs_router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: uuid.UUID, user: AuthenticatedUser, db: Annotated[Session, Depends(get_db)]) -> JobOut:
    job = db.get(Job, job_id)
    if job is None or (job.status != "open" and job.contractor_id != user.id and user.role != Role.ADMIN.value):
        raise HTTPException(status_code=404, detail="Job listing not found.")
    return JobOut.model_validate(job)


@jobs_router.patch("/{job_id}", response_model=JobOut)
def update_job(job_id: uuid.UUID, payload: JobPatch, user: ContractorUser, db: Annotated[Session, Depends(get_db)]) -> JobOut:
    job = _owned_job(db, job_id, user.id)
    updates = payload.model_dump(exclude_unset=True)
    required_fields = {"title", "occupation", "location", "wage_amount", "wage_period", "working_hours", "payment_terms", "start_date", "status"}
    if any(field in updates and updates[field] is None for field in required_fields):
        raise HTTPException(status_code=422, detail="Required job fields cannot be cleared.")
    latitude = updates.get("latitude", job.latitude)
    longitude = updates.get("longitude", job.longitude)
    if (latitude is None) != (longitude is None):
        raise HTTPException(status_code=422, detail="latitude and longitude must be provided together.")
    for field, value in updates.items():
        setattr(job, field, value)
    db.commit()
    db.refresh(job)
    return JobOut.model_validate(job)


@jobs_router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_job(job_id: uuid.UUID, user: ContractorUser, db: Annotated[Session, Depends(get_db)]) -> Response:
    job = _owned_job(db, job_id, user.id)
    job.status = "cancelled"
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@jobs_router.post("/{job_id}/applications", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
def apply_to_job(
    job_id: uuid.UUID,
    payload: ApplicationCreate,
    user: WorkerUser,
    db: Annotated[Session, Depends(get_db)],
) -> ApplicationOut:
    job = db.get(Job, job_id)
    if job is None or job.status != "open":
        raise HTTPException(status_code=404, detail="Open job listing not found.")
    application = JobApplication(job_id=job_id, worker_id=user.id, message=payload.message)
    db.add(application)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="You have already applied for this job.") from exc
    db.refresh(application)
    return ApplicationOut.model_validate(application)


@applications_router.get("/me", response_model=list[ApplicationOut])
def my_applications(user: WorkerUser, db: Annotated[Session, Depends(get_db)]) -> list[ApplicationOut]:
    applications = db.scalars(
        select(JobApplication).where(JobApplication.worker_id == user.id).order_by(JobApplication.created_at.desc())
    ).all()
    return [ApplicationOut.model_validate(application) for application in applications]


@applications_router.post("/{application_id}/withdraw", response_model=ApplicationOut)
def withdraw_application(application_id: uuid.UUID, user: WorkerUser, db: Annotated[Session, Depends(get_db)]) -> ApplicationOut:
    application = db.scalar(select(JobApplication).where(JobApplication.id == application_id, JobApplication.worker_id == user.id))
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    if application.status != "pending":
        raise HTTPException(status_code=409, detail="Only pending applications can be withdrawn.")
    application.status = "withdrawn"
    db.commit()
    db.refresh(application)
    return ApplicationOut.model_validate(application)
