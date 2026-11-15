import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import supabase_auth
from app.database import get_db
from app.main import app
from app.models import Base, Contractor, Job, JobApplication, User, Worker


@pytest.fixture
def protection_client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    ids = {"worker": uuid.uuid4(), "contractor": uuid.uuid4(), "admin": uuid.uuid4()}
    job_id, application_id = uuid.uuid4(), uuid.uuid4()
    db = TestingSession()
    db.add_all([
        User(id=ids["worker"], email="protection-worker@example.com", full_name="Worker Protect", role="worker"),
        User(id=ids["contractor"], email="protection-contractor@example.com", full_name="Contractor Protect", role="contractor"),
        User(id=ids["admin"], email="protection-admin@example.com", full_name="Admin Protect", role="admin"),
    ])
    db.add_all([
        Worker(user_id=ids["worker"], city="Pune"),
        Contractor(user_id=ids["contractor"], business_name="Protect Build"),
    ])
    job = Job(
        id=job_id,
        contractor_id=ids["contractor"],
        title="Site Painter",
        occupation="Painter",
        skill="Painting",
        location="Kothrud, Pune",
        wage_amount=1000,
        wage_period="day",
        working_hours="09:00-17:00",
        payment_terms="Paid each Friday",
        start_date=date(2026, 12, 10),
        status="filled",
    )
    db.add(job)
    db.add(JobApplication(id=application_id, job_id=job_id, worker_id=ids["worker"], status="accepted"))
    db.commit()
    db.close()

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    token_ids = {f"{role}-token": user_id for role, user_id in ids.items()}
    monkeypatch.setattr(supabase_auth, "get_user", lambda token: {"id": str(token_ids[token])})
    with TestClient(app) as client:
        yield client, ids, job_id, application_id
    app.dependency_overrides.clear()
    engine.dispose()


