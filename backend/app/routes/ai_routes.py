"""
AI Catch-Up Agent API routes.

POST /api/v1/ai/query
  - Both free and premium tiers use the full Groq LLM for conversational
    answers grounded in the deterministic retrieval context.
  - Free tier is capped at 10,000 received tokens (enforced per user);
    premium is unlimited. SSE streaming is supported.
A base slowapi guard protects the endpoint.
"""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_user_tier, is_premium_user
from app.models import ChatMessage, User
from app.rate_limit import enforce_ai_quota, limiter
from app.schemas import (
    AIQueryRequest, AIQueryResponse, AICitation, AIRetrievalInfo,
    ChatClearResponse, ChatHistoryResponse, ChatMessageResponse, ChatSendRequest,
)
from app.services.ai_agent_service import AIAgentService, RetrievalContext
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ai", tags=["AI Catch-Up Agent"])


def _build_messages(ctx: RetrievalContext):
    return [
        {"role": "system", "content": AIAgentService.build_system_prompt(ctx)},
        {"role": "user", "content": ctx.query},
    ]


def enforce_ai_token_limit(user: User) -> None:
    """Raise 403 if the user is on the free tier and has consumed 10,000 received tokens."""
    if not user.is_premium and user.ai_tokens_received >= 10000:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Free tier token limit of 10,000 received tokens reached. "
                "Upgrade to Pro for unlimited usage."
            ),
        )


@router.post("/query", response_model=AIQueryResponse)
@limiter.limit("120/minute")
async def query_ai(
    payload: AIQueryRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Answer a catch-up query via Groq for both tiers (free token-capped)."""
    try:
        enforce_ai_quota(user)
        enforce_ai_token_limit(user)
    except HTTPException:
        raise

    tier = get_user_tier(user)
    ctx = AIAgentService.retrieve(
        payload.query, user.id, db, course_code=payload.course_code
    )

    use_llm = LLMService.is_available()

    if use_llm and payload.stream:
        return _stream_conversational(ctx, tier, user, db)

    if use_llm:
        try:
            result = await AIAgentService.answer_premium(ctx, tier=tier)
            mode = "conversational"
            
            # Count received tokens
            answer_text = result["answer"]
            tokens_received = max(1, len(answer_text) // 4)
            user.ai_tokens_received += tokens_received
            db.commit()
        except Exception as exc:
            logger.error(f"LLM call failed, falling back to deterministic: {exc}")
            result = AIAgentService.compose_deterministic(ctx)
            mode = "deterministic"
    else:
        result = AIAgentService.compose_deterministic(ctx)
        mode = "deterministic"

    return AIQueryResponse(
        query=payload.query,
        answer=result["answer"],
        tier=tier,
        mode=mode,
        citations=[AICitation(**c) for c in result["citations"]],
        retrieval=AIRetrievalInfo(**result["retrieval"]),
    )


def _stream_conversational(ctx: RetrievalContext, tier: str, user: User, db: Session) -> StreamingResponse:
    async def event_stream():
        citations = AIAgentService._citations(ctx.events)
        retrieval = AIAgentService._retrieval_info(ctx)

        yield f"data: {json.dumps({'type': 'start', 'tier': tier, 'mode': 'conversational'})}\n\n"

        total_response_chars = 0
        try:
            async for token in LLMService.stream_chat(
                _build_messages(ctx), tier=tier
            ):
                total_response_chars += len(token)
                yield f"data: {json.dumps({'type': 'delta', 'content': token})}\n\n"
            
            # Count received tokens
            tokens_received = max(1, total_response_chars // 4)
            user.ai_tokens_received += tokens_received
            db.commit()
        except Exception as exc:
            logger.error(f"Streaming LLM failed: {exc}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'citations': _jsonable(citations), 'retrieval': retrieval})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _jsonable(citations):
    safe = []
    for c in citations:
        safe.append(
            {
                "event_id": str(c["event_id"]),
                "title": c["title"],
                "course_code": c["course_code"],
                "date_time": c["date_time"].isoformat() if c["date_time"] else None,
                "event_type": c["event_type"],
                "venue": c["venue"],
            }
        )
    return safe


# ── Persistent AI chat ────────────────────────────────────────────────────────
@router.post("/chat", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("120/minute")
async def send_chat_message(
    payload: ChatSendRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a user message and receive an AI reply (persisted)."""
    try:
        enforce_ai_quota(user)
        enforce_ai_token_limit(user)
    except HTTPException:
        raise

    user_msg = ChatMessage(
        user_id=user.id, role="user", content=payload.message, day=datetime.utcnow().date()
    )
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    tier = get_user_tier(user)
    ctx = AIAgentService.retrieve(payload.message, user.id, db)
    use_llm = LLMService.is_available()

    if use_llm:
        try:
            result = await AIAgentService.answer_premium(ctx, tier=tier)
            answer = result["answer"]
            
            # Count received tokens
            tokens_received = max(1, len(answer) // 4)
            user.ai_tokens_received += tokens_received
            db.commit()
        except Exception as exc:
            logger.error(f"LLM call failed, falling back to deterministic: {exc}")
            answer = AIAgentService.compose_deterministic(ctx)["answer"]
    else:
        answer = AIAgentService.compose_deterministic(ctx)["answer"]

    reply = ChatMessage(
        user_id=user.id, role="assistant", content=answer, day=datetime.utcnow().date()
    )
    db.add(reply)
    db.commit()
    db.refresh(reply)

    return ChatMessageResponse(
        id=str(reply.id), role=reply.role, content=reply.content,
        day=reply.day.isoformat() if reply.day else None,
        created_at=reply.created_at.isoformat() if reply.created_at else None,
    )


@router.get("/chat/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    limit: int = 200,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch the user's persisted AI conversation, oldest first."""
    msgs = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at.asc())
        .limit(min(limit, 500))
        .all()
    )
    return ChatHistoryResponse(
        messages=[
            ChatMessageResponse(
                id=str(m.id), role=m.role, content=m.content,
                day=m.day.isoformat() if m.day else None,
                created_at=m.created_at.isoformat() if m.created_at else None,
            )
            for m in msgs
        ]
    )


@router.delete("/chat", response_model=ChatClearResponse)
async def clear_chat(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Clear the entire AI chat history for the current user."""
    deleted = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user.id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return ChatClearResponse(deleted=deleted)
