import uuid
import fnmatch
import ipaddress
from typing import Annotated, Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import inspect as sa_inspect, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Contractor, Role, User, Worker
from app import supabase_auth
from app.config import settings

router = APIRouter(prefix="/auth", tags=["authentication"])
bearer = HTTPBearer(auto_error=False)


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)
    role: Literal["worker", "contractor"]
    phone: str | None = Field(default=None, max_length=30)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    business_name: str | None = Field(default=None, max_length=200)
    email_redirect_to: str | None = Field(default=None, max_length=500)
    code_challenge: str | None = Field(default=None, min_length=43, max_length=128, pattern=r"^[A-Za-z0-9._~-]+$")

    @model_validator(mode="after")
    def coordinates_are_a_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class ResendConfirmationRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    email_redirect_to: str = Field(min_length=1, max_length=500)
    code_challenge: str = Field(min_length=43, max_length=128, pattern=r"^[A-Za-z0-9._~-]+$")


class ProvisionWorkerRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=30)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def coordinates_are_a_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int | None = None
    user: UserResponse


class RegisterResponse(BaseModel):
    message: str
    user_id: uuid.UUID
    requires_email_confirmation: bool


class ProfilePatch(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=30)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    business_name: str | None = Field(default=None, max_length=200)


class ProfileResponse(UserResponse):
    phone: str | None = None
    city: str | None = None
    state: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    business_name: str | None = None
    verification_status: str | None = None


def _missing_profile() -> HTTPException:
    return HTTPException(status_code=403, detail="No ShramRakshak profile is provisioned for this account.")


def _email_redirect_allowed(candidate: str) -> bool:
    """Match the configured allowlist pattern and constrain Expo Go targets."""
    try:
        parsed = urlsplit(candidate)
        if (
            parsed.scheme != "exp"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path != "/--/auth/callback"
            or parsed.query
            or parsed.fragment
            or parsed.port is None
            or not 1 <= parsed.port <= 65535
            or not fnmatch.fnmatchcase(candidate, settings.supabase_email_redirect_url)
        ):
            return False
        host = parsed.hostname
        if host == "localhost":
            return True
        return bool(host and ipaddress.ip_address(host).is_private)
    except ValueError:
        return False


def _profile_for_auth_user(auth_user: dict, db: Session) -> User:
    try:
        user_id = uuid.UUID(str(auth_user["id"]))
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired access token.") from exc
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise _missing_profile()
    return user


def get_authenticated_supabase_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Bearer access token required.", headers={"WWW-Authenticate": "Bearer"})
    return supabase_auth.get_user(credentials.credentials)


AuthenticatedSupabaseUser = Annotated[dict, Depends(get_authenticated_supabase_user)]


