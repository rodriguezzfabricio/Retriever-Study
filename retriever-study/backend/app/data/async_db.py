"""Async database placeholders for development mode.

These stubs allow the FastAPI application to import async database helpers
without requiring the production Postgres implementation. When running in
SQLite development mode, the sync database defined in ``local_db`` is used
instead.
"""

from typing import Optional, Any

async_db: Optional[Any] = None
user_repo: Optional[Any] = None
group_repo: Optional[Any] = None


async def initialize_async_database(database_url: str) -> None:  # pragma: no cover
    """Placeholder initializer for async database infrastructure."""
    return None


async def close_async_database() -> None:  # pragma: no cover
    """Placeholder shutdown hook for async database infrastructure."""
    return None
