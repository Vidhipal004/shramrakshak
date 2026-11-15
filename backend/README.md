# Backend

FastAPI API with Supabase Auth, PostgreSQL-ready SQLAlchemy models, and Alembic migrations. The service uses Supabase Auth for password/session handling and stores application roles in `public.users`; the role from user-editable Auth metadata is never trusted. Public registration is limited to workers and contractors. Admin accounts must be provisioned by an administrator through a trusted process. RLS is enabled on the application tables without direct client policies; application data is accessed through this backend.

## Configure Supabase

1. Create a Supabase project and copy `.env.example` to `.env`.
2. Set `SUPABASE_URL` and `SUPABASE_ANON_KEY` using the project URL and public anon/publishable key. Do not put a `service_role` or secret key in the app configuration.
3. Set `DATABASE_URL` to the project's PostgreSQL connection string. Prefer the Supabase pooler for hosted deployments; URL-encode special characters in the password. SQLite remains the local fallback.
4. To use the offer scanner, set `GEMINI_API_KEY` (server-side only) and optionally `GEMINI_MODEL`.
5. Keep `.env` private; it is ignored by Git.

## Run on Windows PowerShell

From the `backend` folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

If activation is blocked, use the interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

## Routes

- `GET /health` – API process health.
- `GET /health/database` – checks the configured database without returning connection details.
- `GET /api/v1` – API version information.
- `POST /api/v1/auth/register` – create a worker or contractor account and profile.
- `POST /api/v1/auth/login` – sign in through Supabase Auth and return a bearer access token and DB-backed role.
- `POST /api/v1/auth/logout` – validate and revoke the current Supabase session.
- `GET /api/v1/auth/me` – return the authenticated profile.
- `GET /api/v1/auth/admin/me` – example admin-only route.
- `POST /api/v1/jobs` – contractor creates a listing with occupation, skill, wage, hours, location, payment terms, and start date.
- `GET /api/v1/jobs` – workers browse/search/filter open listings (`skill`, `location`, `min_wage`, `max_wage`, `start_date_from`, `start_date_to`). If worker/profile coordinates and job coordinates exist, results default to a 5 km radius; pass `latitude`, `longitude`, and optionally `radius_km` to override the center/radius.
- `GET /api/v1/jobs/mine`, `PATCH /api/v1/jobs/{job_id}`, and `DELETE /api/v1/jobs/{job_id}` – contractor listing management. Delete cancels the listing and preserves applications.
- `POST /api/v1/jobs/{job_id}/applications` – worker applies to an open listing.
- `GET /api/v1/applications/me` – worker views application statuses; pending applications can be withdrawn.
- `GET /api/v1/jobs/{job_id}/applications` and `PATCH /api/v1/jobs/{job_id}/applications/{application_id}` – listing owner reviews and accepts/rejects applicants.
- `POST /api/v1/offer-scanner/extract` – worker submits offer text, an image, or both; that input is sent to Gemini for OCR/structured extraction and returned as a nullable draft with source excerpts. Configure `GEMINI_API_KEY`; uploaded images and source text are not saved by this service's extract route.
- `POST /api/v1/offer-scanner/save` – save worker-corrected fields only after explicit `worker_confirmed: true`; `GET /api/v1/offer-scanner/saved` lists that worker's saved terms.
- `GET /api/v1/contractors/{contractor_id}/jobtrust-score` – score, weighted component breakdown, evidence coverage/confidence, and reasons.
- Admin evidence routes: `PUT /api/v1/admin/contractors/{contractor_id}/verification`, `POST /api/v1/admin/contractors/{contractor_id}/wage-evidence`, `POST /api/v1/admin/contractors/{contractor_id}/job-outcomes`, and `PATCH /api/v1/admin/feedback/{feedback_id}/review`.
- `POST /api/v1/jobs/{job_id}/feedback` – accepted workers can submit feedback; it does not affect scores until an admin verifies it.
- `POST /api/v1/agreements` – contractor records proposed accepted wage, currency, hours, location, payment terms, and start date for an accepted application.
- `GET /api/v1/agreements/mine` and `GET /api/v1/agreements/{agreement_id}` – participants view the agreement and complete version history. `POST /api/v1/agreements/{agreement_id}/versions` appends changed terms; the other party accepts or rejects. Version terms are immutable in the database.
- `POST /api/v1/agreements/{agreement_id}/travel-confirmations` – worker requests a pre-travel check. Contractor must reconfirm every accepted detail through `POST /api/v1/travel-confirmations/{confirmation_id}/confirm`; a mismatch blocks departure until terms are agreed and reconfirmed. `POST /api/v1/travel-confirmations/{confirmation_id}/depart` records departure only after confirmation.
- `POST /api/v1/agreements/{agreement_id}/reality` – worker appends actual wage, hours, and payment status against a specific accepted agreement version; `GET .../reality` shows promise beside reality.
- `/api/v1/complaints` – workers submit a complaint linked to an agreement or reality report, upload evidence, and view the case. Evidence is stored in the database and downloadable only by the worker, involved contractor, or admin.
- `POST /api/v1/complaints/{complaint_id}/responses` – involved contractor appends a response.
- `GET /api/v1/admin/complaints` and `PATCH /api/v1/admin/complaints/{complaint_id}/review` – admins review cases, append review history, and resolve or dismiss with an outcome.
- `/docs` and `/redoc` – API documentation.

JobTrust uses weights of 20% verification, 25% wage consistency, 20% completed outcomes, 20% verified worker feedback, and 15% listing completeness. The score is normalized over components with usable evidence and includes the available weight coverage. At least two components and 50% weight coverage are required to publish a score; below that, `score` is `null` with `insufficient_data`. Unverified records and unresolved disputes are excluded. This is an evidence summary, not a fraud finding.

Run the local suite with `python -m pytest -q`. Live Supabase checks require valid project credentials and a reachable PostgreSQL connection string in `.env`.