def get_current_user(auth_user: AuthenticatedSupabaseUser, db: Annotated[Session, Depends(get_db)]) -> User:
    return _profile_for_auth_user(auth_user, db)


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role):
    def role_dependency(user: CurrentUser) -> User:
        if user.role not in {role.value for role in roles}:
            raise HTTPException(status_code=403, detail="Your role is not permitted to access this resource.")
        return user

    return role_dependency


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Annotated[Session, Depends(get_db)]) -> RegisterResponse:
    email = payload.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=422, detail="A valid email address is required.")

    try:
        db.execute(text("SELECT 1"))
        required_tables = {"users", "workers" if payload.role == Role.WORKER.value else "contractors"}
        available_tables = set(sa_inspect(db.get_bind()).get_table_names())
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database is unavailable; registration cannot be completed.") from exc

    if not required_tables.issubset(available_tables):
        raise HTTPException(status_code=503, detail="Database schema is not initialized; apply backend migrations before registration.")

    existing_profile = db.scalar(select(User).where(User.email == email))
    if existing_profile is not None:
        raise HTTPException(status_code=409, detail="An account already exists; sign in or resend its confirmation email.")

    if payload.email_redirect_to and not _email_redirect_allowed(payload.email_redirect_to):
        raise HTTPException(status_code=422, detail="Email confirmation redirect URL is not allowed.")
    auth_result = supabase_auth.register(
        email,
        payload.password,
        payload.full_name.strip(),
        redirect_url=payload.email_redirect_to,
        code_challenge=payload.code_challenge,
    )
    auth_user = auth_result.get("user")
    if not isinstance(auth_user, dict):
        # Keep compatibility with raw GoTrue responses and adapter test doubles.
        auth_user = auth_result if isinstance(auth_result.get("id"), str) else {}
    try:
        user_id = uuid.UUID(str(auth_user["id"]))
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="Supabase Auth did not return an account identifier.") from exc

    user = User(id=user_id, email=email, full_name=payload.full_name.strip(), role=payload.role)
    db.add(user)
    if payload.role == Role.WORKER.value:
        db.add(Worker(user=user, phone=payload.phone, city=payload.city, state=payload.state, latitude=payload.latitude, longitude=payload.longitude))
    else:
        db.add(Contractor(user=user, phone=payload.phone, city=payload.city, state=payload.state, business_name=payload.business_name))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A profile for this account already exists.") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Could not save the account profile to the database.") from exc

    session = auth_result.get("session")
    return RegisterResponse(
        message="Registration successful. Check your email to confirm the account if prompted.",
        user_id=user_id,
        requires_email_confirmation=not bool(session and session.get("access_token")),
    )


@router.post("/resend-confirmation", status_code=status.HTTP_200_OK)
def resend_confirmation(payload: ResendConfirmationRequest) -> dict[str, str]:
    email = payload.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=422, detail="A valid email address is required.")
    if not _email_redirect_allowed(payload.email_redirect_to):
        raise HTTPException(status_code=422, detail="Email confirmation redirect URL is not allowed.")
    supabase_auth.resend_signup_confirmation(
        email,
        redirect_url=payload.email_redirect_to,
        code_challenge=payload.code_challenge,
    )
    # Keep responses identical whether or not this address has a pending account.
    return {"message": "If an unconfirmed account exists, a confirmation email has been sent."}


@router.post("/provision-worker-profile", response_model=ProfileResponse)
def provision_worker_profile(
    payload: ProvisionWorkerRequest,
    auth_user: AuthenticatedSupabaseUser,
    db: Annotated[Session, Depends(get_db)],
) -> ProfileResponse:
    """Idempotently create a local worker profile for the signed-in Auth user."""
    try:
        user_id = uuid.UUID(str(auth_user["id"]))
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired access token.") from exc

    email = auth_user.get("email")
    if not isinstance(email, str) or "@" not in email:
        raise HTTPException(status_code=401, detail="Supabase Auth did not return a verified email address.")
    if not auth_user.get("email_confirmed_at"):
        raise HTTPException(status_code=403, detail="Email confirmation is required before profile provisioning.")

    user = db.get(User, user_id)
    if user is not None and user.role != Role.WORKER.value:
        raise HTTPException(status_code=409, detail="An account profile already exists with a different role.")

    worker = db.get(Worker, user_id)
    if user is None:
        metadata = auth_user.get("user_metadata") or {}
        full_name = payload.full_name or metadata.get("full_name")
        if not isinstance(full_name, str) or not full_name.strip():
            raise HTTPException(status_code=422, detail="A worker name is required to provision this profile.")
        user = User(id=user_id, email=email.strip().lower(), full_name=full_name.strip(), role=Role.WORKER.value)
        db.add(user)
    if worker is None:
        worker = Worker(
            user_id=user_id,
            phone=payload.phone,
            city=payload.city,
            state=payload.state,
            latitude=payload.latitude,
            longitude=payload.longitude,
        )
        db.add(worker)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # A concurrent retry may have provisioned this same Auth UID already.
        user = db.get(User, user_id)
        worker = db.get(Worker, user_id)
        if user is None or user.role != Role.WORKER.value or worker is None:
            raise HTTPException(status_code=409, detail="Could not provision the worker profile safely.") from exc

    return _profile_response(user, db)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> AuthResponse:
    result = supabase_auth.login(payload.email.strip().lower(), payload.password)
    token = result.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Sign-in did not return a valid session. Confirm your email and try again.")
    auth_user = result.get("user") or supabase_auth.get_user(token)
    profile = _profile_for_auth_user(auth_user, db)
    return AuthResponse(
        access_token=token,
        expires_in=result.get("expires_in"),
        user=UserResponse(id=profile.id, email=profile.email, full_name=profile.full_name, role=profile.role),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(user: CurrentUser, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> None:
    # `get_current_user` already validates the token against Supabase and loads
    # the profile; forward it to GoTrue to revoke the server-side session.
    if credentials is None:
        raise HTTPException(status_code=401, detail="Bearer access token required.")
    supabase_auth.logout(credentials.credentials)


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser) -> UserResponse:
    return UserResponse(id=user.id, email=user.email, full_name=user.full_name, role=user.role)


def _profile_response(user: User, db: Session) -> ProfileResponse:
    worker = db.get(Worker, user.id) if user.role == Role.WORKER.value else None
    contractor = db.get(Contractor, user.id) if user.role == Role.CONTRACTOR.value else None
    return ProfileResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        phone=worker.phone if worker else contractor.phone if contractor else None,
        city=worker.city if worker else contractor.city if contractor else None,
        state=worker.state if worker else contractor.state if contractor else None,
        latitude=worker.latitude if worker else None,
        longitude=worker.longitude if worker else None,
        business_name=contractor.business_name if contractor else None,
        verification_status=contractor.verification_status if contractor else None,
    )


