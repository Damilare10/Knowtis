"""
In-process realtime connection registry.

Maintains live WebSocket / SSE subscribers keyed by user id and exposes a
sync-friendly :meth:`ConnectionManager.broadcast_sync` so that synchronous
services (``notification_service``, ``reminder_service``, the scheduler) can
push updates to connected dashboard clients without touching the event loop.

The registry is intentionally process-local: it is shared between the realtime
routes and the notification service so that every DB write can also fan out to
live sockets.
"""
import asyncio
import json
import logging
import threading
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Registry of live realtime clients keyed by user id (as string)."""

    def __init__(self) -> None:
        self._sockets: Dict[str, Set[Any]] = {}
        self._sse_queues: Dict[str, Set[asyncio.Queue]] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        # A plain (sync) lock guards the dict mutations. The critical sections
        # are trivial (set add/discard), and a threading.Lock is loop-agnostic,
        # avoiding asyncio.Lock footguns when the module is imported before a
        # loop exists or used across multiple loops (e.g. in tests).
        self._lock = threading.Lock()

    # -- event loop capture -------------------------------------------------
    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Capture the running event loop.

        Called lazily by the realtime routes on each connection. Always refresh
        to the current running loop: in production (uvicorn) this is one stable
        loop, and in tests it tracks whichever loop is currently alive.
        """
        self._loop = loop

    @property
    def loop(self) -> Optional[asyncio.AbstractEventLoop]:
        return self._loop

    # -- registration -------------------------------------------------------
    async def add_socket(self, user_id: Any, websocket: Any) -> None:
        with self._lock:
            self._sockets.setdefault(str(user_id), set()).add(websocket)

    async def remove_socket(self, user_id: Any, websocket: Any) -> None:
        with self._lock:
            conns = self._sockets.get(str(user_id))
            if conns:
                conns.discard(websocket)
                if not conns:
                    self._sockets.pop(str(user_id), None)

    async def add_sse(self, user_id: Any, queue: asyncio.Queue) -> None:
        with self._lock:
            self._sse_queues.setdefault(str(user_id), set()).add(queue)

    async def remove_sse(self, user_id: Any, queue: asyncio.Queue) -> None:
        with self._lock:
            queues = self._sse_queues.get(str(user_id))
            if queues:
                queues.discard(queue)
                if not queues:
                    self._sse_queues.pop(str(user_id), None)

    def has_listeners(self, user_id: Any) -> bool:
        uid = str(user_id)
        return bool(self._sockets.get(uid) or self._sse_queues.get(uid))

    # -- broadcast ----------------------------------------------------------
    async def broadcast(self, user_id: Any, payload: Dict[str, Any]) -> None:
        """Push a message to every live socket and SSE queue for a user."""
        uid = str(user_id)
        message = json.dumps(payload, default=str)

        dead: list = []
        for ws in list(self._sockets.get(uid, ())):
            try:
                await ws.send_text(message)
            except Exception as exc:
                logger.debug("socket send failed for user %s: %s", uid, exc)
                dead.append(ws)
        if dead:
            with self._lock:
                conns = self._sockets.get(uid)
                if conns:
                    for ws in dead:
                        conns.discard(ws)
                    if not conns:
                        self._sockets.pop(uid, None)

        for queue in list(self._sse_queues.get(uid, ())):
            try:
                queue.put_nowait(message)
            except Exception as exc:
                logger.debug("sse queue put failed for user %s: %s", uid, exc)

    def broadcast_sync(self, user_id: Any, payload: Dict[str, Any]) -> bool:
        """Fire-and-forget broadcast usable from synchronous code.

        Schedules :meth:`broadcast` on the captured event loop (the running
        uvicorn loop). Returns ``True`` when scheduled, ``False`` when there
        are no listeners or no running loop (the message is silently dropped).
        Broadcast errors are logged via a done-callback so synchronous callers
        don't accidentally swallow loop-level exceptions.
        """
        if not self.has_listeners(user_id):
            return False
        loop = self._loop
        if loop is not None and loop.is_running():
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self.broadcast(user_id, payload), loop
                )
            except RuntimeError:
                return False

            def _log_error(fut):
                try:
                    fut.result()
                except Exception as exc:  # noqa: BLE001 - log and continue
                    logger.debug("Realtime broadcast failed for user %s: %s", user_id, exc)

            future.add_done_callback(_log_error)
            return True
        return False


# Shared process-local registry consumed by both the realtime routes and the
# notification service.
manager = ConnectionManager()
