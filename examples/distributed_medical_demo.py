from __future__ import annotations

import asyncio

from bgw.circuits import build_therapy_response_sums, build_variant_frequency_sums
from bgw.field import DEFAULT_PRIME
from bgw.participant import BGWParticipant
from bgw.reconstruction import reconstruct_result
from bgw.transport.memory import InMemoryTransport

PARTICIPANTS = [1, 2, 3]
T = 1


def reveal(parties: dict[int, BGWParticipant], value_name: str) -> int:
    return reconstruct_result(
        prime=DEFAULT_PRIME,
        threshold=T,
        shares=[parties[pid].get_share(value_name) for pid in PARTICIPANTS],
    )


async def main() -> None:
    transport = InMemoryTransport()
    parties = {
        pid: BGWParticipant(
            session_id="precision-demo",
            participant_id=pid,
            participant_ids=PARTICIPANTS,
            threshold=T,
        )
        for pid in PARTICIPANTS
    }
    for pid, party in parties.items():
        transport.register(pid, party.handle_message)

    # Variant Frequency: each tuple is (local variant count, local cohort size).
    variant_local = {1: (12, 100), 2: (18, 120), 3: (10, 80)}
    for owner, (variant_count, cohort_size) in variant_local.items():
        await parties[owner].share_private_input(f"v{owner}", variant_count, transport)
        await parties[owner].share_private_input(f"n{owner}", cohort_size, transport)

    for party in parties.values():
        build_variant_frequency_sums(
            party,
            variant_wires=["v1", "v2", "v3"],
            cohort_wires=["n1", "n2", "n3"],
        )

    V = reveal(parties, "variant_total")
    N = reveal(parties, "cohort_total")
    print(f"Variant frequency: {V}/{N} = {100 * V / N:.2f}%")

    # New session in production. Reused here only to keep the example short.
    therapy_local = {
        1: (21, 9, 15, 25),
        2: (16, 9, 14, 21),
        3: (15, 5, 12, 18),
    }
    for owner, values in therapy_local.items():
        for label, value in zip(("a", "b", "c", "d"), values):
            await parties[owner].share_private_input(f"{label}{owner}", value, transport)

    for party in parties.values():
        build_therapy_response_sums(
            party,
            a_wires=["a1", "a2", "a3"],
            b_wires=["b1", "b2", "b3"],
            c_wires=["c1", "c2", "c3"],
            d_wires=["d1", "d2", "d3"],
        )

    # All hospitals execute the same two interactive gates.
    for party in parties.values():
        await party.begin_multiplication(
            operation_id="AD", out="AD", a="A", b="D", transport=transport
        )
        await party.begin_multiplication(
            operation_id="BC", out="BC", a="B", b="C", transport=transport
        )

    for party in parties.values():
        party.finalize_multiplication(operation_id="AD", out="AD")
        party.finalize_multiplication(operation_id="BC", out="BC")

    AD = reveal(parties, "AD")
    BC = reveal(parties, "BC")
    odds_ratio = None if BC == 0 else AD / BC
    print(f"Therapy association: AD={AD}, BC={BC}, OR={odds_ratio:.4f}")


if __name__ == "__main__":
    asyncio.run(main())