def test_agreement_versions_travel_check_reality_and_dispute_workflow(protection_client):
    client, ids, job_id, application_id = protection_client
    worker_headers = {"Authorization": "Bearer worker-token"}
    contractor_headers = {"Authorization": "Bearer contractor-token"}
    admin_headers = {"Authorization": "Bearer admin-token"}

    agreement_response = client.post(
        "/api/v1/agreements",
        headers=contractor_headers,
        json={
            "application_id": str(application_id),
            "accepted_wage": 1000,
            "currency": "INR",
            "wage_period": "day",
            "working_hours": "09:00-17:00",
            "location": "Kothrud, Pune",
            "payment_terms": "Paid each Friday",
            "start_date": "2026-12-10",
        },
    )
    assert agreement_response.status_code == 201, agreement_response.text
    agreement = agreement_response.json()
    agreement_id = agreement["id"]
    original = agreement["versions"][0]
    assert original["version_number"] == 1
    assert original["status"] == "pending"
    assert original["accepted_wage"] == "1000.00"

    worker_accept = client.post(
        f"/api/v1/agreements/{agreement_id}/versions/{original['id']}/accept",
        headers=worker_headers,
    )
    assert worker_accept.status_code == 200
    assert worker_accept.json()["status"] == "accepted"

    revised = client.post(
        f"/api/v1/agreements/{agreement_id}/versions",
        headers=contractor_headers,
        json={"accepted_wage": 1100, "working_hours": "08:30-16:30"},
    )
    assert revised.status_code == 201, revised.text
    revised_version = revised.json()
    assert revised_version["version_number"] == 2
    assert revised_version["status"] == "pending"

    history = client.get(f"/api/v1/agreements/{agreement_id}", headers=worker_headers)
    assert history.status_code == 200
    assert history.json()["versions"][0]["accepted_wage"] == "1000.00"  # original terms remain intact
    assert history.json()["versions"][1]["accepted_wage"] == "1100.00"
    assert history.json()["current_accepted_version"] == 1

    worker_accept_revision = client.post(
        f"/api/v1/agreements/{agreement_id}/versions/{revised_version['id']}/accept",
        headers=worker_headers,
    )
    assert worker_accept_revision.status_code == 200
    assert worker_accept_revision.json()["status"] == "accepted"

    travel = client.post(
        f"/api/v1/agreements/{agreement_id}/travel-confirmations",
        headers=worker_headers,
        json={"travel_date": "2026-12-10"},
    )
    assert travel.status_code == 201, travel.text
    travel_id = travel.json()["id"]
    blocked_departure = client.post(f"/api/v1/travel-confirmations/{travel_id}/depart", headers=worker_headers)
    assert blocked_departure.status_code == 409

    accepted_terms = {
        "accepted_wage": 1100,
        "currency": "INR",
        "wage_period": "day",
        "working_hours": "08:30-16:30",
        "location": "Kothrud, Pune",
        "payment_terms": "Paid each Friday",
        "start_date": "2026-12-10",
    }
    mismatched = client.post(
        f"/api/v1/travel-confirmations/{travel_id}/confirm",
        headers=contractor_headers,
        json={**accepted_terms, "accepted_wage": 1200},
    )
    assert mismatched.status_code == 200
    assert mismatched.json()["status"] == "terms_changed"
    assert client.post(f"/api/v1/travel-confirmations/{travel_id}/depart", headers=worker_headers).status_code == 409

    fresh_travel = client.post(
        f"/api/v1/agreements/{agreement_id}/travel-confirmations",
        headers=worker_headers,
        json={"travel_date": "2026-12-10"},
    )
    fresh_travel_id = fresh_travel.json()["id"]
    confirmed = client.post(
        f"/api/v1/travel-confirmations/{fresh_travel_id}/confirm",
        headers=contractor_headers,
        json=accepted_terms,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"
    departure = client.post(f"/api/v1/travel-confirmations/{fresh_travel_id}/depart", headers=worker_headers)
    assert departure.status_code == 200
    assert departure.json()["departure_recorded_at"] is not None

    reality = client.post(
        f"/api/v1/agreements/{agreement_id}/reality",
        headers=worker_headers,
        json={
            "agreement_version_id": revised_version["id"],
            "work_date": "2026-12-10",
            "actual_wage": 900,
            "actual_hours": 9.5,
            "payment_status": "partially_paid",
            "worker_notes": "Received only part of the agreed wage.",
        },
    )
    assert reality.status_code == 201, reality.text
    reality_data = reality.json()
    assert reality_data["promised_terms"]["accepted_wage"] == "1100.00"
    assert reality_data["actual_wage"] == "900.00"
    assert reality_data["payment_status"] == "partially_paid"

    complaint = client.post(
        "/api/v1/complaints",
        headers=worker_headers,
        json={
            "agreement_id": agreement_id,
            "reality_report_id": reality_data["id"],
            "job_id": str(job_id),
            "category": "payment",
            "description": "The wage received was lower than the accepted agreement amount.",
        },
    )
    assert complaint.status_code == 201, complaint.text
    complaint_id = complaint.json()["id"]
    assert complaint.json()["status"] == "submitted"

    evidence = client.post(
        f"/api/v1/complaints/{complaint_id}/evidence",
        headers=worker_headers,
        files=[("files", ("receipt.txt", b"Wage receipt reference 123", "text/plain"))],
    )
    assert evidence.status_code == 201, evidence.text
    evidence_id = evidence.json()[0]["id"]
    downloaded = client.get(f"/api/v1/complaints/{complaint_id}/evidence/{evidence_id}", headers=contractor_headers)
    assert downloaded.status_code == 200
    assert downloaded.content == b"Wage receipt reference 123"

    response = client.post(
        f"/api/v1/complaints/{complaint_id}/responses",
        headers=contractor_headers,
        json={"message": "We will review the wage record and respond with the payment details."},
    )
    assert response.status_code == 201
    assert client.get(f"/api/v1/admin/complaints?status=contractor_responded", headers=admin_headers).status_code == 200

    review = client.patch(
        f"/api/v1/admin/complaints/{complaint_id}/review",
        headers=admin_headers,
        json={"status": "under_review", "notes": "Reviewed the agreement, report, and attached receipt."},
    )
    assert review.status_code == 200, review.text
    resolved = client.patch(
        f"/api/v1/admin/complaints/{complaint_id}/review",
        headers=admin_headers,
        json={"status": "resolved", "outcome": "worker_upheld", "notes": "The submitted evidence supports the reported wage difference."},
    )
    assert resolved.status_code == 200, resolved.text
    final_record = resolved.json()
    assert final_record["status"] == "resolved"
    assert final_record["resolution_outcome"] == "worker_upheld"
    assert len(final_record["responses"]) == 1
    assert len(final_record["evidence"]) == 1
    assert len(final_record["reviews"]) == 2
