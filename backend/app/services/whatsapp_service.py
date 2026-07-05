"""
WhatsApp Gateway Service

Communicates with the external WhatsApp connector (a Node.js Baileys/Puppeteer
bridge). The connector base URL is configurable via the ``WHATSAPP_CONNECTOR_URL``
environment variable (default ``http://localhost:3001``).

Two access styles are supported:

* **Static helpers** (``get_status``, ``get_groups``, ``join_group``) used by the
  HTTP routes in ``whatsapp_routes.py`` for synchronous invite validation /
  status checks.
* **Async connector methods** (``health``, ``is_bot_member``, ``fetch_messages``,
  ``rejoin_group`` ...) used by the headless listener and recovery services.
  Every async method degrades gracefully when the connector is unreachable,
  returning ``None``/``False`` so callers can apply exponential backoff.
"""
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Service to handle interactions with the external WhatsApp connector."""

    # ------------------------------------------------------------------
    # Connector configuration (instance access mirrors static config)
    # ------------------------------------------------------------------
    @property
    def base_url(self) -> str:
        return settings.whatsapp_connector_url.rstrip("/")

    @property
    def timeout(self) -> float:
        return getattr(settings, "whatsapp_connector_timeout", 30.0)

    @staticmethod
    def _auth_headers() -> Dict[str, str]:
        secret = getattr(settings, "whatsapp_connector_api_secret", "")
        return {"X-Connector-Secret": secret} if secret else {}

    # ------------------------------------------------------------------
    # Static helpers (used by whatsapp_routes.py)
    # ------------------------------------------------------------------
    @staticmethod
    def join_group(invite_link: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Sends a request to the Node.js connector to join a WhatsApp group.
        Optionally forwards an anti-ban ``session_id`` so the connector can
        route the join through a specific worker session.
        Returns the response dictionary: { "success": bool, "group_jid": str, "group_name": str, "message": str }
        """
        url = f"{settings.whatsapp_connector_url}/join"
        try:
            payload: Dict[str, Any] = {"invite_link": invite_link}
            if session_id:
                payload["session_id"] = session_id
            logger.info(
                "Sending join request to WhatsApp connector: %s (session=%s)",
                url, session_id or "default",
            )
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, json=payload, headers=WhatsAppService._auth_headers())

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Successfully joined WhatsApp group: {data.get('group_name')} ({data.get('group_jid')})")
                    return {
                        "success": True,
                        "group_jid": data.get("group_jid"),
                        "group_name": data.get("group_name"),
                        "message": "Successfully joined group."
                    }
                else:
                    error_detail = "Unknown error"
                    try:
                        error_detail = response.json().get("detail", response.text)
                    except Exception:
                        error_detail = response.text

                    logger.error(f"WhatsApp connector join failed ({response.status_code}): {error_detail}")
                    return {
                        "success": False,
                        "message": f"Connector failed: {error_detail}"
                    }
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to WhatsApp connector service at {url}: {e}")
            return {
                "success": False,
                "message": "WhatsApp connector service is currently unreachable."
            }

    @staticmethod
    def get_status() -> Dict[str, Any]:
        """
        Retrieves connection status and QR code from the Node.js connector.
        """
        url = f"{settings.whatsapp_connector_url}/status"
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(url, headers=WhatsAppService._auth_headers())
                if response.status_code == 200:
                    return response.json()
                return {"status": "DISCONNECTED", "message": "Failed to get status from connector."}
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to WhatsApp connector status endpoint: {e}")
            return {"status": "UNREACHABLE", "message": str(e)}

    @staticmethod
    def get_groups() -> list:
        """
        Retrieves the list of active groups monitored by the connector.
        """
        url = f"{settings.whatsapp_connector_url}/groups"
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url, headers=WhatsAppService._auth_headers())
                if response.status_code == 200:
                    return response.json().get("groups", [])
                return []
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to WhatsApp connector groups endpoint: {e}")
            return []

    # ------------------------------------------------------------------
    # Async connector methods (used by listener / recovery services)
    # ------------------------------------------------------------------
    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Perform an HTTP request to the connector, returning None on failure."""
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method, url, json=json, params=params, headers=self._auth_headers()
                )
                response.raise_for_status()
                return response.json()
        except httpx.ConnectError:
            logger.warning(
                "WhatsApp connector unreachable at %s (ConnectError)", url
            )
        except httpx.TimeoutException:
            logger.warning(
                "WhatsApp connector timed out at %s after %.1fs", url, self.timeout
            )
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "WhatsApp connector returned %s for %s",
                exc.response.status_code, url,
            )
        except Exception as exc:
            logger.warning("WhatsApp connector request failed for %s: %s", url, exc)
        return None

    async def health(self) -> Optional[Dict[str, Any]]:
        """Check connector health. None means unreachable."""
        return await self._request("GET", "/health")

    async def is_available(self) -> bool:
        """True when the connector responds to /health."""
        return await self.health() is not None

    async def join_group_async(
        self, invite_link: str, group_jid: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Join (or queue joining) a group via invite link (async)."""
        payload: Dict[str, Any] = {"invite_link": invite_link}
        if group_jid:
            payload["group_jid"] = group_jid
        return await self._request("POST", "/groups/join", json=payload)

    async def rejoin_group(
        self, group_jid: str, invite_link: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Attempt to rejoin a previously linked group."""
        payload: Dict[str, Any] = {"group_jid": group_jid}
        if invite_link:
            payload["invite_link"] = invite_link
        return await self._request("POST", "/groups/rejoin", json=payload)

    async def leave_group(self, group_jid: str) -> Optional[Dict[str, Any]]:
        """Leave a group via the connector."""
        return await self._request(
            "POST", "/groups/leave", json={"group_jid": group_jid}
        )

    async def get_group_metadata(
        self, group_jid: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch group metadata including participants and bot membership."""
        return await self._request("GET", f"/groups/{group_jid}")

    async def is_bot_member(self, group_jid: str) -> Optional[bool]:
        """
        Return True/False for bot membership, or None when the connector is
        unreachable (so callers can distinguish 'removed' from 'unknown').
        """
        meta = await self.get_group_metadata(group_jid)
        if meta is None:
            return None
        if "is_bot_member" in meta:
            return bool(meta.get("is_bot_member"))
        participants = meta.get("participants") or []
        bot_jid = meta.get("bot_jid")
        if bot_jid:
            return any(p.get("jid") == bot_jid for p in participants)
        return None

    async def fetch_messages(
        self,
        group_jid: str,
        since: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch messages newer than `since` (a message id or ISO timestamp).
        Returns a list of message dicts, or None when the connector is down.
        """
        params: Dict[str, Any] = {}
        if since:
            params["since"] = since
        if limit:
            params["limit"] = limit
        result = await self._request(
            "GET", f"/groups/{group_jid}/messages", params=params
        )
        if result is None:
            return None
        if isinstance(result, list):
            return result
        return result.get("messages") or []
