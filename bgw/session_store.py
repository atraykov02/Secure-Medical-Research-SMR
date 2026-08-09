from __future__ import annotations

from dataclasses import dataclass, field

from .participant import BGWParticipant


@dataclass
class BGWSessionStore:
    """Ephemeral per-process session registry for one hospital node."""

    sessions: dict[str, BGWParticipant] = field(default_factory=dict)

    def create(self, participant: BGWParticipant) -> BGWParticipant:
        if participant.session_id in self.sessions:
            raise ValueError(f"session '{participant.session_id}' already exists")
        self.sessions[participant.session_id] = participant
        return participant

    def get(self, session_id: str) -> BGWParticipant:
        try:
            return self.sessions[session_id]
        except KeyError as exc:
            raise KeyError(f"unknown MPC session '{session_id}'") from exc

    def destroy(self, session_id: str) -> None:
        participant = self.sessions.pop(session_id, None)
        if participant is not None:
            participant.clear_sensitive_state()
