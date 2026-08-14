from __future__ import annotations

from bgw.models import MPCMessage
from bgw.transport.base import MPCTransport
from bgw.transport.http import HTTPTransport


class HospitalNodeTransport(MPCTransport):
    """Direct peer transport with an in-process fast path for messages to self."""

    def __init__(self, *, local_participant, peer_urls, service_token, timeout_seconds):
        self.local_participant = local_participant
        self.http = HTTPTransport(
            peer_urls,
            service_token=service_token,
            timeout_seconds=timeout_seconds,
        )

    async def send(self, message: MPCMessage) -> None:
        if message.recipient_id == self.local_participant.participant_id:
            await self.local_participant.handle_message(message)
            return
        await self.http.send(message)
