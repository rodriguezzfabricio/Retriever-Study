"""Async AI service stubs for local development."""

from typing import Any, Dict, List, Optional


class _AsyncAIService:
    async def generate_embedding_async(self, text: str) -> List[float]:
        return []

    async def health_check(self) -> Dict[str, Any]:
        return {"status": "disabled"}


ai_service: Optional[_AsyncAIService] = None


def initialize_ai_service(max_workers: int = 4) -> None:  # pragma: no cover
    global ai_service
    ai_service = _AsyncAIService()


async def cleanup_ai_service() -> None:  # pragma: no cover
    global ai_service
    ai_service = None
