"""Monitoring helpers for local development."""

from contextlib import contextmanager
from typing import Any, Dict


class PerformanceTracker:
    def get_performance_summary(self, window_minutes: int = 5) -> Dict[str, Any]:
        return {
            "window_minutes": window_minutes,
            "requests": 0,
            "average_latency_ms": 0.0,
        }


performance_tracker = PerformanceTracker()


class PoolMonitor:
    async def start_monitoring(self, _async_db: Any) -> None:  # pragma: no cover
        return None

    async def stop_monitoring(self) -> None:  # pragma: no cover
        return None


pool_monitor = PoolMonitor()


class HealthChecker:
    async def get_system_health(self, async_db: Any, ai_service: Any) -> Dict[str, Any]:
        return {
            "database": "healthy" if async_db else "disabled",
            "ai_service": "healthy" if ai_service else "disabled",
        }


health_checker = HealthChecker()


def get_performance_middleware():  # pragma: no cover
    async def middleware(request, call_next):  # type: ignore[override]
        response = await call_next(request)
        return response

    return middleware


@contextmanager
def get_ai_operation_monitor(operation_name: str):  # pragma: no cover
    yield {"operation": operation_name}
