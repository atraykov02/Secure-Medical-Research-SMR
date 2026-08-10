from __future__ import annotations

import asyncio

from bgw.circuits import build_therapy_response_sums, build_variant_frequency_sums
from bgw.field import DEFAULT_PRIME, PrimeField
from bgw.models import MPCMessage, MessageType
from bgw.participant import BGWParticipant
from bgw.reconstruction import reconstruct_result
from bgw.shamir import shamir_share
from bgw.transport.memory import InMemoryTransport


PARTY_IDS = [1, 2, 3]
THRESHOLD = 1


def make_participants(session_id: str = "test-session"):
    transport = InMemoryTransport()
    participants = {
        pid: BGWParticipant(
            session_id=session_id,
            participant_id=pid,
            participant_ids=PARTY_IDS,
            threshold=THRESHOLD,
        )
        for pid in PARTY_IDS
    }
    for pid, participant in participants.items():
        transport.register(pid, participant.handle_message)
    return participants, transport


async def share_owned_value(participants, transport, owner_id: int, name: str, value: int):
    await participants[owner_id].share_private_input(name, value, transport)


def reveal(participants, name: str) -> int:
    shares = [participants[pid].get_share(name) for pid in PARTY_IDS]
    return reconstruct_result(
        prime=DEFAULT_PRIME,
        threshold=THRESHOLD,
        shares=shares,
        signed=False,
    )


def test_shamir_threshold_validation():
    F = PrimeField()
    shares = shamir_share(F, 42, threshold=1, xs=PARTY_IDS)
    assert len(shares) == 3


def test_distributed_input_and_addition():
    async def scenario():
        participants, transport = make_participants()
        await share_owned_value(participants, transport, 1, "x1", 10)
        await share_owned_value(participants, transport, 2, "x2", 20)
        await share_owned_value(participants, transport, 3, "x3", 30)

        for participant in participants.values():
            participant.local_add("tmp", "x1", "x2")
            participant.local_add("sum", "tmp", "x3")

        assert reveal(participants, "sum") == 60

    asyncio.run(scenario())


def test_distributed_multiplication_and_degree_reduction():
    async def scenario():
        participants, transport = make_participants()
        await share_owned_value(participants, transport, 1, "a", 17)
        await share_owned_value(participants, transport, 2, "b", 9)

        for participant in participants.values():
            await participant.begin_multiplication(
                operation_id="mul-1",
                out="product",
                a="a",
                b="b",
                transport=transport,
            )

        for participant in participants.values():
            assert participant.can_finalize_multiplication("mul-1")
            participant.finalize_multiplication(operation_id="mul-1", out="product")

        assert reveal(participants, "product") == 153

    asyncio.run(scenario())


def test_variant_frequency_medical_flow():
    async def scenario():
        participants, transport = make_participants("variant")
        local = {1: (12, 100), 2: (18, 120), 3: (10, 80)}

        for owner_id, (variants, cohort) in local.items():
            await share_owned_value(participants, transport, owner_id, f"v{owner_id}", variants)
            await share_owned_value(participants, transport, owner_id, f"n{owner_id}", cohort)

        for participant in participants.values():
            build_variant_frequency_sums(
                participant,
                variant_wires=["v1", "v2", "v3"],
                cohort_wires=["n1", "n2", "n3"],
            )

        assert reveal(participants, "variant_total") == 40
        assert reveal(participants, "cohort_total") == 300

    asyncio.run(scenario())


def test_therapy_response_secure_cross_products():
    async def scenario():
        participants, transport = make_participants("therapy")
        # (variant+responder, variant+nonresponder, no-variant+responder, no-variant+nonresponder)
        local = {
            1: (21, 9, 15, 25),
            2: (16, 9, 14, 21),
            3: (15, 5, 12, 18),
        }

        labels = ("a", "b", "c", "d")
        for owner_id, values in local.items():
            for label, value in zip(labels, values):
                await share_owned_value(
                    participants, transport, owner_id, f"{label}{owner_id}", value
                )

        for participant in participants.values():
            build_therapy_response_sums(
                participant,
                a_wires=["a1", "a2", "a3"],
                b_wires=["b1", "b2", "b3"],
                c_wires=["c1", "c2", "c3"],
                d_wires=["d1", "d2", "d3"],
            )

        for participant in participants.values():
            await participant.begin_multiplication(
                operation_id="AD",
                out="AD",
                a="A",
                b="D",
                transport=transport,
            )
            await participant.begin_multiplication(
                operation_id="BC",
                out="BC",
                a="B",
                b="C",
                transport=transport,
            )

        for participant in participants.values():
            participant.finalize_multiplication(operation_id="AD", out="AD")
            participant.finalize_multiplication(operation_id="BC", out="BC")

        A = 21 + 16 + 15
        B = 9 + 9 + 5
        C = 15 + 14 + 12
        D = 25 + 21 + 18
        assert reveal(participants, "AD") == A * D
        assert reveal(participants, "BC") == B * C

    asyncio.run(scenario())


def test_http_payload_uses_decimal_string_for_field_values():
    message = MPCMessage(
        session_id="s",
        message_type=MessageType.INPUT_SHARE,
        sender_id=1,
        recipient_id=2,
        value_name="x",
        value=2**60 + 123,
    )
    payload = message.to_payload()
    assert isinstance(payload["value"], str)
    assert MPCMessage.from_payload(payload) == message
