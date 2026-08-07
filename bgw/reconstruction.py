from __future__ import annotations

from .field import PrimeField
from .models import Share
from .shamir import shamir_reconstruct


def reconstruct_result(
    *,
    prime: int,
    threshold: int,
    shares: list[Share],
    signed: bool = False,
) -> int:
    """Reconstruct an explicitly authorized final aggregate/result."""
    F = PrimeField(prime)
    value = shamir_reconstruct(F, shares, threshold=threshold)
    return F.to_signed(value) if signed else value
