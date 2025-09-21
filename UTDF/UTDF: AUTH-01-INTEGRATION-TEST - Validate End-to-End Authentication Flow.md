# **UTDF: AUTH-01-INTEGRATION-TEST - Validate End-to-End Authentication Flow**

## **1. Agent Assignment**

- **Primary Agent:** `QA_Engineer`
- **Supporting Agent(s):** `Frontend_Engineer`, `Backend_Engineer`

## **2. Task Description**

Now that the critical authentication bugs have been fixed, we need to validate that the complete Google OAuth → Backend JWT → Protected API flow works end-to-end. This is a **blocking task** - if authentication still fails, we cannot proceed with user-facing features.

## **3. Acceptance Criteria**

- [ ] **VERIFY** Google OAuth login completes successfully in browser
- [ ] **CONFIRM** backend receives `id_token` and validates it with Google
- [ ] **VALIDATE** backend returns properly formatted `TokenResponse` with `access_token` and `user` data
- [ ] **TEST** frontend stores auth data and includes JWT in subsequent API calls
- [ ] **VERIFY** protected endpoints (like `/auth/me`, `/recommendations`) work with the new JWT
- [ ] **CONFIRM** token refresh flow works if implemented
- [ ] **TEST** logout clears stored tokens and redirects properly
- [ ] **DOCUMENT** any remaining authentication issues with specific error messages

## **4. Test Scenarios to Execute**

### **Scenario 1: Happy Path Login**

1. User clicks "LOG IN" button
2. Google OAuth popup appears and user authenticates
3. Frontend receives Google credential
4. Frontend calls `/auth/google/callback` with `id_token`
5. Backend validates token and returns our JWT
6. Frontend stores tokens and shows "HELLO, [Name]" in header
7. User can access protected pages like `/profile`

### **Scenario 2: Protected Route Access**

1. Authenticated user visits `/recommendations`
2. Frontend includes JWT in Authorization header
3. Backend validates JWT and returns personalized data
4. Page renders successfully

### **Scenario 3: Error Handling**

1. Try invalid/expired Google token
2. Try accessing protected route without JWT
3. Verify appropriate error messages shown to user

## **5. Required Output Format**

- **Format:** Test execution report with pass/fail status for each scenario
- **Structure:**
