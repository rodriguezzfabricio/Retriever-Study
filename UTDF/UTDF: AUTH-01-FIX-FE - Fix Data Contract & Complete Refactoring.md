# **UTDF: AUTH-01-FIX-FE - Fix Data Contract & Complete Refactoring**

## **1. Agent Assignment**

- **Primary Agent:** `Frontend_Engineer`
- **Reviewing Agent(s):** `QA_Engineer`

## **2. Task Description**

The frontend has two issues: (1) The original UTDF instruction to rename `googleLogin` to `exchangeGoogleToken` was not followed - both functions exist, and (2) there's a data contract mismatch where we send `id_token` but backend expects consistency. Complete the refactoring and ensure data contract alignment.

## **3. Acceptance Criteria**

- [ ] **REMOVE** the old `googleLogin` function completely from `api.js`
- [ ] **VERIFY** `exchangeGoogleToken` sends `{ id_token: idToken }` in request body
- [ ] **UPDATE** `Login.js` to use ONLY `exchangeGoogleToken` (remove any `googleLogin` references)
- [ ] **ENSURE** the `AuthContext.js` login function properly stores the backend response
- [ ] **VERIFY** `apiRequest` function correctly reads `access_token` from stored auth data
- [ ] **TEST** that error handling works for authentication failures

## **4. Relevant Files & Context**

- `frontend/src/services/api.js` (contains both `googleLogin` AND `exchangeGoogleToken`)
- `frontend/src/pages/Login.js` (should call `exchangeGoogleToken` only)
- `frontend/src/context/AuthContext.js` (handles storing auth response)
- **Backend endpoint expects:** `POST /auth/google/callback` with `{ id_token: "..." }`

## **5. Required Output Format**

- **Format:** Provide the complete, updated contents of all three modified files
- **Delimiters:** Use markdown code blocks with file paths
- **Show:** Clearly indicate which functions/lines were removed
