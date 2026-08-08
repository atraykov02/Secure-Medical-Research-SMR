from __future__ import annotations

from collections.abc import Awaitable, Callable

from .base import MPCTransport
from ..models import MPCMessage

MessageHandler = Callable[[MPCMessage], Awaitable[None]]


class InMemoryTransport(MPCTransport):
    """Test transport that still keeps participants as separate objects."""

    def __init__(self):
        self._handlers: dict[int, MessageHandler] = {}
        self.sent_messages: list[MPCMessage] = []

    def register(self, participant_id: int, handler: MessageHandler) -> None:
        self._handlers[participant_id] = handler

    async def send(self, message: MPCMessage) -> None:
        self.sent_messages.append(message)
        handler = self._handlers.get(message.recipient_id)
        if handler is None:
            raise RuntimeError(f"no participant registered for id {message.recipient_id}")
        await handler(message)
