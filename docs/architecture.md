# Architecture

## Project areas

| Path | Responsibility |
|---|---|
| `apps/worker-mobile/` | Expo React Native worker client for job discovery, offer scanning, JobTrust reports, wage agreements, travel confirmations, work reality reports, complaints, evidence, and profile management. |
| `apps/contractor-web/` | Vite contractor workspace for listings, applicants, agreements, pre-travel reconfirmations, complaint responses, JobTrust, and contractor profiles. |
| `apps/admin-web/` | Vite operations console for contractor verification, JobTrust evidence summaries, and complaint review. |
| `apps/contractor-web-ui/` | Preserved pre-existing Vite starter project; it is not the active contractor client. |
| `backend/app/` | FastAPI routes, authentication, marketplace and worker-protection business logic, scanner integration, and JobTrust calculations. |
| `backend/tests/` | Backend behavior and workflow tests. |
| `database/` | Database assets and migration-related project materials. |
| `docs/` | Architecture and product documentation. |

## System boundary

```text
Worker mobile client ─┐
Contractor web client ─┼──> FastAPI API ───> PostgreSQL / local SQLite
Admin web client ─────┘                      └──> Supabase Auth (when configured)
```

All clients call the API for records and authorization. Browser clients use bearer tokens in session storage; the mobile app stores its bearer token with Expo SecureStore. API URLs are configured with `VITE_API_URL` for web and `EXPO_PUBLIC_API_URL` for mobile. Supabase and Gemini credentials remain server-side in the backend environment.

## Offer scanning

```text
Offer text and/or image → OCR and structured extraction → editable worker draft → worker-confirmed saved record
```

Extracted details remain a suggestion until the worker reviews and confirms them. Missing values remain empty; the score and verification flows do not treat unverified allegations or unresolved disputes as verified evidence.

## Worker protection

Accepted wage terms are kept in immutable agreement versions. Workers request before-travel confirmation against an accepted version; contractors reconfirm the exact terms before departure can be recorded. Workers can submit actual wage, hours, and payment status, then attach evidence to a complaint. Contractors may respond and admins record a review outcome.

## Client status

The three clients are implemented and connected to the backend routes. The worker and contractor surfaces support English and Hindi. The admin console supports English and Hindi. Live Supabase/Gemini-backed use requires valid backend environment configuration; clients contain no service credentials.
