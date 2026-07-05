"""
LLM service: conversational layer over the Groq chat completions API.

Uses ``httpx`` for async HTTP so no ``groq`` SDK import is required at
module load time (keeping ``import app.main`` dependency-light). If the
``GROQ_API_KEY`` is absent, ``LLMService`` reports unavailable and the AI
agent gracefully falls back to the deterministic engine.
"""

import json
import logging
from typing import AsyncIterator, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """Thin async wrapper around Groq's OpenAI-compatible chat API."""

    @staticmethod
    def is_available() -> bool:
        return settings.llm_enabled

    @staticmethod
    def _headers() -> dict:
        return {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _model_for(tier: str) -> str:
        # Both tiers use the full Groq model. Free-tier usage is capped by the
        # 10k received-token quota enforced in ai_routes.enforce_ai_token_limit.
        return settings.ai_premium_model

    @staticmethod
    async def chat(
        messages: List[dict],
        tier: str = "premium",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Return a complete (non-streamed) chat completion."""
        if not LLMService.is_available():
            raise RuntimeError("LLM service is not configured (GROQ_API_KEY missing)")

        payload = {
            "model": LLMService._model_for(tier),
            "messages": messages,
            "temperature": settings.ai_temperature
            if temperature is None
            else temperature,
            "max_tokens": settings.ai_max_tokens if max_tokens is None else max_tokens,
            "stream": False,
        }

        async with httpx.AsyncClient(
            timeout=settings.ai_request_timeout
        ) as client:
            response = await client.post(
                f"{settings.groq_base_url}/chat/completions",
                headers=LLMService._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    @staticmethod
    async def stream_chat(
        messages: List[dict],
        tier: str = "premium",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """Yield token deltas from a streamed chat completion."""
        if not LLMService.is_available():
            raise RuntimeError("LLM service is not configured (GROQ_API_KEY missing)")

        payload = {
            "model": LLMService._model_for(tier),
            "messages": messages,
            "temperature": settings.ai_temperature
            if temperature is None
            else temperature,
            "max_tokens": settings.ai_max_tokens if max_tokens is None else max_tokens,
            "stream": True,
        }

        async with httpx.AsyncClient(
            timeout=settings.ai_request_timeout
        ) as client:
            async with client.stream(
                "POST",
                f"{settings.groq_base_url}/chat/completions",
                headers=LLMService._headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    token = LLMService._parse_stream_line(line)
                    if token:
                        yield token

    @staticmethod
    def _parse_stream_line(line: str) -> Optional[str]:
        line = line.strip()
        if not line or not line.startswith("data:"):
            return None
        data = line[len("data:"):].strip()
        if data == "[DONE]":
            return None
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            return None
        choices = chunk.get("choices") or []
        if not choices:
            return None
        return choices[0].get("delta", {}).get("content")
