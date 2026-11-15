"""Cross-module workflow check with an isolated DB and mocked external providers."""
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import offer_scanner, supabase_auth
from app.database import get_db
from app.gemini_scanner import ExtractedOffer
from app.main import app
from app.models import Base, User


@pytest.fixture
def workflow(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    ids = {"worker": uuid.uuid4(), "contractor": uuid.uuid4(), "admin": uuid.uuid4()}
    by_email = {f"{role}@example.test": user_id for role, user_id in ids.items()}
    tokens = {f"{role}-session": user_id for role, user_id in ids.items()}

    def fake_register(email, _password, _name, **_kwargs):
        return {"user": {"id": str(by_email[email])}, "session": {"access_token": f"{email.split('@')[0]}-session"}}

    def fake_login(email, _password):
        role = email.split("@", 1)[0]
        return {"access_token": f"{role}-session", "expires_in": 3600, "user": {"id": str(ids[role])}}

    monkeypatch.setattr(supabase_auth, "register", fake_register)
    monkeypatch.setattr(supabase_auth, "login", fake_login)
    monkeypatch.setattr(supabase_auth, "get_user", lambda token: {"id": str(tokens[token])})
    monkeypatch.setattr(supabase_auth, "logout", lambda _token: None)

    async def fake_extract(_text, _image_bytes, _mime_type):
        return ExtractedOffer(
            contractor_name="Nirman Works", occupation="Painter", wage_amount=900,
            currency="INR", wage_period="day", working_hours="09:00-17:00",
            location="Kothrud, Pune", payment_terms="Paid daily", start_date=date(2026, 12, 1),
            field_evidence={"wage_amount": "₹900 per day"}, notes=[],
        )

    monkeypatch.setattr(offer_scanner, "extract_offer", fake_extract)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, ids
    app.dependency_overrides.clear()
    engine.dispose()


def test_worker_to_contractor_to_admin_workflow(workflow):
    client, ids = workflow

    # Registration and Supabase-style login, with the role persisted in our DB.
    worker_registration = client.post("/api/v1/auth/register", json={
        "email": "worker@example.test", "password": "worker-password-123", "full_name": "Asha Worker",
        "role": "worker", "city": "Pune", "latitude": 18.5204, "longitude": 73.8567,
    })
    assert worker_registration.status_code == 201, worker_registration.text
    contractor_registration = client.post("/api/v1/auth/register", json={
        "email": "contractor@example.test", "password": "builder-password-123", "full_name": "Nirman Owner",
        "role": "contractor", "business_name": "Nirman Works", "city": "Pune",
    })
    assert contractor_registration.status_code == 201, contractor_registration.text
    admin_db = next(app.dependency_overrides[get_db]())
    try:
        admin_db.add(User(id=ids["admin"], email="admin@example.test", full_name="Platform Admin", role="admin"))
        admin_db.commit()
    finally:
        admin_db.close()
    worker_token = client.post("/api/v1/auth/login", json={"email": "worker@example.test", "password": "worker-password-123"}).json()["access_token"]
    contractor_token = client.post("/api/v1/auth/login", json={"email": "contractor@example.test", "password": "builder-password-123"}).json()["access_token"]
    admin_token = client.post("/api/v1/auth/login", json={"email": "admin@example.test", "password": "admin-password-123"}).json()["access_token"]
    worker = {"Authorization": f"Bearer {worker_token}"}
    contractor = {"Authorization": f"Bearer {contractor_token}"}
    admin = {"Authorization": f"Bearer {admin_token}"}

    # A nearby listing is discoverable within the default radius; a distant one is not.
    listing = {"title": "Site painter", "occupation": "Painter", "skill": "Painting", "location": "Kothrud, Pune",
        "latitude": 18.521, "longitude": 73.857, "wage_amount": 900, "wage_period": "day",
        "working_hours": "09:00-17:00", "payment_terms": "Paid daily", "start_date": "2026-12-01"}
    job_response = client.post("/api/v1/jobs", headers=contractor, json=listing)
    assert job_response.status_code == 201, job_response.text
    job = job_response.json()
    far_response = client.post("/api/v1/jobs", headers=contractor, json={**listing, "title": "Far painter", "location": "Mumbai", "latitude": 19.076, "longitude": 72.8777})
    assert far_response.status_code == 201, far_response.text
    nearby = client.get("/api/v1/jobs?skill=Painter", headers=worker)
    assert nearby.status_code == 200, nearby.text
    assert [entry["id"] for entry in nearby.json()] == [job["id"]]
    assert nearby.json()[0]["distance_km"] < 5

    # Scanner extraction is mocked at the Gemini boundary; persistence still uses the real endpoint and DB.
    extracted = client.post("/api/v1/offer-scanner/extract", headers=worker, data={"text": "Painter, ₹900 per day, Kothrud, Pune"})
    assert extracted.status_code == 200, extracted.text
    assert extracted.json()["wage_amount"] == "900"
    saved = client.post("/api/v1/offer-scanner/save", headers=worker, json={
        "contractor_name": "Nirman Works", "occupation": "Painter", "wage_amount": 900, "currency": "INR",
        "wage_period": "day", "working_hours": "09:00-17:00", "location": "Kothrud, Pune",
        "payment_terms": "Paid daily", "start_date": "2026-12-01", "source_type": "text", "worker_confirmed": True,
    })
    assert saved.status_code == 201, saved.text
    assert len(client.get("/api/v1/offer-scanner/saved", headers=worker).json()) == 1
    trust = client.get(f"/api/v1/contractors/{job['contractor_id']}/jobtrust-score", headers=worker)
    assert trust.status_code == 200, trust.text
    assert trust.json()["status"] == "insufficient_data"  # New/unverified contractor is not assigned an invented zero.
    assert trust.json()["score"] is None

    # Apply, contractor accepts, then worker accepts the immutable wage agreement version.
    application_response = client.post(f"/api/v1/jobs/{job['id']}/applications", headers=worker, json={"message": "Painter with site experience."})
    assert application_response.status_code == 201, application_response.text
    application_id = application_response.json()["id"]
    accepted_application = client.patch(f"/api/v1/jobs/{job['id']}/applications/{application_id}", headers=contractor, json={"status": "accepted"})
    assert accepted_application.status_code == 200, accepted_application.text
    agreement_response = client.post("/api/v1/agreements", headers=contractor, json={
        "application_id": application_id, "accepted_wage": 900, "currency": "INR", "wage_period": "day",
        "working_hours": "09:00-17:00", "location": "Kothrud, Pune", "payment_terms": "Paid daily", "start_date": "2026-12-01",
    })
    assert agreement_response.status_code == 201, agreement_response.text
    agreement = agreement_response.json()
    version = agreement["versions"][0]
    assert client.post(f"/api/v1/agreements/{agreement['id']}/versions/{version['id']}/accept", headers=worker).status_code == 200

    # Contractor reconfirms exact accepted terms before worker departure.
    travel_response = client.post(f"/api/v1/agreements/{agreement['id']}/travel-confirmations", headers=worker, json={"travel_date": "2026-12-01"})
    assert travel_response.status_code == 201, travel_response.text
    travel_id = travel_response.json()["id"]
    assert client.post(f"/api/v1/travel-confirmations/{travel_id}/depart", headers=worker).status_code == 409
    confirm_response = client.post(f"/api/v1/travel-confirmations/{travel_id}/confirm", headers=contractor, json={
        "accepted_wage": 900, "currency": "INR", "wage_period": "day", "working_hours": "09:00-17:00",
        "location": "Kothrud, Pune", "payment_terms": "Paid daily", "start_date": "2026-12-01",
    })
    assert confirm_response.status_code == 200 and confirm_response.json()["status"] == "confirmed"
    assert client.post(f"/api/v1/travel-confirmations/{travel_id}/depart", headers=worker).status_code == 200

    # Promise vs reality; underpayment triggers a complaint with supporting evidence and admin review.
    reality_response = client.post(f"/api/v1/agreements/{agreement['id']}/reality", headers=worker, json={
        "agreement_version_id": version["id"], "work_date": "2026-12-01", "actual_wage": 700,
        "actual_hours": 9, "payment_status": "partially_paid", "worker_notes": "Only part of today's agreed wage was received.",
    })
    assert reality_response.status_code == 201, reality_response.text
    reality = reality_response.json()
    assert reality["promised_terms"]["accepted_wage"] == "900.00" and reality["actual_wage"] == "700.00"
    complaint_response = client.post("/api/v1/complaints", headers=worker, json={
        "agreement_id": agreement["id"], "reality_report_id": reality["id"], "job_id": job["id"],
        "category": "payment", "description": "Only part of my accepted daily wage was paid after the shift.",
    })
    assert complaint_response.status_code == 201, complaint_response.text
    complaint = complaint_response.json()
    evidence = client.post(f"/api/v1/complaints/{complaint['id']}/evidence", headers=worker,
        files=[("files", ("receipt.txt", b"Payment received: 700 INR", "text/plain"))])
    assert evidence.status_code == 201, evidence.text
    contractor_reply = client.post(f"/api/v1/complaints/{complaint['id']}/responses", headers=contractor,
        json={"message": "We received the report and will verify the remaining wage payment."})
    assert contractor_reply.status_code == 201, contractor_reply.text
    review = client.patch(f"/api/v1/admin/complaints/{complaint['id']}/review", headers=admin, json={
        "status": "resolved", "outcome": "worker_upheld", "notes": "The submitted agreement and report support the worker's underpayment claim.",
    })
    assert review.status_code == 200, review.text
    assert review.json()["status"] == "resolved"
    assert len(review.json()["reviews"]) == 1
