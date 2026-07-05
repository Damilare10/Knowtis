"""
API Routes - Billing / RevenueCat Webhook
Handles subscription lifecycle events from RevenueCat.
"""
import logging
import hmac
from fastapi import APIRouter, Depends, HTTPException, Request, Header, status
from sqlalchemy import or_
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app.models import User, Subscription
from app.config import settings
from app.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/billing", tags=["Billing"])

# RevenueCat event types that indicate an active premium subscription
PREMIUM_EVENTS = {"INITIAL_PURCHASE", "RENEWAL", "UNCANCELLATION", "PRODUCT_CHANGE"}

# RevenueCat event types that indicate subscription ended
EXPIRED_EVENTS = {"EXPIRATION", "CANCELLATION", "BILLING_ISSUE"}

# Pricing configuration in Naira (NGN)
NAIRA_PRICING = {
    "pro_monthly": 6500.00,
    "pro_yearly": 65000.00,
}
DEFAULT_NAIRA_PRICE = 6500.00


def _verify_revenuecat_webhook(authorization: str | None) -> bool:
    """
    Validate the RevenueCat webhook Authorization header.
    RevenueCat sends: Authorization: Bearer <WEBHOOK_SECRET>
    """
    if not settings.revenuecat_webhook_secret:
        # Fail-closed: refuse webhooks when the secret is not configured so a
        # missing env var cannot be exploited to forge subscription upgrades.
        logger.error(
            "REVENUECAT_WEBHOOK_SECRET not set — rejecting webhook (configure the secret to enable)"
        )
        return False

    if not authorization:
        return False

    if authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
        return hmac.compare_digest(token, settings.revenuecat_webhook_secret)

    return False


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def revenuecat_webhook(
    request: Request,
    authorization: str = Header(None),
    db: Session = Depends(get_db),
):
    """
    RevenueCat webhook endpoint.
    Receives subscription lifecycle events and updates user tier in the database.
    Processes payments in Nigerian Naira (NGN) internally.
    """
    if not _verify_revenuecat_webhook(authorization):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook authorization.",
        )

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload.",
        )

    event = payload.get("event", {})
    event_type = event.get("type", "")
    app_user_id = event.get("app_user_id", "")
    product_id = event.get("product_id", "")
    environment = event.get("environment", "PRODUCTION")

    logger.info(f"RevenueCat webhook: type={event_type} user={app_user_id} env={environment}")

    if environment == "SANDBOX":
        logger.debug(f"Sandbox webhook event — processing for dev/test purposes")

    # Find user by app_user_id (email or username) in a single query.
    user = (
        db.query(User)
        .filter(or_(User.email == app_user_id, User.username == app_user_id))
        .first()
    )

    if not user:
        logger.warning(f"RevenueCat webhook: user not found for app_user_id={app_user_id}")
        return {"received": True, "processed": False, "reason": "user_not_found"}

    # ── Upgrade to Premium ─────────────────────────────────────────────────
    if event_type in PREMIUM_EVENTS:
        user.is_premium = True
        user.tier = "premium"

        # Parse timestamps (ms → datetime)
        expiration_ms = event.get("expiration_at_ms")
        purchased_ms = event.get("purchased_at_ms")
        end_date = datetime.utcfromtimestamp(expiration_ms / 1000) if expiration_ms else None
        start_date = datetime.utcfromtimestamp(purchased_ms / 1000) if purchased_ms else datetime.utcnow()

        # Determine amount and currency (forced to NGN on backend)
        currency = "NGN"
        price = NAIRA_PRICING.get(product_id, DEFAULT_NAIRA_PRICE)

        # Allow matching event-reported NGN prices directly if they exist
        event_currency = event.get("currency")
        event_price = event.get("price_in_purchased_currency")
        if event_currency == "NGN" and event_price is not None:
            price = float(event_price)

        # Upsert Subscription record
        sub = db.query(Subscription).filter(
            Subscription.user_id == user.id,
        ).order_by(Subscription.created_at.desc()).first()

        if sub:
            sub.tier = "premium"
            sub.is_active = True
            sub.end_date = end_date
            sub.renewal_date = end_date
            sub.payment_provider = event.get("store", "PLAY_STORE")
            sub.price = price
            sub.currency = currency
        else:
            sub = Subscription(
                user_id=user.id,
                revenuecat_subscription_id=f"{app_user_id}_{product_id}",
                tier="premium",
                start_date=start_date,
                end_date=end_date,
                renewal_date=end_date,
                is_active=True,
                auto_renew=True,
                payment_provider=event.get("store", "PLAY_STORE"),
                price=price,
                currency=currency,
            )
            db.add(sub)

        db.commit()
        logger.info(f"User {user.id} upgraded to premium (paid {currency} {price}) via {event_type}")

    # ── Downgrade to Free ──────────────────────────────────────────────────
    elif event_type in EXPIRED_EVENTS:
        user.is_premium = False
        user.tier = "free"

        # Mark subscription as inactive
        sub = db.query(Subscription).filter(
            Subscription.user_id == user.id,
            Subscription.is_active == True,
        ).first()

        if sub:
            sub.is_active = False
            sub.auto_renew = False

        db.commit()
        logger.info(f"User {user.id} downgraded to free via {event_type}")

    else:
        logger.info(f"Unhandled RevenueCat event type: {event_type} — no action taken")

    return {"received": True, "processed": True, "event_type": event_type}


@router.get("/subscription")
async def get_user_subscription(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get current user's active subscription information.
    Surfaces the backend currency (Naira) and price.
    """
    sub = db.query(Subscription).filter(
        Subscription.user_id == user.id,
        Subscription.is_active == True,
    ).order_by(Subscription.created_at.desc()).first()

    if not sub:
        return {
            "is_active": False,
            "tier": "free",
            "price": 0.0,
            "currency": "NGN",
            "end_date": None,
        }

    return {
        "is_active": sub.is_active,
        "tier": sub.tier,
        "price": sub.price or 0.0,
        "currency": sub.currency or "NGN",
        "end_date": sub.end_date,
        "renewal_date": sub.renewal_date,
        "payment_provider": sub.payment_provider,
    }

