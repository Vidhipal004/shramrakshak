import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth
from app.config import settings
from app.database import get_db
from app.main import app
from app.models import Base, Contractor, User, Worker


@pytest.fixture
def client():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    test_session = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = test_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    test_engine.dispose()


def test_registration_creates_worker_profile(client, monkeypatch):
    user_id = uuid.uuid4()
    monkeypatch.setattr(auth.supabase_auth, "register", lambda *args, **kwargs: {"user": {"id": str(user_id)}, "session": None})

    response = client.post(
        "/api/v1/auth/register",
        json={"email": "worker@example.com", "password": "strong-pass-123", "full_name": "A Worker", "role": "worker", "city": "Pune"},
    )
    assert response.status_code == 201
    assert response.json()["requires_email_confirmation"] is True
    db = next(app.dependency_overrides[get_db]())
    try:
        assert db.get(User, user_id).role == "worker"
        assert db.get(Worker, user_id).city == "Pune"
    finally:
        db.close()


def test_signup_with_confirmation_creates_profile_from_raw_gotrue_user(client, monkeypatch):
    user_id = uuid.uuid4()
    monkeypatch.setattr(
        auth.supabase_auth,
        "register",
        lambda *args, **kwargs: {
            "id": str(user_id),
            "email": "confirmed-later@example.com",
            "user_metadata": {"full_name": "A Worker"},
            "session": None,
        },
    )

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "confirmed-later@example.com",
            "password": "strong-pass-123",
            "full_name": "A Worker",
            "role": "worker",
            "city": "Pune",
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "message": "Registration successful. Check your email to confirm the account if prompted.",
        "user_id": str(user_id),
        "requires_email_confirmation": True,
    }
    db = next(app.dependency_overrides[get_db]())
    try:
        assert db.get(User, user_id).role == "worker"
        assert db.get(Worker, user_id).city == "Pune"
    finally:
        db.close()


def test_signup_without_supabase_user_id_returns_sanitized_error_and_creates_no_profile(client, monkeypatch):
    monkeypatch.setattr(auth.supabase_auth, "register", lambda *args, **kwargs: {"session": None})
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "missing-id@example.com",
            "password": "strong-pass-123",
            "full_name": "A Worker",
            "role": "worker",
        },
    )
    assert response.status_code == 502
    assert response.json()["detail"] == "Supabase Auth did not return an account identifier."
    db = next(app.dependency_overrides[get_db]())
    try:
        assert db.scalar(select(User).where(User.email == "missing-id@example.com")) is None
    finally:
        db.close()


def test_registration_schema_preflight_stops_before_supabase_signup():
    empty_engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    empty_session = sessionmaker(bind=empty_engine, autoflush=False, autocommit=False)
    supabase_calls = []

    def override_empty_db():
        db = empty_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_empty_db
    original_register = auth.supabase_auth.register
    auth.supabase_auth.register = lambda *args, **kwargs: supabase_calls.append(True)
    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                "/api/v1/auth/register",
                json={"email": "worker@example.com", "password": "strong-pass-123", "full_name": "Worker", "role": "worker"},
            )
        assert response.status_code == 503
        assert "schema is not initialized" in response.json()["detail"]
        assert supabase_calls == []
    finally:
        auth.supabase_auth.register = original_register
        app.dependency_overrides.clear()
        empty_engine.dispose()


def test_existing_local_account_is_not_submitted_to_supabase_signup(client, monkeypatch):
    user_id = uuid.uuid4()
    db = next(app.dependency_overrides[get_db]())
    db.add(User(id=user_id, email="worker@example.com", full_name="Existing Worker", role="worker"))
    db.add(Worker(user_id=user_id))
    db.commit()
    db.close()
    calls = []
    monkeypatch.setattr(auth.supabase_auth, "register", lambda *args, **kwargs: calls.append(True))

    response = client.post(
        "/api/v1/auth/register",
        json={"email": "worker@example.com", "password": "strong-pass-123", "full_name": "Worker", "role": "worker"},
    )
    assert response.status_code == 409
    assert calls == []


