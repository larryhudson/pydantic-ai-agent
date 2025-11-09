"""API endpoints for channel adapters (webhooks, etc.)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

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
