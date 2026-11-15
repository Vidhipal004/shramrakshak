import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.database import get_db
from app.models import (
    ComplaintEvidence,
    ComplaintResponse,
    ComplaintReview,
    ProtectionComplaint,
    Role,
    User,
    WageAgreement,
    WorkRealityReport,
)

router = APIRouter(prefix="/complaints", tags=["complaints and disputes"])
admin_router = APIRouter(prefix="/admin/complaints", tags=["admin dispute review"])
WorkerUser = Annotated[User, Depends(require_roles(Role.WORKER))]
ContractorUser = Annotated[User, Depends(require_roles(Role.CONTRACTOR))]
AdminUser = Annotated[User, Depends(require_roles(Role.ADMIN))]
ParticipantUser = Annotated[User, Depends(require_roles(Role.WORKER, Role.CONTRACTOR, Role.ADMIN))]

MAX_EVIDENCE_BYTES = 8 * 1024 * 1024
MAX_EVIDENCE_FILES = 5
ALLOWED_EVIDENCE_TYPES = {
    "image/jpeg", "image/png", "image/webp", "application/pdf", "text/plain",
    "audio/mpeg", "audio/mp4", "audio/wav",
}


class ComplaintCreate(BaseModel):
    agreement_id: uuid.UUID | None = None
    reality_report_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    category: Literal["wage", "hours", "job_mismatch", "payment", "safety", "other"]
    description: str = Field(min_length=10, max_length=10000)

    @model_validator(mode="after")
    def require_related_work_record(self):
        if self.agreement_id is None and self.reality_report_id is None:
            raise ValueError("An agreement or work reality report must be linked to the complaint")
        return self


class ContractorResponseCreate(BaseModel):
    message: str = Field(min_length=10, max_length=10000)


class ComplaintReviewRequest(BaseModel):
    status: Literal["under_review", "resolved", "dismissed"]
    outcome: Literal["worker_upheld", "contractor_upheld", "inconclusive"] | None = None
    notes: str = Field(min_length=5, max_length=10000)

    @model_validator(mode="after")
    def final_status_needs_outcome(self):
        if self.status in {"resolved", "dismissed"} and self.outcome is None:
            raise ValueError("A resolution outcome is required for a final decision")
        return self


class EvidenceMetadata(BaseModel):
    id: uuid.UUID
    uploaded_by: uuid.UUID
    file_name: str
    content_type: str
    sha256: str
    byte_size: int
    created_at: datetime


class ResponseOut(BaseModel):
    id: uuid.UUID
    author_id: uuid.UUID
    message: str
    created_at: datetime


