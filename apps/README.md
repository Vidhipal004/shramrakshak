# ShramRakshak – JobTrust AI

A worker-first marketplace and protection platform. The backend is in `backend/`; the three connected clients are:

- `apps/worker-mobile`: Expo React Native worker app (English/Hindi).
- `apps/contractor-web`: Vite contractor workspace (English/Hindi).
- `apps/admin-web`: Vite admin console (English/Hindi).
- `apps/contractor-web-ui`: preserved starter project from the original workspace.

## Run locally

Run the FastAPI backend from `backend/` following its `.env.example` and `README.md`. Keep credentials in environment files that are not committed. Configure client API URLs:

- Copy `apps/contractor-web/.env.example` to `.env` in that app; default API is `http://127.0.0.1:8000`.
- Copy `apps/admin-web/.env.example` to `.env` in that app; default API is `http://127.0.0.1:8000`.
- Copy `apps/worker-mobile/.env.example` to `.env` in that app. For a physical phone, set `EXPO_PUBLIC_API_URL` to the development computer's LAN address; Android emulator users typically use `http://10.0.2.2:8000`.

Then run `npm install` and `npm run dev` in each web app. For mobile, run `npm install` then `npx expo start`. Admin accounts must be provisioned through the backend; public registration is limited to workers and contractors.

## Connected workflows

Worker: account registration/login, profile, job search/filtering, application tracking, contractor JobTrust reports, offer OCR/AI extraction with editable fields, saved offers, versioned wage agreements, travel confirmation, departure, actual wage/hour/payment reports, complaint submission and evidence photo upload.

Contractor: account registration/login, profile, job listing create/edit/cancel, application review, wage agreement proposals/version updates, pre-travel reconfirmation, complaint responses, and JobTrust report.

Admin: restricted login, contractor directory and verification decisions, evidence-based JobTrust report, complaint evidence downloads, review states and recorded resolutions.