def test_resend_confirmation_for_existing_account_does_not_create_a_new_profile(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        auth.supabase_auth,
        "resend_signup_confirmation",
        lambda email, **kwargs: calls.append((email, kwargs)),
    )
    response = client.post(
        "/api/v1/auth/resend-confirmation",
        json={
            "email": " Worker@Example.com ",
            "email_redirect_to": "exp://192.168.1.44:8081/--/auth/callback",
            "code_challenge": "a" * 43,
        },
    )
    assert response.status_code == 200
    assert response.json() == {"message": "If an unconfirmed account exists, a confirmation email has been sent."}
    assert calls == [(
        "worker@example.com",
        {"redirect_url": "exp://192.168.1.44:8081/--/auth/callback", "code_challenge": "a" * 43},
    )]
    db = next(app.dependency_overrides[get_db]())
    try:
        assert db.scalar(select(User)) is None
    finally:
        db.close()


def test_verified_existing_supabase_user_is_provisioned_once_and_found_by_backend(client, monkeypatch):
    user_id = uuid.uuid4()
    auth_user = {
        "id": str(user_id),
        "email": "existing-worker@example.com",
        "email_confirmed_at": "2026-11-15T12:00:00Z",
        "user_metadata": {"full_name": "Existing Worker"},
    }
    monkeypatch.setattr(auth.supabase_auth, "get_user", lambda token: auth_user if token == "verified-existing-token" else {})
    headers = {"Authorization": "Bearer verified-existing-token"}

    provisioned = client.post("/api/v1/auth/provision-worker-profile", headers=headers, json={})
    assert provisioned.status_code == 200, provisioned.text
    assert provisioned.json()["id"] == str(user_id)
    assert provisioned.json()["role"] == "worker"

    found = client.get("/api/v1/auth/me", headers=headers)
    assert found.status_code == 200
    assert found.json()["id"] == str(user_id)
    assert found.json()["role"] == "worker"

    repeated = client.post("/api/v1/auth/provision-worker-profile", headers=headers, json={})
    assert repeated.status_code == 200
    db = next(app.dependency_overrides[get_db]())
    try:
        assert db.scalar(select(User).where(User.id == user_id)).role == "worker"
        assert db.scalar(select(Worker).where(Worker.user_id == user_id)) is not None
        assert len(db.scalars(select(Worker).where(Worker.user_id == user_id)).all()) == 1
    finally:
        db.close()


def test_worker_profile_provisioning_requires_verified_supabase_email(client, monkeypatch):
    monkeypatch.setattr(auth.supabase_auth, "get_user", lambda _token: {
        "id": str(uuid.uuid4()),
        "email": "unconfirmed@example.com",
        "user_metadata": {"full_name": "Unconfirmed Worker"},
    })
    response = client.post(
        "/api/v1/auth/provision-worker-profile",
        headers={"Authorization": "Bearer unconfirmed-token"},
        json={},
    )
    assert response.status_code == 403
    assert "Email confirmation" in response.json()["detail"]


def test_worker_registration_only_accepts_configured_email_redirect(client, monkeypatch):
    calls = []
    user_id = uuid.uuid4()

    def fake_register(*args, **kwargs):
        calls.append(kwargs)
        return {"user": {"id": str(user_id)}, "session": None}

    monkeypatch.setattr(auth.supabase_auth, "register", fake_register)
    good = client.post(
        "/api/v1/auth/register",
        json={
            "email": "worker@example.com",
            "password": "strong-pass-123",
            "full_name": "A Worker",
            "role": "worker",
            "email_redirect_to": "exp://192.168.1.25:8081/--/auth/callback",
            "code_challenge": "a" * 43,
        },
    )
    assert good.status_code == 201
    assert calls == [{"redirect_url": "exp://192.168.1.25:8081/--/auth/callback", "code_challenge": "a" * 43}]

    denied = client.post(
        "/api/v1/auth/register",
        json={
            "email": "other@example.com",
            "password": "strong-pass-123",
            "full_name": "Other Worker",
            "role": "worker",
            "email_redirect_to": "exp://evil.example:8081/--/auth/callback",
        },
    )
    assert denied.status_code == 422


