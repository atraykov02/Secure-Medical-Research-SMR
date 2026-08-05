from __future__ import annotations

import secrets

DEFAULT_PRIME = 2**61 - 1


class PrimeField:
    """Arithmetic in the prime field GF(p)."""

    def __init__(self, p: int = DEFAULT_PRIME):
        if p <= 2:
            raise ValueError("p must be an odd prime greater than 2")
        self.p = p

    def elem(self, x: int) -> int:
        return x % self.p

    def add(self, a: int, b: int) -> int:
        return (a + b) % self.p

    def sub(self, a: int, b: int) -> int:
        return (a - b) % self.p

    def mul(self, a: int, b: int) -> int:
        return (a * b) % self.p

    def inv(self, a: int) -> int:
        a %= self.p
        if a == 0:
            raise ZeroDivisionError("0 has no multiplicative inverse in GF(p)")
        return pow(a, self.p - 2, self.p)

    def div(self, a: int, b: int) -> int:
        return self.mul(a, self.inv(b))

    def rand(self) -> int:
        return secrets.randbelow(self.p)

    def to_signed(self, a: int) -> int:
        a %= self.p
        return a - self.p if a > self.p // 2 else a