class ReviewOut(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID
    status: str
    outcome: str | None
    notes: str
    created_at: datetime


class ComplaintOut(BaseModel):
    id: uuid.UUID
    worker_id: uuid.UUID
    contractor_id: uuid.UUID
    job_id: uuid.UUID | None
    agreement_id: uuid.UUID | None
    reality_report_id: uuid.UUID | None
    category: str
    description: str
    status: str
    resolution_outcome: str | None
    resolution_summary: str | None
    created_at: datetime
    updated_at: datetime
    responses: list[ResponseOut]
    evidence: list[EvidenceMetadata]
    reviews: list[ReviewOut]


def _complaint(db: Session, complaint_id: uuid.UUID) -> ProtectionComplaint:
    complaint = db.get(ProtectionComplaint, complaint_id)
    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found.")
    return complaint


def _can_view(complaint: ProtectionComplaint, user: User) -> bool:
    return user.role == Role.ADMIN.value or user.id in {complaint.worker_id, complaint.contractor_id}


def _require_participant(complaint: ProtectionComplaint, user: User) -> None:
    if not _can_view(complaint, user):
        raise HTTPException(status_code=404, detail="Complaint not found.")


def _complaint_out(db: Session, complaint: ProtectionComplaint) -> ComplaintOut:
    responses = db.scalars(
        select(ComplaintResponse).where(ComplaintResponse.complaint_id == complaint.id).order_by(ComplaintResponse.created_at)
    ).all()
    evidence = db.scalars(
        select(ComplaintEvidence).where(ComplaintEvidence.complaint_id == complaint.id).order_by(ComplaintEvidence.created_at)
    ).all()
    reviews = db.scalars(
        select(ComplaintReview).where(ComplaintReview.complaint_id == complaint.id).order_by(ComplaintReview.created_at)
    ).all()
    return ComplaintOut(
        id=complaint.id,
        worker_id=complaint.worker_id,
        contractor_id=complaint.contractor_id,
        job_id=complaint.job_id,
        agreement_id=complaint.agreement_id,
        reality_report_id=complaint.reality_report_id,
        category=complaint.category,
        description=complaint.description,
        status=complaint.status,
        resolution_outcome=complaint.resolution_outcome,
        resolution_summary=complaint.resolution_summary,
        created_at=complaint.created_at,
        updated_at=complaint.updated_at,
        responses=[ResponseOut.model_validate(response, from_attributes=True) for response in responses],
        evidence=[EvidenceMetadata.model_validate(item, from_attributes=True) for item in evidence],
        reviews=[ReviewOut.model_validate(item, from_attributes=True) for item in reviews],
    )


@router.post("", response_model=ComplaintOut, status_code=status.HTTP_201_CREATED)
def submit_complaint(
    payload: ComplaintCreate,
    user: WorkerUser,
    db: Annotated[Session, Depends(get_db)],
) -> ComplaintOut:
    agreement = None
    report = None
    if payload.agreement_id:
        agreement = db.get(WageAgreement, payload.agreement_id)
        if agreement is None or agreement.worker_id != user.id:
            raise HTTPException(status_code=404, detail="Related agreement not found.")
    if payload.reality_report_id:
        report = db.get(WorkRealityReport, payload.reality_report_id)
        if report is None or report.worker_id != user.id:
            raise HTTPException(status_code=404, detail="Related work report not found.")
        if agreement is not None and report.agreement_id != agreement.id:
            raise HTTPException(status_code=422, detail="The work report must belong to the linked agreement.")
        if agreement is None:
            agreement = db.get(WageAgreement, report.agreement_id)
    if agreement is None:
        raise HTTPException(status_code=404, detail="Related agreement not found.")
    job_id = agreement.job_id
    if payload.job_id and payload.job_id != job_id:
        raise HTTPException(status_code=422, detail="The job does not match the linked agreement.")

    complaint = ProtectionComplaint(
        worker_id=user.id,
        contractor_id=agreement.contractor_id,
        job_id=job_id,
        agreement_id=agreement.id,
        reality_report_id=report.id if report else None,
        category=payload.category,
        description=payload.description.strip(),
        status="submitted",
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)
    return _complaint_out(db, complaint)


@router.get("/mine", response_model=list[ComplaintOut])
def my_complaints(user: ParticipantUser, db: Annotated[Session, Depends(get_db)]) -> list[ComplaintOut]:
    if user.role == Role.ADMIN.value:
        complaints = db.scalars(select(ProtectionComplaint).order_by(ProtectionComplaint.created_at.desc())).all()
    elif user.role == Role.WORKER.value:
        complaints = db.scalars(select(ProtectionComplaint).where(ProtectionComplaint.worker_id == user.id).order_by(ProtectionComplaint.created_at.desc())).all()
    else:
        complaints = db.scalars(select(ProtectionComplaint).where(ProtectionComplaint.contractor_id == user.id).order_by(ProtectionComplaint.created_at.desc())).all()
    return [_complaint_out(db, complaint) for complaint in complaints]


@router.get("/{complaint_id}", response_model=ComplaintOut)
def get_complaint(complaint_id: uuid.UUID, user: ParticipantUser, db: Annotated[Session, Depends(get_db)]) -> ComplaintOut:
    complaint = _complaint(db, complaint_id)
    _require_participant(complaint, user)
    return _complaint_out(db, complaint)


@router.post("/{complaint_id}/responses", response_model=ResponseOut, status_code=status.HTTP_201_CREATED)
def contractor_respond(
    complaint_id: uuid.UUID,
    payload: ContractorResponseCreate,
    user: ContractorUser,
    db: Annotated[Session, Depends(get_db)],
) -> ResponseOut:
    complaint = _complaint(db, complaint_id)
    if complaint.contractor_id != user.id:
        raise HTTPException(status_code=404, detail="Complaint not found.")
    if complaint.status in {"resolved", "dismissed"}:
        raise HTTPException(status_code=409, detail="A final complaint cannot receive new responses.")
    response = ComplaintResponse(complaint_id=complaint.id, author_id=user.id, message=payload.message.strip())
    db.add(response)
    complaint.status = "contractor_responded"
    db.commit()
    db.refresh(response)
    return ResponseOut.model_validate(response, from_attributes=True)


@router.post("/{complaint_id}/evidence", response_model=list[EvidenceMetadata], status_code=status.HTTP_201_CREATED)
async def upload_complaint_evidence(
    complaint_id: uuid.UUID,
    user: ParticipantUser,
    db: Annotated[Session, Depends(get_db)],
    files: list[UploadFile] = File(...),
) -> list[EvidenceMetadata]:
    complaint = _complaint(db, complaint_id)
    _require_participant(complaint, user)
    if complaint.status in {"resolved", "dismissed"}:
        raise HTTPException(status_code=409, detail="Evidence cannot be added to a final complaint.")
    if not files:
        raise HTTPException(status_code=422, detail="At least one evidence file is required.")
    if len(files) > MAX_EVIDENCE_FILES:
        raise HTTPException(status_code=413, detail=f"Upload no more than {MAX_EVIDENCE_FILES} evidence files at once.")
    rows = []
    for upload in files:
        content_type = (upload.content_type or "").lower()
        if content_type not in ALLOWED_EVIDENCE_TYPES:
            raise HTTPException(status_code=415, detail="Evidence must be an image, PDF, plain text, or supported audio file.")
        content = await upload.read(MAX_EVIDENCE_BYTES + 1)
        if not content:
            raise HTTPException(status_code=422, detail="Evidence file is empty.")
        if len(content) > MAX_EVIDENCE_BYTES:
            raise HTTPException(status_code=413, detail="Each evidence file must be 8 MB or smaller.")
        file_name = Path(upload.filename or "evidence").name.replace("\r", "").replace("\n", "")[:255] or "evidence"
        rows.append(ComplaintEvidence(
            complaint_id=complaint.id,
            uploaded_by=user.id,
            file_name=file_name,
            content_type=content_type,
            sha256=hashlib.sha256(content).hexdigest(),
            byte_size=len(content),
            content=content,
        ))
    db.add_all(rows)
    db.commit()
    for row in rows:
        db.refresh(row)
    return [EvidenceMetadata.model_validate(row, from_attributes=True) for row in rows]


@router.get("/{complaint_id}/evidence", response_model=list[EvidenceMetadata])
def list_complaint_evidence(
    complaint_id: uuid.UUID,
    user: ParticipantUser,
    db: Annotated[Session, Depends(get_db)],
) -> list[EvidenceMetadata]:
    complaint = _complaint(db, complaint_id)
    _require_participant(complaint, user)
    items = db.scalars(select(ComplaintEvidence).where(ComplaintEvidence.complaint_id == complaint.id).order_by(ComplaintEvidence.created_at)).all()
    return [EvidenceMetadata.model_validate(item, from_attributes=True) for item in items]


@router.get("/{complaint_id}/evidence/{evidence_id}")
def download_complaint_evidence(
    complaint_id: uuid.UUID,
    evidence_id: uuid.UUID,
    user: ParticipantUser,
    db: Annotated[Session, Depends(get_db)],
) -> StreamingResponse:
    complaint = _complaint(db, complaint_id)
    _require_participant(complaint, user)
    evidence = db.scalar(select(ComplaintEvidence).where(ComplaintEvidence.id == evidence_id, ComplaintEvidence.complaint_id == complaint.id))
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence file not found.")
    encoded_name = quote(evidence.file_name, safe="")
    return StreamingResponse(
        iter([evidence.content]),
        media_type=evidence.content_type,
        headers={
            "Content-Disposition": f"attachment; filename=\"evidence\"; filename*=UTF-8''{encoded_name}",
            "X-Content-Type-Options": "nosniff",
        },
    )


@admin_router.get("", response_model=list[ComplaintOut])
def admin_list_complaints(
    user: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    complaint_status: Literal["submitted", "contractor_responded", "under_review", "resolved", "dismissed"] | None = Query(default=None, alias="status"),
) -> list[ComplaintOut]:
    query = select(ProtectionComplaint)
    if complaint_status:
        query = query.where(ProtectionComplaint.status == complaint_status)
    complaints = db.scalars(query.order_by(ProtectionComplaint.created_at.desc())).all()
    return [_complaint_out(db, complaint) for complaint in complaints]


@admin_router.patch("/{complaint_id}/review", response_model=ComplaintOut)
def admin_review_complaint(
    complaint_id: uuid.UUID,
    payload: ComplaintReviewRequest,
    user: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> ComplaintOut:
    complaint = _complaint(db, complaint_id)
    if complaint.status in {"resolved", "dismissed"}:
        raise HTTPException(status_code=409, detail="This complaint already has a final decision.")
    complaint.status = payload.status
    complaint.resolution_outcome = payload.outcome if payload.status in {"resolved", "dismissed"} else None
    complaint.resolution_summary = payload.notes.strip() if payload.status in {"resolved", "dismissed"} else None
    db.add(ComplaintReview(
        complaint_id=complaint.id,
        admin_id=user.id,
        status=payload.status,
        outcome=payload.outcome,
        notes=payload.notes.strip(),
    ))
    db.commit()
    db.refresh(complaint)
    return _complaint_out(db, complaint)
