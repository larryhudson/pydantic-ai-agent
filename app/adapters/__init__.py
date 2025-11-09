"""Channel adapter package for bidirectional communication with external platforms."""

from app.adapters.base import (
    AdapterCapabilities,
    ChannelAdapter,
    InteractiveCapable,
    MessageStyle,
    ReactionCapable,
    RichFormattingCapable,
    StreamingCapable,
)
from app.adapters.email import EmailChannelAdapter
from app.adapters.models import (
    InteractionResponse,
    InteractiveMessage,
    ReceivedMessage,
    RichMessage,
)
from app.adapters.slack import SlackChannelAdapter

__all__ = [
    "AdapterCapabilities",
    "ChannelAdapter",
    "EmailChannelAdapter",
    "InteractionResponse",
    "InteractiveCapable",
    "InteractiveMessage",
    "MessageStyle",
    "ReactionCapable",
    "ReceivedMessage",
    "RichFormattingCapable",
    "RichMessage",
    "SlackChannelAdapter",
    "StreamingCapable",
]
