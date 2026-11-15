import uuid
import asyncio
import json
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import offer_scanner, supabase_auth
from app.database import get_db
from app import gemini_scanner
from app.gemini_scanner import ExtractedOffer
from app.main import app
from app.models import (
    Base,
    Contractor,
    ContractorFeedback,
    Job,
    JobApplication,
    JobOutcomeEvidence,
    OfferRecord,
    User,
    WageEvidence,
    Worker,
)


@pytest.fixture
def feature_client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    ids = {"worker": uuid.uuid4(), "contractor": uuid.uuid4(), "admin": uuid.uuid4()}
    db = TestingSession()
    db.add_all([
        User(id=ids["worker"], email="feature-worker@example.com", full_name="Feature Worker", role="worker"),
        User(id=ids["contractor"], email="feature-contractor@example.com", full_name="Feature Contractor", role="contractor"),
        User(id=ids["admin"], email="feature-admin@example.com", full_name="Feature Admin", role="admin"),
    ])
    db.add_all([Worker(user_id=ids["worker"]), Contractor(user_id=ids["contractor"], business_name="Feature Build")])
    db.commit()
    db.close()

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    token_roles = {f"{role}-token": user_id for role, user_id in ids.items()}
    monkeypatch.setattr(supabase_auth, "get_user", lambda token: {"id": str(token_roles[token])})
    with TestClient(app) as client:
        yield client, ids, TestingSession
    app.dependency_overrides.clear()
    engine.dispose()


def test_offer_scanner_returns_editable_draft_then_saves_worker_correction(feature_client, monkeypatch):
    client, ids, TestingSession = feature_client
    worker_headers = {"Authorization": "Bearer worker-token"}
    observed = {}

    async def fake_extract(source_text, image_bytes, mime_type):
        observed.update({"source_text": source_text, "image_bytes": image_bytes, "mime_type": mime_type})
        return ExtractedOffer(
            contractor_name="Build Co",
            occupation="Painter",
            wage_amount=Decimal("900"),
            currency="INR",
            wage_period="day",
            working_hours="09:00 to 17:00",
            location=None,
            payment_terms="Paid weekly",
            start_date=date(2026, 12, 1),
            field_evidence={"contractor_name": "Build Co", "wage_amount": "₹900/day"},
            notes=["Please review every extracted field."],
        )

    monkeypatch.setattr(offer_scanner, "extract_offer", fake_extract)
    extracted = client.post(
        "/api/v1/offer-scanner/extract",
        data={"text": "Build Co needs a painter. Pay ₹900/day, weekly."},
        files={"image": ("offer.png", b"fake png bytes", "image/png")},
        headers=worker_headers,
    )
    assert extracted.status_code == 200, extracted.text
    assert extracted.json()["wage_amount"] == "900"
    assert extracted.json()["location"] is None
    assert observed["mime_type"] == "image/png"
    assert observed["source_text"].startswith("Build Co")

    # Extract is deliberately draft-only; an explicit worker-confirmed save is required.
    db = TestingSession()
    assert db.query(OfferRecord).count() == 0
    db.close()
    saved = client.post(
        "/api/v1/offer-scanner/save",
        headers=worker_headers,
        json={
            "contractor_name": "Build Co",
            "occupation": "Painter",
            "wage_amount": 950,
            "currency": "INR",
            "wage_period": "day",
            "working_hours": "09:00 to 17:00",
            "location": "Kothrud, Pune",
            "payment_terms": "Paid weekly",
            "start_date": "2026-12-01",
            "source_type": "both",
            "worker_confirmed": True,
        },
    )
    assert saved.status_code == 201, saved.text
    assert Decimal(saved.json()["wage_amount"]) == Decimal("950")
    assert saved.json()["location"] == "Kothrud, Pune"
    assert saved.json()["id"]

    history = client.get("/api/v1/offer-scanner/saved", headers=worker_headers)
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["contractor_name"] == "Build Co"


def test_offer_image_upload_limits_type_and_size(feature_client):
    client, _, _ = feature_client
    headers = {"Authorization": "Bearer worker-token"}
    unsupported = client.post(
        "/api/v1/offer-scanner/extract",
        files={"image": ("offer.svg", b"<svg/>", "image/svg+xml")},
        headers=headers,
    )
    assert unsupported.status_code == 415


