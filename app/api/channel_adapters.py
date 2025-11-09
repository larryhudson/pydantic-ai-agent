"""API endpoints for channel adapters (webhooks, etc.)."""

import logging
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import InteractiveCapable
from app.adapters.email import EmailChannelAdapter
from app.config import get_settings
from app.database import get_db
from app.services.channel_adapter_manager import ChannelAdapterManager, SecurityError
from app.services.conversation_manager import ConversationManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/channel-adapters", tags=["channel-adapters"])

settings = get_settings()

# Global channel adapter manager instance
_channel_manager: ChannelAdapterManager | None = None


def get_channel_manager() -> ChannelAdapterManager:
    """Get or create the global channel adapter manager."""
    global _channel_manager
    if _channel_manager is None:
        _channel_manager = ChannelAdapterManager()
    return _channel_manager


async def initialize_email_adapter() -> None:
    """Initialize and register the email adapter."""
    if not settings.mailgun_api_key or not settings.mailgun_domain:
        logger.warning("Mailgun not configured - email adapter will not be available")
        return

    manager = get_channel_manager()
    adapter = EmailChannelAdapter(
        mailgun_api_key=settings.mailgun_api_key,
        mailgun_domain=settings.mailgun_domain,
    )
    await manager.register_adapter("email", adapter)
    logger.info("Email adapter (Mailgun) registered")


@router.post("/email/webhook")
async def email_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Receive incoming email webhook from Mailgun.

    Mailgun sends incoming emails to this endpoint when configured
    in the domain settings.

    Args:
        request: FastAPI request containing Mailgun webhook payload
        db: Database session

    Returns:
        Confirmation response

    Raises:
        HTTPException: If Mailgun not configured (returns 503)
    """
    if not settings.mailgun_api_key or not settings.mailgun_domain:
        logger.error("Mailgun not configured (missing API key or domain)")
        raise HTTPException(status_code=503, detail="Email service not configured")

    # Parse the incoming form data from Mailgun
    form_data = await request.form()
    event_data = dict(form_data)
    message_id = event_data.get("message-id", "unknown")

    try:
        # Get channel manager and handle incoming event
        channel_manager = get_channel_manager()
        conversation_manager = ConversationManager(db)

        conversation_id, _thread_id = await channel_manager.handle_incoming_event(
            adapter_name="email",
            event_data=event_data,
            conversation_manager=conversation_manager,
            db_session=db,
        )

        await db.commit()
        logger.info(f"Successfully processed email {message_id} to conversation {conversation_id}")

        return {"status": "ok", "message_id": message_id, "conversation_id": str(conversation_id)}

    except SecurityError as e:
        logger.warning(f"Security error processing email {message_id}: {e}")
        # Return 200 anyway to prevent Mailgun retries
        # but log the security issue
        return {"status": "error", "message": "signature verification failed"}

    except Exception as e:
        logger.error(f"Error processing email {message_id}: {e}", exc_info=True)
        # Return 200 to acknowledge receipt and prevent Mailgun retries
        # The error is logged for investigation
        return {"status": "error", "message": str(e)}


@router.post("/slack/events")
async def slack_events(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle incoming Slack events (app_mention, message, etc.).

    Args:
        request: Raw HTTP request from Slack
        db: Database session

    Returns:
        Slack API response
    """
    # Parse request body
    body = await request.json()

    # Handle Slack URL verification challenge
    if body.get("type") == "url_verification":
        return {"challenge": body.get("challenge")}

    # Get the Slack adapter
    manager = ChannelAdapterManager(db)
    try:
        adapter = manager.get_adapter("slack")
    except KeyError:
        raise HTTPException(status_code=500, detail="Slack adapter not configured") from None

    # Get raw request data for signature verification
    raw_body = await request.body()
    headers = dict(request.headers)

    request_data = {"headers": headers, "body": raw_body.decode("utf-8")}

    # Verify Slack request signature
    is_valid = await adapter.verify_request(request_data)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid Slack signature")

    # Handle the incoming event
    try:
        conversation_manager = ConversationManager(db)
        conversation_id, thread_id = await manager.handle_incoming_event(
            "slack", body, conversation_manager, db
        )
        return {"ok": True, "conversation_id": str(conversation_id), "thread_id": thread_id}
    except SecurityError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/slack/interactions")
async def slack_interactions(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle Slack interactive events (button clicks, menu selections, etc.).

    Args:
        request: Raw HTTP request from Slack
        db: Database session

    Returns:
        Slack API response
    """
    import json

    # Parse form data
    form = await request.form()
    payload_str = form.get("payload", "{}")

    # Handle case where payload might be UploadFile
    if isinstance(payload_str, str):
        payload_str_decoded = payload_str
    else:
        payload_str_decoded = await payload_str.read()
        payload_str_decoded = payload_str_decoded.decode("utf-8")

    # Parse JSON payload
    try:
        payload = json.loads(payload_str_decoded)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="Invalid JSON in payload") from e

    # Get the Slack adapter
    manager = ChannelAdapterManager(db)
    try:
        adapter = manager.get_adapter("slack")
    except KeyError:
        raise HTTPException(status_code=500, detail="Slack adapter not configured") from None

    # Get raw request data for signature verification
    raw_body = await request.body()
    headers = dict(request.headers)

    request_data = {"headers": headers, "body": raw_body.decode("utf-8")}

    # Verify Slack request signature
    is_valid = await adapter.verify_request(request_data)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid Slack signature")

    # Handle interaction
    try:
        # Check if adapter supports interactions
        if not hasattr(adapter, "handle_interaction"):
            raise HTTPException(status_code=400, detail="Adapter does not support interactions")

        interactive_adapter = cast(InteractiveCapable, adapter)
        interaction_response = await interactive_adapter.handle_interaction(payload)

        # Store conversation mapping if needed
        trigger_id = payload.get("trigger_id", "")
        await manager._store_conversation_mapping(
            conversation_id=interaction_response.conversation_id,
            adapter_name="slack",
            thread_id=trigger_id,
            metadata=payload,
            db_session=db,
        )

        return {"ok": True, "action_id": interaction_response.action_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
