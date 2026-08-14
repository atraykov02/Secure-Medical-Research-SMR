from __future__ import annotations

from dataclasses import dataclass, field

from bgw import BGWParticipant, BGWSessionStore
from bgw.transport.base import MPCTransport

from .config import HospitalSettings
from .schemas import MPCSessionCreate
from .transport import HospitalNodeTransport


@dataclass
class NodeRuntime:
    settings: HospitalSettings
    store: BGWSessionStore = field(default_factory=BGWSessionStore)
    transports: dict[str, MPCTransport] = field(default_factory=dict)

    def create_session(self, request: MPCSessionCreate) -> BGWParticipant:
        if request.prime != self.settings.prime:
            raise ValueError("session prime does not match node configuration")

        participant = BGWParticipant(
            session_id=request.session_id,
            participant_id=request.participant_id,
            participant_ids=request.participant_ids,
            threshold=request.threshold,
            prime=request.prime,
            trace_enabled=request.demonstration_trace,
        )
        self.store.create(participant)
        self.transports[request.session_id] = HospitalNodeTransport(
            local_participant=participant,
            peer_urls=request.peer_urls,
            service_token=self.settings.service_token,
            timeout_seconds=self.settings.http_timeout_seconds,
        )
        return participant

    def get_transport(self, session_id: str) -> MPCTransport:
        try:
            return self.transports[session_id]
        except KeyError as exc:
            raise KeyError(f"unknown transport for MPC session '{session_id}'") from exc

    def destroy_session(self, session_id: str) -> None:
        self.store.destroy(session_id)
        self.transports.pop(session_id, None)
