from __future__ import annotations

from dataclasses import dataclass, field

from .field import DEFAULT_PRIME, PrimeField
from .models import MPCMessage, MessageType, Share
from .shamir import lagrange_coeffs_at_zero, shamir_share
from .transport.base import MPCTransport


@dataclass
class BGWParticipant:
    """One BGW participant for exactly one MPC session.

    This object never knows the private inputs or shares held by the other parties.
    It stores only this participant's local shares and the messages required for
    interactive multiplication.
    """

    session_id: str
    participant_id: int
    participant_ids: list[int]
    threshold: int
    prime: int = DEFAULT_PRIME
    trace_enabled: bool = False
    values: dict[str, int] = field(default_factory=dict)
    trace: list[dict] = field(default_factory=list)
    _mul_inbox: dict[str, dict[int, int]] = field(default_factory=dict)
    _mul_started: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.participant_id not in self.participant_ids:
            raise ValueError("participant_id must be included in participant_ids")
        if len(self.participant_ids) != len(set(self.participant_ids)):
            raise ValueError("participant_ids must be unique")
        if 0 in self.participant_ids:
            raise ValueError("participant ids are Shamir x-coordinates and must be non-zero")
        if len(self.participant_ids) < 2 * self.threshold + 1:
            raise ValueError("BGW multiplication requires n >= 2t + 1")

        self.F = PrimeField(self.prime)
        self._lambdas = dict(
            zip(
                self.participant_ids,
                lagrange_coeffs_at_zero(self.F, self.participant_ids),
            )
        )

    @property
    def n(self) -> int:
        return len(self.participant_ids)

    def has_value(self, name: str) -> bool:
        return name in self.values

    def get_share(self, name: str) -> Share:
        if name not in self.values:
            raise KeyError(f"unknown shared value '{name}'")
        return Share(self.participant_id, self.values[name])

    def set_public(self, name: str, value: int) -> None:
        self.values[name] = self.F.elem(value)

    # ------------------------ local operations ------------------------

    def local_add(self, out: str, a: str, b: str) -> None:
        self.values[out] = self.F.add(self.values[a], self.values[b])
        if self.trace_enabled:
            self.trace.append({"phase": "secure_computation", "operation": "add", "out": out, "left": a, "right": b, "left_share": str(self.values[a]), "right_share": str(self.values[b]), "result_share": str(self.values[out])})

    def local_sub(self, out: str, a: str, b: str) -> None:
        self.values[out] = self.F.sub(self.values[a], self.values[b])

    def local_add_const(self, out: str, a: str, constant: int) -> None:
        self.values[out] = self.F.add(self.values[a], self.F.elem(constant))

    def local_mul_const(self, out: str, a: str, constant: int) -> None:
        self.values[out] = self.F.mul(self.values[a], self.F.elem(constant))
        if self.trace_enabled:
            self.trace.append({"phase": "secure_computation", "operation": "multiply_constant", "out": out, "input": a, "constant": constant, "result_share": str(self.values[out])})

    # ------------------------ input sharing ------------------------

    async def share_private_input(
        self,
        name: str,
        secret: int,
        transport: MPCTransport,
    ) -> None:
        """Share a private input owned by this participant.

        The cleartext secret exists only in the caller's process. Each generated
        share is sent directly to its intended participant.
        """
        shares = shamir_share(self.F, secret, self.threshold, self.participant_ids)
        if self.trace_enabled:
            self.trace.append({"phase": "input_sharing", "operation": "shamir_share", "value_name": name, "secret": secret,
                               "shares": [{"recipient": share.x, "x": share.x, "value": str(share.y)} for share in shares]})
        for share in shares:
            message = MPCMessage(
                session_id=self.session_id,
                message_type=MessageType.INPUT_SHARE,
                sender_id=self.participant_id,
                recipient_id=share.x,
                value_name=name,
                value=share.y,
            )
            await transport.send(message)

    # ------------------------ interactive multiplication ------------------------

    async def begin_multiplication(
        self,
        *,
        operation_id: str,
        out: str,
        a: str,
        b: str,
        transport: MPCTransport,
    ) -> None:
        """Start BGW multiplication by locally multiplying and resharing d_i."""
        if a not in self.values or b not in self.values:
            raise KeyError("both multiplication operands must exist locally")

        d_i = self.F.mul(self.values[a], self.values[b])
        reshares = shamir_share(self.F, d_i, self.threshold, self.participant_ids)
        if self.trace_enabled:
            self.trace.append({"phase": "multiplication", "operation": "local_product_and_reshare", "operation_id": operation_id,
                               "left": a, "right": b, "left_share": str(self.values[a]), "right_share": str(self.values[b]),
                               "degree_2_share": str(d_i), "reshares": [{"recipient": s.x, "value": str(s.y)} for s in reshares]})

        # Incoming reshares may already exist because network delivery is asynchronous.
        # Only starting the same local multiplication twice is an error.
        if operation_id in self._mul_started:
            raise ValueError(f"multiplication operation '{operation_id}' was already started locally")
        self._mul_started.add(operation_id)
        self._mul_inbox.setdefault(operation_id, {})

        for share in reshares:
            message = MPCMessage(
                session_id=self.session_id,
                message_type=MessageType.MULTIPLICATION_RESHARE,
                sender_id=self.participant_id,
                recipient_id=share.x,
                value_name=out,
                value=share.y,
                operation_id=operation_id,
            )
            await transport.send(message)

    def can_finalize_multiplication(self, operation_id: str) -> bool:
        received = self._mul_inbox.get(operation_id, {})
        return set(received) == set(self.participant_ids)

    def finalize_multiplication(self, *, operation_id: str, out: str) -> None:
        received = self._mul_inbox.get(operation_id)
        if received is None:
            raise ValueError(f"unknown multiplication operation '{operation_id}'")

        missing = set(self.participant_ids) - set(received)
        if missing:
            raise RuntimeError(
                f"multiplication '{operation_id}' is incomplete; missing shares from {sorted(missing)}"
            )

        acc = 0
        for source_id in self.participant_ids:
            acc = self.F.add(
                acc,
                self.F.mul(self._lambdas[source_id], received[source_id]),
            )
        self.values[out] = acc
        if self.trace_enabled:
            self.trace.append({"phase": "degree_reduction", "operation": "lagrange_combine_reshares", "operation_id": operation_id,
                               "lagrange_coefficients": {str(k): str(v) for k, v in self._lambdas.items()},
                               "received_reshares": {str(k): str(v) for k, v in received.items()}, "result_share": str(acc), "out": out})
        del self._mul_inbox[operation_id]
        self._mul_started.discard(operation_id)

    # ------------------------ incoming network messages ------------------------

    async def handle_message(self, message: MPCMessage) -> None:
        if message.session_id != self.session_id:
            raise ValueError("message belongs to another MPC session")
        if message.recipient_id != self.participant_id:
            raise ValueError("message was sent to another participant")
        if message.sender_id not in self.participant_ids:
            raise ValueError("message sender is not part of this MPC session")

        if message.message_type is MessageType.INPUT_SHARE:
            # Different parties can own different input names. Reusing the same name
            # for two dealers is rejected because it would silently overwrite a share.
            if message.value_name in self.values:
                raise ValueError(f"shared value '{message.value_name}' already exists")
            self.values[message.value_name] = self.F.elem(message.value)
            if self.trace_enabled:
                self.trace.append({"phase": "share_distribution", "operation": "receive_input_share", "sender": message.sender_id,
                                   "value_name": message.value_name, "share": str(self.values[message.value_name])})
            return

        if message.message_type is MessageType.MULTIPLICATION_RESHARE:
            if not message.operation_id:
                raise ValueError("multiplication reshare requires operation_id")
            inbox = self._mul_inbox.setdefault(message.operation_id, {})
            if message.sender_id in inbox:
                raise ValueError(
                    f"duplicate multiplication reshare from participant {message.sender_id}"
                )
            inbox[message.sender_id] = self.F.elem(message.value)
            if self.trace_enabled:
                self.trace.append({"phase": "multiplication", "operation": "receive_degree_reduction_reshare", "sender": message.sender_id,
                                   "operation_id": message.operation_id, "share": str(inbox[message.sender_id])})
            return

        raise ValueError(f"unsupported MPC message type: {message.message_type}")

    def clear_sensitive_state(self) -> None:
        """
        Python cannot guarantee secure memory zeroization, but removing references is
        still useful and prevents accidental persistence in the application state.
        """
        self.values.clear()
        self._mul_inbox.clear()
        self._mul_started.clear()
        self.trace.clear()