def test_registration_rejects_password_shorter_than_eight_without_calling_supabase(client, monkeypatch):
    called = []
    monkeypatch.setattr(auth.supabase_auth, "register", lambda *args, **kwargs: called.append(True))
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "worker@example.com", "password": "short7!", "full_name": "Worker", "role": "worker"},
    )
    assert response.status_code == 422
    assert called == []


def test_expo_go_redirect_allowlist_matches_dynamic_local_host_only(monkeypatch):
    monkeypatch.setattr(settings, "supabase_email_redirect_url", "exp://**/--/auth/callback")
    assert auth._email_redirect_allowed("exp://192.168.1.25:8081/--/auth/callback")
    assert auth._email_redirect_allowed("exp://localhost:8081/--/auth/callback")
    assert not auth._email_redirect_allowed("https://example.com/--/auth/callback")
    assert not auth._email_redirect_allowed("exp://192.168.1.25:8081/wrong/callback")
    assert not auth._email_redirect_allowed("exp://8.8.8.8:8081/--/auth/callback")


def test_public_registration_rejects_admin_role(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "admin@example.com", "password": "strong-pass-123", "full_name": "Admin", "role": "admin"},
    )
    assert response.status_code == 422
    assert "strong-pass-123" not in response.text


def test_login_and_current_user_role_comes_from_database(client, monkeypatch):
    user_id = uuid.uuid4()
    db = next(app.dependency_overrides[get_db]())
    db.add(User(id=user_id, email="contractor@example.com", full_name="A Contractor", role="contractor"))
    db.add(Contractor(user_id=user_id, business_name="Build Co"))
    db.commit()
    db.close()

    monkeypatch.setattr(auth.supabase_auth, "login", lambda *args: {"access_token": "test-token", "expires_in": 3600, "user": {"id": str(user_id)}})
    monkeypatch.setattr(auth.supabase_auth, "get_user", lambda token: {"id": str(user_id)})
    response = client.post("/api/v1/auth/login", json={"email": "contractor@example.com", "password": "strong-pass-123"})
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "contractor"

    denied = client.get("/api/v1/auth/admin/me", headers={"Authorization": "Bearer test-token"})
    assert denied.status_code == 403


def test_missing_bearer_token_is_rejected(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_logout_revokes_supabase_session(client, monkeypatch):
    user_id = uuid.uuid4()
    db = next(app.dependency_overrides[get_db]())
    db.add(User(id=user_id, email="worker@example.com", full_name="A Worker", role="worker"))
    db.add(Worker(user_id=user_id))
    db.commit()
    db.close()

    revoked = []
    monkeypatch.setattr(auth.supabase_auth, "get_user", lambda token: {"id": str(user_id)})
    monkeypatch.setattr(auth.supabase_auth, "logout", lambda token: revoked.append(token))
    response = client.post("/api/v1/auth/logout", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 204
    assert revoked == ["test-token"]


def test_admin_role_can_access_admin_route(client, monkeypatch):
    user_id = uuid.uuid4()
    db = next(app.dependency_overrides[get_db]())
    db.add(User(id=user_id, email="admin@example.com", full_name="Platform Admin", role="admin"))
    db.commit()
    db.close()
    monkeypatch.setattr(auth.supabase_auth, "get_user", lambda token: {"id": str(user_id)})

    response = client.get("/api/v1/auth/admin/me", headers={"Authorization": "Bearer admin-token"})
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_admin_profile_is_read_only(client, monkeypatch):
    user_id = uuid.uuid4()
    db = next(app.dependency_overrides[get_db]())
    db.add(User(id=user_id, email="readonly-admin@example.com", full_name="Platform Admin", role="admin"))
    db.commit()
    db.close()
    monkeypatch.setattr(auth.supabase_auth, "get_user", lambda token: {"id": str(user_id)})

    response = client.patch(
        "/api/v1/auth/profile",
        json={"full_name": "Changed Admin"},
        headers={"Authorization": "Bearer admin-token"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Admin profile details are managed by the platform."
    unchanged = client.get("/api/v1/auth/profile", headers={"Authorization": "Bearer admin-token"})
    assert unchanged.status_code == 200
    assert unchanged.json()["full_name"] == "Platform Admin"
