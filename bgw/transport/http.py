from __future__ import annotations

from .base import MPCTransport
from ..models import MPCMessage


class HTTPTransport(MPCTransport):
    """Production transport for direct hospital-node to hospital-node messages."""

    def __init__(
        self,
        peer_urls: dict[int, str],
        *,
        service_token: str | None = None,
        timeout_seconds: float = 10.0,
    ):
        self.peer_urls = {pid: url.rstrip("/") for pid, url in peer_urls.items()}
        self.service_token = service_token
        self.timeout_seconds = timeout_seconds

    async def send(self, message: MPCMessage) -> None:
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError("HTTPTransport requires the optional dependency 'httpx'") from exc

        base_url = self.peer_urls.get(message.recipient_id)
        if base_url is None:
            raise ValueError(f"missing URL for participant {message.recipient_id}")

        headers = {"Content-Type": "application/json"}
        if self.service_token:
            headers["X-MPC-Service-Token"] = self.service_token

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{base_url}/api/mpc/messages",
                json=message.to_payload(),
                headers=headers,
            )
            response.raise_for_status()
