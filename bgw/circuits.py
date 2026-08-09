from __future__ import annotations

from .participant import BGWParticipant


def sum_shared_values(participant: BGWParticipant, names: list[str], out: str) -> None:
    if not names:
        raise ValueError("at least one shared value is required")
    if len(names) == 1:
        participant.local_mul_const(out, names[0], 1)
        return

    current = names[0]
    for index, name in enumerate(names[1:], start=1):
        target = out if index == len(names) - 1 else f"__sum_{out}_{index}"
        participant.local_add(target, current, name)
        current = target


def build_variant_frequency_sums(
    participant: BGWParticipant,
    *,
    variant_wires: list[str],
    cohort_wires: list[str],
    variant_total_out: str = "variant_total",
    cohort_total_out: str = "cohort_total",
) -> None:
    """Local circuit portion for the Variant Frequency analysis."""
    sum_shared_values(participant, variant_wires, variant_total_out)
    sum_shared_values(participant, cohort_wires, cohort_total_out)


def build_therapy_response_sums(
    participant: BGWParticipant,
    *,
    a_wires: list[str],
    b_wires: list[str],
    c_wires: list[str],
    d_wires: list[str],
) -> None:
    """Compute the four global 2x2-table cells in shared form."""
    sum_shared_values(participant, a_wires, "A")
    sum_shared_values(participant, b_wires, "B")
    sum_shared_values(participant, c_wires, "C")
    sum_shared_values(participant, d_wires, "D")

    # The combined cohort size is itself an allowed aggregate output.  Build it
    # locally from the four already-shared global cells without opening A/B/C/D.
    participant.local_add("__therapy_ab", "A", "B")
    participant.local_add("__therapy_cd", "C", "D")
    participant.local_add("therapy_cohort_total", "__therapy_ab", "__therapy_cd")
