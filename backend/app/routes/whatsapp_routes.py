"""
API Routes - WhatsApp Groups
Group management and webhook listener for external WhatsApp connector.
"""
import logging
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Literal, Union, Annotated
import hmac

from app.config import settings
from app.database import get_db
from app.models import User, WhatsAppGroup, CoverageState
from app.schemas import WhatsAppGroupResponse, JoinGroupRequest
from app.dependencies import get_current_user
from app.services.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/whatsapp", tags=["WhatsApp"])

FREE_TIER_GROUP_LIMIT = 2

class MessageWebhookData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message_id: str = Field(..., min_length=1, max_length=255)
    sender_jid: Optional[str] = Field(default=None, max_length=255)
    sender_name: Optional[str] = Field(default=None, max_length=255)
    message_text: str = Field(..., min_length=1, max_length=5000)
    group_jid: str = Field(..., pattern=r"^[^\s@]+@g\.us$", max_length=255)
    timestamp: Optional[Union[int, float, str]] = None
    mentioned_jids: list[str] = Field(default_factory=list, max_length=100)
    is_bot_mentioned: bool = False
    mention_all: bool = False


class GroupJoinedWebhookData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    invite_code: str = Field(..., min_length=1, max_length=255)
    group_jid: str = Field(..., pattern=r"^[^\s@]+@g\.us$", max_length=255)
    group_name: str = Field(..., min_length=1, max_length=255)
    group_description: Optional[str] = Field(default=None, max_length=2000)


class GroupJidWebhookData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    group_jid: str = Field(..., pattern=r"^[^\s@]+@g\.us$", max_length=255)


class ConnectionStatusWebhookData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: str = Field(..., max_length=50)


class MessageWebhookPayload(BaseModel):
    event: Literal["message"]
    data: MessageWebhookData


class GroupJoinedWebhookPayload(BaseModel):
    event: Literal["group_joined"]
    data: GroupJoinedWebhookData


class BotRemovedWebhookPayload(BaseModel):
    event: Literal["bot_removed"]
    data: GroupJidWebhookData


class ConnectionStatusWebhookPayload(BaseModel):
    event: Literal["connection_status"]
    data: ConnectionStatusWebhookData


WebhookPayload = Annotated[
    Union[
        MessageWebhookPayload,
        GroupJoinedWebhookPayload,
        BotRemovedWebhookPayload,
        ConnectionStatusWebhookPayload,
    ],
    Field(discriminator="event"),
]


def _validate_invite_link(link: str) -> bool:
    """Basic WhatsApp invite link format validation.

    Accepts the canonical share URL, with or without a trailing slash, and
    tolerates the newer share links that append ?uba=...&ref=... query params.
    """
    stripped = link.strip().split("?")[0].split("#")[0]
    return stripped.startswith("https://chat.whatsapp.com/") or stripped.startswith(
        "http://chat.whatsapp.com/"
    )


def _extract_invite_code(link: str) -> str:
    """Pull the bare invite code out of a chat.whatsapp.com link.

    Handles trailing slashes, query strings (?uba=share&ref=...), fragments,
    and stray trailing '+' characters that some copied links carry.
    """
    cleaned = link.strip().split("?")[0].split("#")[0].rstrip("/").rstrip("+")
    return cleaned.split("/")[-1]


