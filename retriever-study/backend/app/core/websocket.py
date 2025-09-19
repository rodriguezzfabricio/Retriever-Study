"""In-memory WebSocket connection management for development."""

import json
from typing import Any, Dict, Set

from fastapi import WebSocket

from app.core.auth import AuthError, verify_token
from app.data.local_db import db


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
        await self._send_chat_history(websocket, group_id, user_id)
        
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

    async def _send_chat_history(self, websocket: WebSocket, group_id: str, user_id: str) -> None:
        """Send recent chat history to a newly connected user."""
        try:
            # Fetch recent messages (last 50 messages)
            messages_data = db.get_messages_by_group(group_id, limit=50)
            
            # Enrich messages with sender names
            enriched_messages = []
            for msg in messages_data:
                try:
                    # Try to resolve sender name
                    sender_name = None
                    user = db.get_user_by_google_id(msg.get("senderId"))
                    if not user and msg.get("senderId"):
                        user = db.get_user_by_id(msg.get("senderId"))
                    if user:
                        sender_name = user.get("name")
                except Exception:
                    sender_name = None
                
                enriched_msg = {
                    "type": "history_message",
                    "messageId": msg.get("messageId"),
                    "groupId": msg.get("groupId"),
                    "senderId": msg.get("senderId"),
                    "senderName": sender_name or "Member",
                    "content": msg.get("content"),
                    "createdAt": msg.get("createdAt"),
                    "toxicityScore": msg.get("toxicityScore", 0.0)
                }
                enriched_messages.append(enriched_msg)
            
            # Send history as a batch
            if enriched_messages:
                history_payload = {
                    "type": "chat_history",
                    "messages": enriched_messages,
                    "groupId": group_id
                }
                await websocket.send_text(json.dumps(history_payload))
                
        except Exception as e:
            # Log error but don't fail the connection
            # In production, use proper logging
            print(f"Error sending chat history to user {user_id} in group {group_id}: {e}")
            
            # Send error notification to client
            try:
                error_payload = {
                    "type": "error",
                    "error": "Failed to load chat history",
                    "message": "Some messages may not be visible"
                }
                await websocket.send_text(json.dumps(error_payload))
            except Exception:
                pass  # Don't fail if we can't send error message

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
