# Unified Task Definition File (UTDF)

**ID:** `BE-01-DB-MIGRATION`

**Title:** Complete Async DB Migration

**Assignee:** `Backend_Engineer`

**Status:** `Not Started`

---

## 📝 Description

The backend application is currently in a transitional state, supporting both a legacy synchronous SQLite database and the new asynchronous PostgreSQL database. This has resulted in technical debt, including conditional logic and redundant data access patterns.

The objective of this task is to **fully migrate the application to the asynchronous PostgreSQL database** and remove all legacy synchronous database code. This will stabilize the backend, improve performance, and prepare the application for a production environment.

---

## Relevant Files

- `backend/app/main.py`
- `backend/app/data/async_db.py`
- `backend/app/data/local_db.py`
- `backend/app/core/environment.py`

---

## ✅ Acceptance Criteria

1. **Remove Synchronous DB Logic:**

   - All code related to the synchronous SQLite database (`local_db.py`) must be removed from `main.py`.
   - The `async_initialized` flag and all associated conditional logic (`if async_initialized: ... else: ...`) must be eliminated.

2. **Standardize on Async Repositories:**

   - All database operations within `main.py` must be performed using the asynchronous repository patterns (`user_repo` and `group_repo`) provided by `async_db.py`.
   - Direct calls to the legacy `db` object must be replaced with their `user_repo` or `group_repo` equivalents.

3. **Update Environment Configuration:**

   - The `ASYNC_DB_ENABLED` environment variable check in `environment.py` should be removed, as the async database will now be the default and only option.

4. **Ensure Full API Functionality:**

   - After the refactoring, all existing API endpoints must be fully functional using only the asynchronous database connection.
   - The application must start and run without errors.

---
