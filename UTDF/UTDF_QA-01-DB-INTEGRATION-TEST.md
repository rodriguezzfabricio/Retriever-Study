# Unified Task Definition File (UTDF)

**ID:** `QA-01-DB-INTEGRATION-TEST`

**Title:** Create Integration Tests for Async Database

**Assignee:** `QA_Engineer`

**Status:** `Not Started`

---

## 📝 Description

The `Backend_Engineer` has successfully completed the migration from a hybrid database system to a fully asynchronous PostgreSQL database. All synchronous code and the SQLite database have been removed.

The primary objective of this task is to develop a comprehensive suite of integration tests that verify the correctness and reliability of all API endpoints that interact with the database. This will ensure the migration was successful and prevent future regressions.

---

## Relevant Files

- `backend/app/main.py`
- `backend/app/data/async_db.py`
- `backend/app/tests/`

---

## ✅ Acceptance Criteria

1. **Create New Test File:**

   - A new test file, `backend/app/tests/test_db_integration.py`, must be created to house the new integration tests.

2. **Comprehensive Endpoint Coverage:**

   - Write integration tests for all API endpoints in `main.py` that perform CRUD (Create, Read, Update, Delete) operations.
   - This includes, but is not limited to:
     - User profile management (`/users/me`)
     - Group creation and management (`/groups/`, `/groups/{group_id}`)
     - User-to-group associations.

3. **Data Integrity Validation:**

   - Tests must assert that data is correctly persisted in the database after creation and updates.
   - Tests must verify that data is correctly retrieved from the database.
   - Tests must confirm that data is correctly deleted or associations are removed as expected.

4. **Successful Test Execution:**

   - All new integration tests must pass successfully in the local test environment.
   - The existing test suite must also continue to pass without any new failures.

---
