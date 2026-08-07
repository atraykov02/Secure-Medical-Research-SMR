from __future__ import annotations

from .field import PrimeField
from .models import Share


def shamir_share(F: PrimeField, secret: int, threshold: int, xs: list[int]) -> list[Share]:
    if threshold < 0:
        raise ValueError("threshold must be >= 0")
    if len(xs) < threshold + 1:
        raise ValueError("not enough participant points for the requested threshold")
    if 0 in xs:
        raise ValueError("participant x-coordinates must be non-zero")
    if len(xs) != len(set(xs)):
        raise ValueError("participant x-coordinates must be unique")

    coeffs = [F.elem(secret)] + [F.rand() for _ in range(threshold)]

    def evaluate(x: int) -> int:
        acc = 0
        for coefficient in reversed(coeffs):
            acc = F.add(F.mul(acc, x), coefficient)
        return acc

    return [Share(x=x, y=evaluate(x)) for x in xs]


def lagrange_coeffs_at_zero(F: PrimeField, xs: list[int]) -> list[int]:
    if len(xs) != len(set(xs)):
        raise ValueError("duplicate x-coordinates")

    coefficients: list[int] = []
    for i, xi in enumerate(xs):
        numerator, denominator = 1, 1
        for j, xj in enumerate(xs):
            if i == j:
                continue
            numerator = F.mul(numerator, F.elem(-xj))
            denominator = F.mul(denominator, F.sub(xi, xj))
        coefficients.append(F.mul(numerator, F.inv(denominator)))
    return coefficients


def shamir_reconstruct(
    F: PrimeField,
    shares: list[Share],
    threshold: int | None = None,
) -> int:
    if threshold is not None and len(shares) < threshold + 1:
        raise ValueError(
            f"not enough shares: need at least {threshold + 1}, got {len(shares)}"
        )
    if not shares:
        raise ValueError("at least one share is required")

    xs = [share.x for share in shares]
    coefficients = lagrange_coeffs_at_zero(F, xs)
    result = 0
    for coefficient, share in zip(coefficients, shares):
        result = F.add(result, F.mul(coefficient, share.y))
    return result
