from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.auth import router as auth_router
from app.config import settings
from app.database import check_database_connection
from app.marketplace import applications_router, jobs_router
from app.offer_scanner import router as offer_scanner_router
from app.trust_score import admin_router as trust_admin_router
from app.trust_score import feedback_router, score_router
from app.worker_protection import router as worker_protection_router
from app.complaints import admin_router as complaint_admin_router
from app.complaints import router as complaints_router

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Job marketplace and worker-protection API for ShramRakshak – JobTrust AI.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(jobs_router, prefix=settings.api_v1_prefix)
app.include_router(applications_router, prefix=settings.api_v1_prefix)
app.include_router(offer_scanner_router, prefix=settings.api_v1_prefix)
app.include_router(score_router, prefix=settings.api_v1_prefix)
app.include_router(trust_admin_router, prefix=settings.api_v1_prefix)
app.include_router(feedback_router, prefix=settings.api_v1_prefix)
app.include_router(worker_protection_router, prefix=settings.api_v1_prefix)
app.include_router(complaints_router, prefix=settings.api_v1_prefix)
app.include_router(complaint_admin_router, prefix=settings.api_v1_prefix)


@app.exception_handler(RequestValidationError)
async def sanitized_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Pydantic's default error payload can include submitted values (for
    # example, a password). Return locations/messages without request input.
    errors = [
        {"loc": error.get("loc", []), "msg": error.get("msg", "Invalid value."), "type": error.get("type", "value_error")}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.get("/health", tags=["health"], summary="Check API health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "shramrakshak-api"}


@app.get("/health/database", tags=["health"], summary="Check database connectivity")
def database_health() -> dict[str, str]:
    try:
        check_database_connection()
    except Exception as exc:
        # Do not return connection strings, credentials, or driver details.
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="Database is unavailable.") from exc
    return {"status": "ok", "service": "database"}


@app.get(settings.api_v1_prefix, tags=["api"], summary="API version information")
def api_v1() -> dict[str, str]:
    return {
        "project": "ShramRakshak",
        "api_version": "v1",
        "message": "API is ready for feature modules.",
    }
