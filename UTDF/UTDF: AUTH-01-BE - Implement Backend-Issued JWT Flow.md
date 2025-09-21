# UTDF: AUTH-01-BE - Implement Backend-Issued JWT Flow

## 1. Agent Assignment

- **Primary Agent:** `Backend_Engineer`
- **Reviewing Agent(s):** `Security_Auditor`, `QA_Engineer`

## 2. Task Description

The current system improperly uses a Google-issued token for session management. Create a new API endpoint that accepts a Google ID token, validates it, creates or updates a user in our database, and returns a secure, backend-issued JWT that will be used for all subsequent API requests.

## 3. Acceptance Criteria

- [ ] Create a new endpoint at `POST /auth/google/callback`.
- [ ] The endpoint should accept a JSON body with a single field: `google_token`.
- [ ] The endpoint must securely verify the `google_token` with Google's servers.
- [ ] Upon successful verification, it must use the user's Google ID (`sub`) to find an existing user or create a new one via the `create_or_update_oauth_user` function in `local_db.py`.
- [ ] A new, backend-signed JWT must be generated. This JWT's payload must contain the internal `userId` and the user's `email`.
- [ ] The endpoint must return a JSON response containing the `access_token`, `refresh_token`, and user profile information, matching the existing `TokenResponse` Pydantic model in `main.py`.

## 4. Relevant Files & Context

- `backend/app/main.py`
- `backend/app/core/auth.py`
- `backend/app/data/local_db.py`

## 5. Required Output Format

- **Format:** Provide the complete, updated contents of `backend/app/main.py` and `backend/app/core/auth.py`.
- **Delimiters:** Use markdown code blocks with file paths.

**UTDF `AUTH-01-FE`:**
