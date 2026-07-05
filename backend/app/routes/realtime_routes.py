"""
Realtime feed routes.

Exposes a WebSocket endpoint at ``/ws/feed`` and an SSE fallback at
``/feed/stream``. Both authenticate through the existing ``get_current_user``
token resolver — the token is accepted as a ``token`` query parameter so
that WebSocket / EventSource clients (which cannot set custom headers) can
authenticate.

Live subscribers are tracked in ``app.realtime.manager`` keyed by user id; the
notification service fans out to these subscribers on every DB write.
"""
import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.realtime import manager
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Realtime Feed"])


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


async def _authenticate_ws(websocket: WebSocket, token: str) -> User | None:
    """Resolve the authenticated user for a WebSocket handshake.

    FastAPI does not invoke ``Depends`` for ``WebSocket`` handlers, so the auth
    step is performed manually here. Returns ``None`` when the token is missing
    or invalid (the caller closes the socket with a policy-violation code).
    """
    if not token:
        return None
    # Reuse the same resolver the HTTP routes use; it opens a short-lived
    # session to look up the user.
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        return AuthService.get_user_from_token(token, db)
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# WebSocket feed
# --------------------------------------------------------------------------- #
@router.websocket("/ws/feed")
async def feed_socket(
    websocket: WebSocket,
    token: str = Query(default=None),
):
    """Authenticated WebSocket realtime feed.

    The token is supplied as a ``token`` query parameter (WebSockets cannot
    set custom headers). Connections with an invalid or missing token are
    rejected with WebSocket close code 1008 (policy violation).
    """
    user = await _authenticate_ws(websocket, token)
    if user is None or not user.is_active:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="auth_failed")
        return

    manager.set_loop(asyncio.get_running_loop())
    await websocket.accept()
    await manager.add_socket(user.id, websocket)
    logger.info("WS feed client connected: user=%s", user.id)
    try:
        while True:
            data = await websocket.receive_text()
            # Lightweight ping/pong keep-alive; ignore other client messages.
            if data:
                try:
                    msg = json.loads(data)
                    if isinstance(msg, dict) and msg.get("type") == "ping":
                        await websocket.send_text(json.dumps({"type": "pong", "ts": _now()}))
                except (ValueError, TypeError):
                    pass
    except WebSocketDisconnect:
        logger.info("WS feed client disconnected: user=%s", user.id)
    finally:
        await manager.remove_socket(user.id, websocket)


# --------------------------------------------------------------------------- #
# SSE fallback feed
# --------------------------------------------------------------------------- #
@router.get("/feed/stream")
async def feed_stream(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),  # noqa: ARG001 (kept for dependency parity)
):
    """Authenticated SSE fallback for clients that cannot use WebSockets."""
    manager.set_loop(asyncio.get_running_loop())

    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue()
        await manager.add_sse(user.id, queue)
        yield _sse(
            {
                "type": "connected",
                "user_id": str(user.id),
                "ts": _now(),
            }
        )
        try:
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {message}\n\n"
                except asyncio.TimeoutError:
                    # heartbeat keeps proxies from closing the connection
                    yield ": ping\n\n"
        finally:
            await manager.remove_sse(user.id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"
