import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.database import get_db
from app.gemini_scanner import ALLOWED_IMAGE_TYPES, MAX_IMAGE_BYTES, MAX_INPUT_TEXT_CHARS, ExtractedOffer, extract_offer
from app.models import OfferRecord, Role, User

router = APIRouter(prefix="/offer-scanner", tags=["AI job offer scanner"])
WorkerUser = Annotated[User, Depends(require_roles(Role.WORKER))]


class OfferSaveRequest(BaseModel):
    contractor_name: str | None = Field(default=None, max_length=200)
    occupation: str | None = Field(default=None, max_length=120)
    wage_amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, max_length=8)
    wage_period: str | None = Field(default=None, max_length=30)
    working_hours: str | None = Field(default=None, max_length=150)
    location: str | None = Field(default=None, max_length=300)
    payment_terms: str | None = Field(default=None, max_length=5000)
    start_date: date | None = None
    source_type: Literal["text", "image", "both"]
    worker_confirmed: Literal[True]

    @model_validator(mode="after")
    def require_some_confirmed_details(self):
        meaningful = (
            self.contractor_name, self.occupation, self.wage_amount, self.working_hours,
            self.location, self.payment_terms, self.start_date,
        )
        if not any(value is not None for value in meaningful):
            raise ValueError("At least one confirmed offer detail is required")
        return self


class OfferRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contractor_name: str | None
    occupation: str | None
    wage_amount: Decimal | None
    currency: str | None
    wage_period: str | None
    working_hours: str | None
    location: str | None
    payment_terms: str | None
    start_date: date | None
    source_type: str
    created_at: datetime


@router.post("/extract", response_model=ExtractedOffer)
async def extract_job_offer(
    user: WorkerUser,
    text: Annotated[str | None, Form(max_length=MAX_INPUT_TEXT_CHARS)] = None,
    image: UploadFile | None = File(default=None),
) -> ExtractedOffer:
    source_text = text.strip() if text and text.strip() else None
    if source_text is None and image is None:
        raise HTTPException(status_code=422, detail="Submit offer text, an image, or both.")
    if source_text is not None and len(source_text) > MAX_INPUT_TEXT_CHARS:
        raise HTTPException(status_code=413, detail="Offer text exceeds the 20,000 character limit.")

    image_bytes = None
    mime_type = None
    if image is not None:
        mime_type = (image.content_type or "").lower()
        if mime_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, WebP, HEIC, or HEIF image.")
        image_bytes = await image.read(MAX_IMAGE_BYTES + 1)
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Offer image exceeds the 10 MB limit.")
        if not image_bytes:
            raise HTTPException(status_code=422, detail="Uploaded image is empty.")

    # Extraction is a draft only. Nothing is written to the database here.
    return await extract_offer(source_text, image_bytes, mime_type)


@router.post("/save", response_model=OfferRecordOut, status_code=status.HTTP_201_CREATED)
def save_confirmed_offer(
    payload: OfferSaveRequest,
    user: WorkerUser,
    db: Annotated[Session, Depends(get_db)],
) -> OfferRecordOut:
    record = OfferRecord(
        worker_id=user.id,
        contractor_name=payload.contractor_name,
        occupation=payload.occupation,
        wage_amount=payload.wage_amount,
        currency=payload.currency,
        wage_period=payload.wage_period,
        working_hours=payload.working_hours,
        location=payload.location,
        payment_terms=payload.payment_terms,
        start_date=payload.start_date,
        source_type=payload.source_type,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return OfferRecordOut.model_validate(record)


@router.get("/saved", response_model=list[OfferRecordOut])
def saved_offers(user: WorkerUser, db: Annotated[Session, Depends(get_db)]) -> list[OfferRecordOut]:
    records = db.scalars(select(OfferRecord).where(OfferRecord.worker_id == user.id).order_by(OfferRecord.created_at.desc())).all()
    return [OfferRecordOut.model_validate(record) for record in records]