@router.get("/profile", response_model=ProfileResponse)
def get_profile(user: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> ProfileResponse:
    return _profile_response(user, db)


@router.patch("/profile", response_model=ProfileResponse)
def update_profile(payload: ProfilePatch, user: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> ProfileResponse:
    changes = payload.model_dump(exclude_unset=True)
    if user.role == Role.ADMIN.value and changes:
        raise HTTPException(status_code=422, detail="Admin profile details are managed by the platform.")
    if "full_name" in changes:
        if changes["full_name"] is None:
            raise HTTPException(status_code=422, detail="Full name cannot be cleared.")
        user.full_name = changes.pop("full_name").strip()

    if user.role == Role.WORKER.value:
        profile = db.get(Worker, user.id)
    elif user.role == Role.CONTRACTOR.value:
        profile = db.get(Contractor, user.id)
        if "latitude" in changes or "longitude" in changes:
            raise HTTPException(status_code=422, detail="Contractor profiles do not use worker location coordinates.")
    else:
        profile = None
        if changes:
            raise HTTPException(status_code=422, detail="Admin profile details are managed by the platform.")

    if profile is None and changes:
        raise HTTPException(status_code=404, detail="Profile details not found.")
    if profile is not None:
        latitude = changes.get("latitude", getattr(profile, "latitude", None))
        longitude = changes.get("longitude", getattr(profile, "longitude", None))
        if (latitude is None) != (longitude is None):
            raise HTTPException(status_code=422, detail="latitude and longitude must be provided together.")
        allowed = {"phone", "city", "state", "latitude", "longitude"} if user.role == Role.WORKER.value else {"phone", "city", "state", "business_name"}
        if any(key not in allowed for key in changes):
            raise HTTPException(status_code=422, detail="Profile field is not editable for this role.")
        for field, value in changes.items():
            setattr(profile, field, value)
    db.commit()
    db.refresh(user)
    if profile is not None:
        db.refresh(profile)
    return _profile_response(user, db)


@router.get("/admin/me", response_model=UserResponse)
def admin_me(user: Annotated[User, Depends(require_roles(Role.ADMIN))]) -> UserResponse:
    return UserResponse(id=user.id, email=user.email, full_name=user.full_name, role=user.role)
