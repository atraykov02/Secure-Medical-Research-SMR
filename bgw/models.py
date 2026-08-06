from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from time import time


@dataclass(frozen=True)
class Share:
    x: int
    y: int


class MessageType(StrEnum):
    INPUT_SHARE = "input_share"
    MULTIPLICATION_RESHARE = "multiplication_reshare"


@dataclass(frozen=True)
class MPCMessage:
    session_id: str
    message_type: MessageType
    sender_id: int
    recipient_id: int
    value_name: str
    value: int
    operation_id: str | None = None
    created_at: float = field(default_factory=time)

    def to_payload(self) -> dict:
        """HTTP-safe payload. Field elements are decimal strings intentionally."""
        return {
            "session_id": self.session_id,
            "message_type": self.message_type.value,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "value_name": self.value_name,
            "value": str(self.value),
            "operation_id": self.operation_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_payload(cls, payload: dict) -> "MPCMessage":
        return cls(
            session_id=str(payload["session_id"]),
            message_type=MessageType(payload["message_type"]),
            sender_id=int(payload["sender_id"]),
            recipient_id=int(payload["recipient_id"]),
            value_name=str(payload["value_name"]),
            value=int(payload["value"]),
            operation_id=payload.get("operation_id"),
            created_at=float(payload.get("created_at", time())),
        )