def test_gemini_request_uses_private_key_header_and_discards_uncited_text(monkeypatch):
    monkeypatch.setattr(gemini_scanner.settings, "gemini_api_key", "test-private-key")
    observed = {}
    generated = {
        "contractor_name": "Invented Contractor",
        "occupation": "Painter",
        "wage_amount": 900,
        "currency": "INR",
        "wage_period": "day",
        "working_hours": None,
        "location": "Pune",
        "payment_terms": None,
        "start_date": None,
        "field_evidence": {
            "contractor_name": "A different company",
            "occupation": "Painter",
            "wage_amount": "Pay ₹900/day",
            "currency": "₹",
            "wage_period": "₹900/day",
            "working_hours": None,
            "location": "Pune",
            "payment_terms": None,
            "start_date": None,
        },
        "notes": [],
    }

    class FakeResponse:
        status_code = 200
        is_error = False

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": json.dumps(generated)}]}}]}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers, json):
            observed.update({"url": url, "headers": headers, "request": json})
            return FakeResponse()

    monkeypatch.setattr(gemini_scanner.httpx, "AsyncClient", FakeClient)
    result = asyncio.run(gemini_scanner.extract_offer("Painter needed in Pune. Pay ₹900/day.", b"imagebytes", "image/png"))

    assert observed["headers"]["x-goog-api-key"] == "test-private-key"
    assert "test-private-key" not in observed["url"]
    assert observed["request"]["contents"][0]["parts"][2]["inlineData"]["mimeType"] == "image/png"
    assert result.contractor_name == "Invented Contractor"  # image evidence is left for worker review
    assert result.occupation == "Painter"
    assert result.wage_amount == Decimal("900")
    text_only_result = gemini_scanner.validate_extraction(generated, "Painter needed in Pune. Pay ₹900/day.")
    assert text_only_result.contractor_name is None
    assert any("did not match" in note for note in text_only_result.notes)


def test_new_contractor_has_insufficient_data_not_zero(feature_client):
    client, ids, _ = feature_client
    response = client.get(
        f"/api/v1/contractors/{ids['contractor']}/jobtrust-score",
        headers={"Authorization": "Bearer worker-token"},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "insufficient_data"
    assert result["score"] is None
    assert result["confidence"]["level"] == "insufficient"
    assert result["components"][0]["score"] == 0
    assert result["components"][1]["score"] is None
    assert "Missing components are excluded rather than treated as zero." in result["reasons"]


def test_jobtrust_uses_fixed_weights_and_excludes_unverified_or_unresolved_evidence(feature_client):
    client, ids, TestingSession = feature_client
    db = TestingSession()
    contractor = db.get(Contractor, ids["contractor"])
    contractor.verification_status = "verified"
    worker_ids = [ids["worker"], uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
    for idx, worker_id in enumerate(worker_ids[1:], start=2):
        db.add(User(id=worker_id, email=f"worker{idx}@example.com", full_name=f"Worker {idx}", role="worker"))
        db.add(Worker(user_id=worker_id))
    job = Job(
        contractor_id=ids["contractor"], title="Experienced painter", occupation="Painter", skill="Painting",
        location="Pune", wage_amount=Decimal("1000"), wage_period="day", working_hours="09:00-17:00",
        payment_terms="Paid weekly", start_date=date(2026, 12, 1), status="filled",
    )
    db.add(job)
    db.flush()
    applications = []
    for worker_id in worker_ids:
        application = JobApplication(job_id=job.id, worker_id=worker_id, status="accepted")
        db.add(application)
        db.flush()
        applications.append(application)

    db.add_all([
        WageEvidence(application_id=applications[0].id, contractor_id=ids["contractor"], agreed_wage=1000, paid_wage=800, is_verified=True, dispute_status="none"),
        WageEvidence(application_id=applications[1].id, contractor_id=ids["contractor"], agreed_wage=1000, paid_wage=0, is_verified=False, dispute_status="none"),
        WageEvidence(application_id=applications[2].id, contractor_id=ids["contractor"], agreed_wage=1000, paid_wage=0, is_verified=True, dispute_status="unresolved"),
        JobOutcomeEvidence(application_id=applications[0].id, contractor_id=ids["contractor"], completed=True, is_verified=True, dispute_status="none"),
        JobOutcomeEvidence(application_id=applications[1].id, contractor_id=ids["contractor"], completed=False, is_verified=False, dispute_status="none"),
        JobOutcomeEvidence(application_id=applications[2].id, contractor_id=ids["contractor"], completed=False, is_verified=True, dispute_status="unresolved"),
        ContractorFeedback(application_id=applications[0].id, contractor_id=ids["contractor"], worker_id=worker_ids[0], rating=4, is_verified=True, dispute_status="none"),
        ContractorFeedback(application_id=applications[1].id, contractor_id=ids["contractor"], worker_id=worker_ids[1], rating=1, is_verified=False, dispute_status="none"),
        ContractorFeedback(application_id=applications[2].id, contractor_id=ids["contractor"], worker_id=worker_ids[2], rating=1, is_verified=True, dispute_status="unresolved"),
    ])
    db.commit()
    db.close()

    response = client.get(
        f"/api/v1/contractors/{ids['contractor']}/jobtrust-score",
        headers={"Authorization": "Bearer worker-token"},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "scored"
    assert result["score"] == 91.0
    assert result["confidence"]["data_coverage_pct"] == 100.0
    components = {component["key"]: component for component in result["components"]}
    assert {key: components[key]["weight_pct"] for key in components} == {
        "contractor_verification": 20,
        "wage_consistency": 25,
        "previous_job_completion": 20,
        "worker_feedback": 20,
        "job_information_completeness": 15,
    }
    assert components["wage_consistency"]["score"] == 80.0
    assert components["wage_consistency"]["excluded_count"] == 2
    assert components["previous_job_completion"]["score"] == 100.0
    assert components["previous_job_completion"]["excluded_count"] == 2
    assert components["worker_feedback"]["score"] == 80.0
    assert components["worker_feedback"]["excluded_count"] == 2
