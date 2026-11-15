"""Supabase GoTrue adapter tests; these never create remote auth users."""
import httpx
import pytest
from fastapi import HTTPException

from app import supabase_auth


def configure_auth(monkeypatch):
    monkeypatch.setattr(supabase_auth.settings, "supabase_url", "https://demo.supabase.co/")
    monkeypatch.setattr(supabase_auth.settings, "supabase_anon_key", "test-publishable-key-not-real")


def test_signup_sends_credentials_only_to_supabase_auth(monkeypatch, caplog):
    configure_auth(monkeypatch)
    calls = []

    def fake_request(method, url, *, headers, json, timeout, params=None):
        calls.append((method, url, headers, json, timeout, params))
        return httpx.Response(200, request=httpx.Request(method, url), json={
            "user": {"id": "12345678-1234-5678-1234-567812345678"},
            "session": {"access_token": "test-access-token"},
        })

    monkeypatch.setattr(supabase_auth.httpx, "request", fake_request)
    result = supabase_auth.register(
        "worker@example.test",
        "test-password",
        "Worker",
        redirect_url="exp://192.168.1.44:8081/--/auth/callback",
        code_challenge="a" * 43,
    )

    method, url, headers, body, timeout, params = calls[0]
    assert method == "POST"
    assert url == "https://demo.supabase.co/auth/v1/signup"
    assert headers["apikey"] == "test-publishable-key-not-real"
    assert body == {
        "email": "worker@example.test",
        "password": "test-password",
        "data": {"full_name": "Worker"},
        "code_challenge": "a" * 43,
        "code_challenge_method": "s256",
    }
    assert params == {"redirect_to": "exp://192.168.1.44:8081/--/auth/callback"}
    assert timeout == 10.0
    assert result["user"]["id"] == "12345678-1234-5678-1234-567812345678"
    assert "test-publishable-key-not-real" not in caplog.text
    assert "test-password" not in caplog.text


def test_login_uses_password_grant_and_supabase_user_endpoint(monkeypatch):
    configure_auth(monkeypatch)
    calls = []

    def fake_request(method, url, *, headers, json, timeout, params=None):
        calls.append((method, url, headers, json))
        return httpx.Response(200, request=httpx.Request(method, url), json={"access_token": "test-token"})

    monkeypatch.setattr(supabase_auth.httpx, "request", fake_request)
    result = supabase_auth.login("worker@example.test", "test-password")

    assert calls[0][0:2] == ("POST", "https://demo.supabase.co/auth/v1/token?grant_type=password")
    assert calls[0][3] == {"email": "worker@example.test", "password": "test-password"}
    assert result["access_token"] == "test-token"


def test_signup_normalizes_raw_gotrue_user_when_email_confirmation_is_enabled(monkeypatch):
    configure_auth(monkeypatch)

    def fake_request(method, url, **kwargs):
        return httpx.Response(200, request=httpx.Request(method, url), json={
            "id": "12345678-1234-5678-1234-567812345678",
            "email": "worker@example.test",
            "user_metadata": {"full_name": "Worker"},
            "confirmation_sent_at": "2025-01-01T00:00:00Z",
        })

    monkeypatch.setattr(supabase_auth.httpx, "request", fake_request)
    result = supabase_auth.register("worker@example.test", "test-password", "Worker")

    assert result["user"]["id"] == "12345678-1234-5678-1234-567812345678"
    assert result["session"] is None


def test_signup_does_not_send_allowlist_wildcard_as_redirect_to(monkeypatch):
    configure_auth(monkeypatch)
    monkeypatch.setattr(supabase_auth.settings, "supabase_email_redirect_url", "exp://**/--/auth/callback")
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return httpx.Response(200, request=httpx.Request(method, url), json={
            "id": "12345678-1234-5678-1234-567812345678",
        })

    monkeypatch.setattr(supabase_auth.httpx, "request", fake_request)
    supabase_auth.register("worker@example.test", "test-password", "Worker")

    assert calls[0][2]["params"] is None


def test_resend_signup_confirmation_reuses_existing_account_and_callback(monkeypatch):
    configure_auth(monkeypatch)
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return httpx.Response(200, request=httpx.Request(method, url), json={})

    monkeypatch.setattr(supabase_auth.httpx, "request", fake_request)
    supabase_auth.resend_signup_confirmation(
        "worker@example.test",
        redirect_url="exp://192.168.1.44:8081/--/auth/callback",
        code_challenge="a" * 43,
    )

    method, url, kwargs = calls[0]
    assert method == "POST"
    assert url == "https://demo.supabase.co/auth/v1/resend"
    assert kwargs["params"] == {"redirect_to": "exp://192.168.1.44:8081/--/auth/callback"}
    assert kwargs["json"] == {
        "email": "worker@example.test",
        "type": "signup",
        "code_challenge": "a" * 43,
        "code_challenge_method": "s256",
    }


def test_auth_errors_are_generic_and_signup_errors_are_not_misreported_as_login(monkeypatch):
    configure_auth(monkeypatch)
    secret_provider_message = "email already registered: provider-internal-detail"

    def fake_request(method, url, **kwargs):
        return httpx.Response(400, request=httpx.Request(method, url), json={"msg": secret_provider_message})

    monkeypatch.setattr(supabase_auth.httpx, "request", fake_request)
    with pytest.raises(HTTPException) as signup_error:
        supabase_auth.register("worker@example.test", "password", "Worker")
    assert signup_error.value.status_code == 400
    assert secret_provider_message not in signup_error.value.detail

    with pytest.raises(HTTPException) as login_error:
        supabase_auth.login("worker@example.test", "password")
    assert login_error.value.status_code == 401
    assert secret_provider_message not in login_error.value.detail


def test_missing_supabase_configuration_is_reported_without_network_call(monkeypatch):
    monkeypatch.setattr(supabase_auth.settings, "supabase_url", None)
    monkeypatch.setattr(supabase_auth.settings, "supabase_anon_key", None)
    with pytest.raises(HTTPException) as error:
        supabase_auth.login("worker@example.test", "password")
    assert error.value.status_code == 503
    assert "not configured" in error.value.detail


def test_network_errors_are_sanitized(monkeypatch):
    configure_auth(monkeypatch)

    def failed_request(*args, **kwargs):
        raise httpx.ConnectError("private connection detail")

    monkeypatch.setattr(supabase_auth.httpx, "request", failed_request)
    with pytest.raises(HTTPException) as error:
        supabase_auth.login("worker@example.test", "password")
    assert error.value.status_code == 502
    assert error.value.detail == "Supabase Auth could not be reached."