@router.get("", response_model=list[WhatsAppGroupResponse])
async def list_groups(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all WhatsApp groups linked by the current user"""
    groups = db.query(WhatsAppGroup).filter(
        WhatsAppGroup.user_id == user.id,
        WhatsAppGroup.is_active == True,
    ).order_by(WhatsAppGroup.created_at.desc()).all()
    return groups


@router.post("/join", status_code=status.HTTP_202_ACCEPTED)
async def join_group(
    body: JoinGroupRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Queue a WhatsApp group join request.
    Free-tier users are limited to 2 linked groups.
    If the bot is already in the group (linked by another user), links immediately.
    """
    # Validate invite link format
    if not _validate_invite_link(body.invite_link):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid WhatsApp invite link. Must start with https://chat.whatsapp.com/",
        )

    # Enforce free-tier group limit
    if not user.is_premium:
        current_count = db.query(WhatsAppGroup).filter(
            WhatsAppGroup.user_id == user.id,
            WhatsAppGroup.is_active == True,
        ).count()

        if current_count >= FREE_TIER_GROUP_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Free tier allows a maximum of {FREE_TIER_GROUP_LIMIT} linked groups. "
                    "Upgrade to Premium for unlimited group monitoring."
                ),
            )

    # Extract group invite code from link
    invite_code = _extract_invite_code(body.invite_link)
    if not invite_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not extract an invite code from the provided link.",
        )

    # Build the canonical pending JID so we look up by exact match only — a
    # broad ``LIKE %invite_code%`` would falsely match unrelated real JIDs
    # whose random alphanumeric happens to contain the invite code substring.
    pending_jid = f"pending-{invite_code}@g.us"

    # Check if already linked by this user
    existing = db.query(WhatsAppGroup).filter(
        WhatsAppGroup.user_id == user.id,
        (WhatsAppGroup.group_jid == pending_jid) | (WhatsAppGroup.group_jid == invite_code),
    ).first()

    if existing:
        if existing.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This group is already linked to your account.",
            )
        else:
            # Reactivate it
            existing.is_active = True
            existing.coverage_state = CoverageState.ACTIVE
            db.commit()
            return {
                "message": "Group reactivated successfully.",
                "group_id": str(existing.id),
                "status": "ACTIVE",
            }

    # Optimization: Check if this group was already joined by ANY other user
    # (meaning the bot is already in the group and has a real group_jid).
    # Match by exact pending-JID counterpart: a successful join replaces the
    # pending-JID with the real one, so we look for either the pending or
    # canonical forms.
    already_joined = db.query(WhatsAppGroup).filter(
        WhatsAppGroup.group_jid.in_([pending_jid, invite_code]),
        WhatsAppGroup.is_active == True,
    ).first()

    if already_joined:
        logger.info(f"Bot is already in group {already_joined.group_jid}. Linking user {user.id} immediately.")
        group = WhatsAppGroup(
            user_id=user.id,
            group_jid=already_joined.group_jid,
            group_name=already_joined.group_name,
            group_description=already_joined.group_description,
            group_picture_url=already_joined.group_picture_url,
            coverage_state=CoverageState.ACTIVE,
            is_active=True,
        )
        db.add(group)
        db.commit()
        db.refresh(group)

        return {
            "message": "Bot is already in this group. Monitored active immediately.",
            "group_id": str(group.id),
            "status": "ACTIVE",
        }

    # Otherwise: create a pending group record.
    # The background scheduler or webhook will handle the join and update status.
    group = WhatsAppGroup(
        user_id=user.id,
        group_jid=f"pending-{invite_code}@g.us",
        group_name=f"Group ({invite_code[:8]}...)",
        coverage_state=CoverageState.RECOVERING,
        is_active=True,
    )
    db.add(group)
    db.commit()
    db.refresh(group)

    logger.info(f"Group join queued for user {user.id}: invite={invite_code}")

    return {
        "message": "Group join request queued. Monitoring will begin once the bot joins.",
        "group_id": str(group.id),
        "status": "QUEUED",
    }


@router.delete("/{group_id}")
async def unlink_group(
    group_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unlink a WhatsApp group (soft-delete)"""
    group = db.query(WhatsAppGroup).filter(
        WhatsAppGroup.id == group_id,
        WhatsAppGroup.user_id == user.id,
    ).first()

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found.",
        )

    group.is_active = False
    group.coverage_state = CoverageState.PAUSED
    db.commit()

    return {"message": "Group unlinked. Monitoring stopped."}


@router.get("/{group_id}/status")
async def get_group_status(
    group_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the real coverage state of a linked group"""
    group = db.query(WhatsAppGroup).filter(
        WhatsAppGroup.id == group_id,
        WhatsAppGroup.user_id == user.id,
    ).first()

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found.",
        )

    return {
        "group_id": str(group.id),
        "group_name": group.group_name,
        "status": group.coverage_state,
        "is_active": group.is_active,
        "last_coverage_update": group.last_coverage_update,
        "outage_start": group.outage_start,
        "outage_end": group.outage_end,
    }


@router.get("/bot/connection-status")
async def get_bot_status(
    user: User = Depends(get_current_user),
):
    """Get status of the external WhatsApp bot socket connection"""
    return WhatsAppService.get_status()


