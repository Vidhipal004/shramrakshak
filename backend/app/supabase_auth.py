"""Small GoTrue client using only the project's public anon/publishable key.

The Supabase service-role secret is not needed by these user-facing flows and
must never be sent to clients.
"""

from typing import Any

import httpx
from fastapi import HTTPException, status

from app.config import settings


def _configured() -> tuple[str, str]:
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase Auth is not configured on this server.",
        )
    return settings.supabase_url.rstrip("/"), settings.supabase_anon_key


def _request(
    method: str,
    path: str,
    *,
    access_token: str | None = None,
    json: dict[str, Any] | None = None,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    base_url, anon_key = _configured()
    headers = {"apikey": anon_key, "Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    try:
        response = httpx.request(method, f"{base_url}/auth/v1/{path}", headers=headers, json=json, params=params, timeout=10.0)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Supabase Auth could not be reached.") from exc
    if response.is_error:
        if response.status_code in (400, 401, 422):
            # Do not reflect arbitrary provider bodies or credentials to clients.
            if method.upper() == "POST" and path == "signup":
                raise HTTPException(status_code=400, detail="Supabase Auth rejected the registration request.")
            raise HTTPException(status_code=401, detail="Invalid credentials or authentication request.")
        if response.status_code == 429:
            raise HTTPException(status_code=429, detail="Too many authentication attempts. Try again later.")
        raise HTTPException(status_code=502, detail="Supabase Auth request failed.")
    if response.status_code == 204 or not response.content:
        return {}
    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Supabase Auth returned an invalid response.") from exc


def register(
    email: str,
    password: str,
    full_name: str,
    *,
    redirect_url: str | None = None,
    code_challenge: str | None = None,
) -> dict[str, Any]:
    params = {"redirect_to": redirect_url} if redirect_url else None
    payload: dict[str, Any] = {"email": email, "password": password, "data": {"full_name": full_name}}
    if code_challenge:
        payload.update({"code_challenge": code_challenge, "code_challenge_method": "s256"})
    response = _request(
        "POST",
        "signup",
        params=params,
        json=payload,
    )
    # The GoTrue REST endpoint can return a User object directly when email
    # confirmation is enabled (there is no session envelope in that response).
    # Supabase JS normalizes that shape to {user, session}; mirror that here.
    result = dict(response)
    nested_user = response.get("user")
    if isinstance(nested_user, dict):
        result["user"] = nested_user
    elif isinstance(response.get("id"), str):
        result["user"] = response
    else:
        result["user"] = None
    result["session"] = response.get("session")
    return result


def login(email: str, password: str) -> dict[str, Any]:
    return _request("POST", "token?grant_type=password", json={"email": email, "password": password})


def resend_signup_confirmation(email: str, *, redirect_url: str, code_challenge: str) -> dict[str, Any]:
    return _request(
        "POST",
        "resend",
        params={"redirect_to": redirect_url},
        json={
            "email": email,
            "type": "signup",
            "code_challenge": code_challenge,
            "code_challenge_method": "s256",
        },
    )


def get_user(access_token: str) -> dict[str, Any]:
    return _request("GET", "user", access_token=access_token)


def logout(access_token: str) -> None:
    _request("POST", "logout", access_token=access_token)
