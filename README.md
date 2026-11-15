# ShramRakshak – JobTrust AI

ShramRakshak is a VibeX Codes Track 1 project focused on helping daily-wage workers find nearby work, assess job offers and contractor reliability, and keep a clear record of agreed wages.

## Repository structure

| Path | Purpose |
|---|---|
| `apps/` | User-facing application projects. |
| `apps/worker-mobile/` | Future mobile experience for workers to discover jobs, review offers, and track wage agreements. |
| `apps/contractor-web/` | Contractor-facing web application project. |
| `apps/admin-web/` | Admin-facing web application project for platform operations and review. |
| `backend/` | Server-side API and application logic. |
| `backend/app/` | Backend Python application package and API entry point. |
| `backend/tests/` | Backend automated tests. |
| `database/` | Database schema, migrations, and related database assets. |
| `docs/` | Project documentation, including architecture and interface notes. |

## Current workspace

This repository was not empty when the scaffolding was requested. Existing files and projects have been preserved. In addition to the requested folders, the workspace currently contains `apps/contractor-web-ui/`, a Vite frontend project, and existing backend starter code. The requested `worker-mobile/` and `admin-web/` folders are reserved project locations; no application features have been added to them as part of this setup.

See [docs/architecture.md](docs/architecture.md) for the planned system boundaries and data flow.

## Scope

This setup documents the project structure only. It does not implement job discovery, offer verification, contractor scoring, wage agreements, authentication, or database integration.
