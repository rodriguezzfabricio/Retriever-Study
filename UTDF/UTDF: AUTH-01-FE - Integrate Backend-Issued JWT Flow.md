# UTDF: AUTH-01-FE - Integrate Backend-Issued JWT Flow

## 1. Agent Assignment

- **Primary Agent:** `Frontend_Engineer`
- **Reviewing Agent(s):** `QA_Engineer`

## 2. Task Description

Modify the frontend login process to exchange the Google token for a backend-issued JWT. The application must store and use this new backend token for all authenticated API calls.

## 3. Acceptance Criteria

- [ ] In `frontend/src/services/api.js`, rename the existing `googleLogin` function to `exchangeGoogleToken`.
- [ ] The `exchangeGoogleToken` function must now make a `POST` request to the `/auth/google/callback` endpoint, sending the Google credential.
- [ ] In `frontend/src/pages/Login.js`, update the `handleLoginSuccess` function to call the new `exchangeGoogleToken` service function.
- [ ] In `frontend/src/context/AuthContext.js`, the `login` function must now store the entire response object from the backend (which includes the `access_token`, `refresh_token`, and `user` object) in `localStorage`.
- [ ] The `apiRequest` function in `api.js` must be updated to read the `access_token` from this stored object.

## 4. Relevant Files & Context

- `frontend/src/pages/Login.js`
- `frontend/src/services/api.js`
- `frontend/src/context/AuthContext.js`

## 5. Required Output Format

- **Format:** Provide the complete, updated contents of all three modified JavaScript files.
- **Delimiters:** Use markdown code blocks with file paths.

**Step 2: Sequential Handoff for Security Review**

After the `Backend_Engineer` returns the modified Python files, the Orchestrator creates a new UTDF for the `Security_Auditor`.
