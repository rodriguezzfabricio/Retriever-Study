"""In-memory WebSocket connection management for development."""

import json
from typing import Any, Dict, Set

from fastapi import WebSocket

from app.core.auth import AuthError, verify_token



class ConnectionManager:
    def __init__(self) -> None:
        # Mapping: group_id -> { user_id -> set(WebSocket) }
        # Rationale: allow multiple connections per user (multi-tabs/devices)
        # and avoid one connection overwriting another.
        self._groups: Dict[str, Dict[str, Set[WebSocket]]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        group_id: str,
        user_id: str,
        user_data: Dict[str, Any],
    ) -> bool:
        await websocket.accept()
        self._groups.setdefault(group_id, {}).setdefault(user_id, set()).add(websocket)
        
        # Send chat history to newly connected user

        
        return True

    async def disconnect(self, group_id: str, user_id: str) -> None:
        group_connections = self._groups.get(group_id)
        if not group_connections:
            return
        # Close and remove all sockets for this user in this group
        sockets = group_connections.pop(user_id, set())
        for ws in list(sockets):
            try:
                await ws.close()
            except Exception:  # noqa: BLE001
                pass
        if not group_connections:
            self._groups.pop(group_id, None)

    async def send_message_to_group(self, group_id: str, payload: Dict[str, Any], sender_id: str) -> None:
        connections = self._groups.get(group_id, {})
        # Don't override senderId if it's already in the payload (for enriched messages)
        if "senderId" not in payload:
            payload["senderId"] = sender_id
        message = json.dumps(payload)
        for socket_set in list(connections.values()):
            for connection in list(socket_set):
                try:
                    await connection.send_text(message)
                except Exception:  # noqa: BLE001
                    pass



    def get_group_stats(self, group_id: str) -> Dict[str, Any]:
        connections = self._groups.get(group_id, {})
        # Count total websocket endpoints across all users
        count = sum(len(socks) for socks in connections.values())
        return {"active_connections": count}


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
