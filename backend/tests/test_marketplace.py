import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import supabase_auth
from app.database import get_db
from app.main import app
from app.models import Base, Contractor, User, Worker


@pytest.fixture
def marketplace_client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    worker_id, contractor_id = uuid.uuid4(), uuid.uuid4()

    db = TestingSession()
    db.add_all([
        User(id=worker_id, email="market-worker@example.com", full_name="Worker One", role="worker"),
        User(id=contractor_id, email="market-contractor@example.com", full_name="Contractor One", role="contractor"),
    ])
    db.add_all([
        Worker(user_id=worker_id, city="Pune", latitude=18.5204, longitude=73.8567),
        Contractor(user_id=contractor_id, business_name="Build Together"),
    ])
    db.commit()
    db.close()

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    original_get_user = supabase_auth.get_user
    monkeypatch.setattr(
        supabase_auth,
        "get_user",
        lambda token: {"id": str(worker_id if token == "worker-token" else contractor_id)},
    )
    with TestClient(app) as client:
        yield client, worker_id, contractor_id
    app.dependency_overrides.clear()
    monkeypatch.setattr(supabase_auth, "get_user", original_get_user)
    engine.dispose()


def test_contractor_to_worker_marketplace_workflow(marketplace_client):
    client, _, _ = marketplace_client
    contractor_headers = {"Authorization": "Bearer contractor-token"}
    worker_headers = {"Authorization": "Bearer worker-token"}

    close_job = {
        "title": "Mason for apartment site",
        "occupation": "Construction Mason",
        "skill": "Brick masonry",
        "description": "Lay block walls on a residential site.",
        "location": "Kothrud, Pune",
        "latitude": 18.55,
        "longitude": 73.8567,
        "wage_amount": 850,
        "wage_period": "day",
        "working_hours": "08:00–17:00, 1 hour break",
        "payment_terms": "Paid every evening after site close.",
        "start_date": "2026-12-05",
    }
    created = client.post("/api/v1/jobs", json=close_job, headers=contractor_headers)
    assert created.status_code == 201, created.text
    close_job_id = created.json()["id"]

    far_job = {**close_job, "title": "Mason near Hinjewadi", "location": "Hinjewadi, Pune", "latitude": 18.62}
    far_created = client.post("/api/v1/jobs", json=far_job, headers=contractor_headers)
    assert far_created.status_code == 201, far_created.text

    # The worker profile coordinates are used by default; the default radius is 5 km.
    nearby = client.get(
        "/api/v1/jobs?skill=mason&min_wage=800&max_wage=900&start_date_from=2026-12-01&start_date_to=2026-12-31",
        headers=worker_headers,
    )
    assert nearby.status_code == 200, nearby.text
    assert [job["id"] for job in nearby.json()] == [close_job_id]
    assert nearby.json()[0]["distance_km"] is not None

    applied = client.post(
        f"/api/v1/jobs/{close_job_id}/applications",
        json={"message": "I have six years of masonry experience."},
        headers=worker_headers,
    )
    assert applied.status_code == 201, applied.text
    application_id = applied.json()["id"]
    assert applied.json()["status"] == "pending"
    duplicate = client.post(f"/api/v1/jobs/{close_job_id}/applications", json={}, headers=worker_headers)
    assert duplicate.status_code == 409

    applications = client.get(f"/api/v1/jobs/{close_job_id}/applications", headers=contractor_headers)
    assert applications.status_code == 200, applications.text
    assert applications.json()[0]["worker_name"] == "Worker One"
    accepted = client.patch(
        f"/api/v1/jobs/{close_job_id}/applications/{application_id}",
        json={"status": "accepted"},
        headers=contractor_headers,
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"

    worker_applications = client.get("/api/v1/applications/me", headers=worker_headers)
    assert worker_applications.status_code == 200
    assert worker_applications.json()[0]["status"] == "accepted"
    assert worker_applications.json()[0]["job"]["occupation"] == "Construction Mason"

    updated = client.patch(
        f"/api/v1/jobs/{close_job_id}",
        json={"working_hours": "07:00–15:00", "payment_terms": "Weekly, every Friday."},
        headers=contractor_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["working_hours"] == "07:00–15:00"
    assert updated.json()["payment_terms"] == "Weekly, every Friday."

    wrong_role = client.post("/api/v1/jobs", json=close_job, headers=worker_headers)
    assert wrong_role.status_code == 403
