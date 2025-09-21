# **UTDF: AUTH-01-FIX-BE - Fix Backend Data Contract & Remove Duplication**

## **1. Agent Assignment**

- **Primary Agent:** `Backend_Engineer`
- **Reviewing Agent(s):** `Security_Auditor`

## **2. Task Description**

The current backend implementation has two critical flaws: (1) a data contract mismatch with the frontend that prevents authentication from working, and (2) unnecessary code duplication with two nearly identical endpoints. Fix both issues by standardizing on a single, properly-named endpoint that matches frontend expectations.

## **3. Acceptance Criteria**

- [ ] **REMOVE** the duplicate `/auth/google_login` endpoint completely - delete all related code
- [ ] **MODIFY** the `/auth/google/callback` endpoint to accept `id_token` field (not `google_token`)
- [ ] **UPDATE** the `GoogleCallbackRequest` model to use `id_token: str` to match frontend
- [ ] **VERIFY** the endpoint properly validates the Google ID token using `verify_google_id_token()`
- [ ] **ENSURE** the response format matches the existing `TokenResponse` model exactly
- [ ] **MAINTAIN** all existing security features (rate limiting, input validation, error handling)

## **4. Relevant Files & Context**

- `backend/app/main.py` (lines 480-650 contain the problematic duplicate endpoints)
- `backend/app/core/auth.py` (contains `verify_google_id_token` function)
- `frontend/src/services/api.js` (shows frontend sends `{ id_token: idToken }`)

## **5. Required Output Format**

- **Format:** Provide the complete, updated contents of `backend/app/main.py` with the fixes applied
- **Delimiters:** Use markdown code blocks with file paths
- **Critical:** Show EXACTLY which lines were removed and modified
