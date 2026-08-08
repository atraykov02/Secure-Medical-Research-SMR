from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import MPCMessage


class MPCTransport(ABC):
    @abstractmethod
    async def send(self, message: MPCMessage) -> None:
        """Deliver one MPC message to its recipient."""
        raise NotImplementedError
