"""In-memory WebSocket connection management for development."""

import json
from typing import Any, Dict

from fastapi import WebSocket

from app.core.auth import AuthError, verify_token


class ConnectionManager:
    def __init__(self) -> None:
        self._groups: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        group_id: str,
        user_id: str,
        user_data: Dict[str, Any],
    ) -> bool:
        await websocket.accept()
        self._groups.setdefault(group_id, {})[user_id] = websocket
        return True

    async def disconnect(self, group_id: str, user_id: str) -> None:
        group_connections = self._groups.get(group_id)
        if not group_connections:
            return

        websocket = group_connections.pop(user_id, None)
        if websocket:
            try:
                await websocket.close()
            except Exception:  # noqa: BLE001
                pass

        if not group_connections:
            self._groups.pop(group_id, None)

    async def send_message_to_group(self, group_id: str, payload: Dict[str, Any], sender_id: str) -> None:
        connections = self._groups.get(group_id, {})
        message = json.dumps({**payload, "senderId": sender_id})

        for connection in list(connections.values()):
            try:
                await connection.send_text(message)
            except Exception:  # noqa: BLE001
                pass

    def get_group_stats(self, group_id: str) -> Dict[str, Any]:
        connections = self._groups.get(group_id, {})
        return {
            "active_connections": len(connections),
        }


connection_manager = ConnectionManager()


async def authenticate_websocket_user(websocket: WebSocket, token: str | None) -> Dict[str, Any] | None:
    if not token:
        await websocket.close(code=4401)
        return None

    try:
        payload = verify_token(token)
    except AuthError:
        await websocket.close(code=4403)
        return None

    user_id = (
        payload.get("sub")
        or payload.get("user_id")
        or payload.get("userId")
        or payload.get("id")
        or "anonymous"
    )

    return {
        "user_id": user_id,
        "email": payload.get("email"),
        "scopes": payload.get("scopes", []),
        "raw": payload,
    }