@router.post("/reconcile-joins")
async def reconcile_pending_joins(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Detect groups the bot is already a member of (joined manually on the
    primary phone) and flip their pending records to ACTIVE.

    WhatsApp blocks linked-device API joins with account_reachout_restricted,
    so the supported flow is: join the group manually on the bot's phone,
    then call this endpoint to reconcile.
    """
    pending_groups = db.query(WhatsAppGroup).filter(
        WhatsAppGroup.group_jid.like("pending-%"),
        WhatsAppGroup.is_active == True,
    ).all()

    if not pending_groups:
        return {"status": "success", "message": "No pending groups to reconcile.", "reconciled": 0, "checked": 0}

    # De-duplicate by invite code (multiple users may link the same group).
    seen_codes: dict[str, str] = {}
    reconciled = 0

    for group in pending_groups:
        invite_code = group.group_jid.split("@")[0].replace("pending-", "")

        if invite_code in seen_codes:
            # Already resolved this code — apply the cached result.
            real_jid = seen_codes[invite_code]
            group.group_jid = real_jid
            group.coverage_state = CoverageState.ACTIVE
            group.join_date = datetime.utcnow()
            group.last_coverage_update = datetime.utcnow()
            group.join_attempts = 0
            group.next_join_attempt = None
            reconciled += 1
            continue

        res = WhatsAppService.check_invite(invite_code)
        if not res.get("success"):
            logger.info(f"Reconcile: could not resolve invite '{invite_code}': {res.get('message')}")
            continue

        if res.get("is_member"):
            real_jid = res["group_jid"]
            seen_codes[invite_code] = real_jid
            # Update ALL pending records for this invite code.
            matching = db.query(WhatsAppGroup).filter(
                WhatsAppGroup.group_jid == group.group_jid
            ).all()
            for g in matching:
                g.group_jid = real_jid
                g.group_name = res.get("group_name") or g.group_name
                g.group_description = res.get("group_description") or g.group_description
                g.coverage_state = CoverageState.ACTIVE
                g.join_date = datetime.utcnow()
                g.last_coverage_update = datetime.utcnow()
                g.join_attempts = 0
                g.next_join_attempt = None
            reconciled += len(matching)
            logger.info(f"Reconcile: group '{invite_code}' is a member -> {real_jid} ({len(matching)} records)")
        else:
            logger.info(f"Reconcile: bot is not a member of '{invite_code}' yet (resolved jid={res.get('group_jid')})")

    db.commit()
    return {
        "status": "success",
        "checked": len(pending_groups),
        "reconciled": reconciled,
        "message": f"Reconciled {reconciled} pending record(s). Join the group manually on the bot's phone first if none matched.",
    }


@router.post("/webhook")
async def whatsapp_webhook(
    payload: WebhookPayload,
    x_webhook_secret: Optional[str] = Header(default=None, alias="X-Webhook-Secret"),
    db: Session = Depends(get_db),
):
    """
    Webhook endpoint to handle events from the Node.js WhatsApp connector.

    Authenticates via the ``WHATSAPP_CONNECTOR_WEBHOOK_SECRET`` shared secret
    (passed in the ``X-Webhook-Secret`` header). When the secret is unset the
    webhook is rejected fail-closed; configure the connector with the same
    secret to enable it.
    """
    expected_secret = getattr(settings, "whatsapp_connector_webhook_secret", "")
    if not expected_secret:
        logger.warning(
            "WHATSAPP_CONNECTOR_WEBHOOK_SECRET is not configured — rejecting webhook"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook is not configured on this server.",
        )
    if not hmac.compare_digest(x_webhook_secret or "", expected_secret):
        logger.warning("Webhook rejected: invalid X-Webhook-Secret")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook secret.",
        )

    event = payload.event
    data = payload.data.model_dump()
    logger.info(f"Received webhook event: {event}")

    if event == "message":
        from app.tasks import process_incoming_message_task
        from app.models import RawMessage

        message_id = data["message_id"]
        group_jid = data["group_jid"]
        already_seen = (
            db.query(RawMessage.id)
            .join(WhatsAppGroup, RawMessage.group_id == WhatsAppGroup.id)
            .filter(
                WhatsAppGroup.group_jid == group_jid,
                RawMessage.message_id == message_id,
            )
            .first()
        )
        if already_seen:
            return {"status": "ignored", "reason": "duplicate_message"}

        # Queue the message processing task asynchronously in Celery
        process_incoming_message_task.delay(data)
        
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"status": "success", "message": "Message processing task queued."}
        )

    elif event == "group_joined":
        invite_code = data["invite_code"]
        group_jid = data["group_jid"]
        group_name = data["group_name"]
        group_description = data.get("group_description")

        # Find all pending records for this invite code
        pending_groups = db.query(WhatsAppGroup).filter(
            WhatsAppGroup.group_jid == f"pending-{invite_code}@g.us"
        ).all()

        for group in pending_groups:
            group.group_jid = group_jid
            group.group_name = group_name
            group.group_description = group_description
            group.coverage_state = CoverageState.ACTIVE
            group.last_coverage_update = datetime.utcnow()
            
        db.commit()
        logger.info(f"Updated {len(pending_groups)} pending groups to ACTIVE for JID {group_jid}")
        return {"status": "success", "updated_groups": len(pending_groups)}

    elif event == "bot_removed":
        group_jid = data["group_jid"]

        # Find all active groups with this JID
        groups = db.query(WhatsAppGroup).filter(
            WhatsAppGroup.group_jid == group_jid,
            WhatsAppGroup.is_active == True
        ).all()

        for group in groups:
            group.coverage_state = CoverageState.PAUSED
            group.is_active = False
            group.outage_start = datetime.utcnow()

        db.commit()
        logger.info(f"Bot was removed from {group_jid}. Paused monitoring for {len(groups)} user groups.")
        return {"status": "success", "paused_groups": len(groups)}

    elif event == "connection_status":
        status_val = data["status"]
        # Log connection status update
        from app.models import SystemHealth
        health = SystemHealth(
            service_name="whatsapp_connector",
            service_status=status_val,
            message=f"WhatsApp connection status changed to {status_val}",
            checked_at=datetime.utcnow()
        )
        db.add(health)
        db.commit()
        return {"status": "success"}

    return {"status": "ignored", "reason": "unknown event"}
