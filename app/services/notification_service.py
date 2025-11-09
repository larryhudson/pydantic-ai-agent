"""Service for sending notifications via various channels."""

import logging
from typing import Any

import aiohttp

from app.config import get_settings
from app.models.domain import NotificationChannel, NotificationConfig, Task

logger = logging.getLogger(__name__)
settings = get_settings()


class NotificationService:
    """Handles sending notifications through multiple channels."""

    async def notify_task_complete(self, task: Task, result: str) -> None:
        """Send notification when a task completes successfully.

        Args:
            task: Completed task
            result: Task result/output
        """
        subject = f"Task Completed: {task.task_type.value}"
        message = f"""
Task ID: {task.id}
Type: {task.task_type.value}
Status: Completed
Prompt: {task.prompt}

Result:
{result}
"""

        await self._send_notifications(task.notification_config, subject, message)

    async def notify_task_failed(self, task: Task, error: str) -> None:
        """Send notification when a task fails.

        Args:
            task: Failed task
            error: Error message
        """
        subject = f"Task Failed: {task.task_type.value}"
        message = f"""
Task ID: {task.id}
Type: {task.task_type.value}
Status: Failed
Prompt: {task.prompt}

Error:
{error}
"""

        await self._send_notifications(task.notification_config, subject, message)

    async def notify_task_blocked(self, task: Task, reason: str) -> None:
        """Send notification when a task is blocked and needs user input.

        Args:
            task: Blocked task
            reason: Reason for being blocked
        """
        subject = f"Task Blocked: {task.task_type.value}"
        message = f"""
Task ID: {task.id}
Type: {task.task_type.value}
Status: Blocked (Needs User Input)
Prompt: {task.prompt}

Reason:
{reason}

Please continue the conversation at: /conversations/{task.conversation_id}
"""

        await self._send_notifications(task.notification_config, subject, message)

    async def _send_notifications(
        self, config: NotificationConfig, subject: str, message: str
    ) -> None:
        """Send notifications through all configured channels.

        Args:
            config: Notification configuration
            subject: Notification subject/title
            message: Notification message body
        """
        for channel in config.channels:
            try:
                if channel == NotificationChannel.EMAIL and config.email_address:
                    await self.send_email(config.email_address, subject, message)
                elif channel == NotificationChannel.SLACK and config.slack_webhook_url:
                    await self.send_slack(config.slack_webhook_url, subject, message)
                elif channel == NotificationChannel.WEBHOOK and config.webhook_url:
                    await self.send_webhook(config.webhook_url, subject, message)
            except Exception as e:
                logger.error(f"Failed to send notification via {channel}: {e}", exc_info=True)

    async def send_email(self, to: str, subject: str, body: str) -> None:
        """Send email notification via Mailgun.

        TODO: Refactor to use EmailChannelAdapter instead of duplicating
        email sending logic. This method should delegate to the channel adapter.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body (plain text)

        Raises:
            RuntimeError: If Mailgun not configured or email sending fails
        """
        if not settings.mailgun_api_key or not settings.mailgun_domain:
            logger.error("Mailgun not configured - cannot send email notification")
            raise RuntimeError("Email service not configured")

        email_data = {
            "from": settings.mailgun_from_email,
            "to": to,
            "subject": subject,
            "text": body,
        }

        try:
            mailgun_url = f"https://api.mailgun.net/v3/{settings.mailgun_domain}/messages"
            auth = aiohttp.BasicAuth("api", settings.mailgun_api_key)

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    mailgun_url,
                    data=email_data,
                    auth=auth,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        logger.info(f"Email notification sent to {to}")
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"Failed to send email via Mailgun: {response.status} {error_text}"
                        )
                        raise RuntimeError(f"Mailgun API error: {response.status}")
        except aiohttp.ClientError as e:
            logger.error(f"Network error sending email to {to}: {e}", exc_info=True)
            raise RuntimeError(f"Failed to send email: {e}") from e

    async def send_slack(self, webhook_url: str, title: str, message: str) -> None:
        """Send Slack notification via webhook.

        Args:
            webhook_url: Slack webhook URL
            title: Message title
            message: Message body
        """
        payload = {
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": title}},
                {"type": "section", "text": {"type": "mrkdwn", "text": message}},
            ]
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    response.raise_for_status()
                    logger.info("Slack notification sent successfully")
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}", exc_info=True)
            raise

    async def send_webhook(self, webhook_url: str, title: str, message: str) -> None:
        """Send notification to a webhook endpoint.

        Args:
            webhook_url: Webhook URL
            title: Notification title
            message: Notification message
        """
        payload: dict[str, Any] = {"title": title, "message": message}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    response.raise_for_status()
                    logger.info(f"Webhook notification sent to {webhook_url}")
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}", exc_info=True)
            raise
