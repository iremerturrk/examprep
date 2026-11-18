"""Uniform dağılımda erken sonlanan döngülerin beklenen maliyeti (VL2 av-time, sınav 'Average Case').

Algoritmalar (N bit, her bit bağımsız ve uniform):
- compare_bits: iki bit dizisini baştan karşılaştır, ilk farkta dur (maliyet: karşılaştırma)
- increment: n+1, en düşük bitten başla; biti çevir, 0→1 olunca dur (maliyet: bit çevirme)
- first_one: ilk 1 bitini ara (maliyet: okunan bit)
Üçünde de maliyet = ilk "durma" bitinin konumu (yoksa N): E = Σ_{k=0}^{N−1} 2^{−k} = 2 − 2^{1−N}.
Doğrulayıcı formülü değil, girdileri sayarak hesaplar.
"""

from fractions import Fraction
from itertools import product

LIMIT_N = 60
ENUM_MAX_N = 16


def _cost(algorithm: str, bits: tuple[int, ...]) -> int:
    # compare_bits için C XOR D'nin bitleri uniformdur: 1 = fark → durma
    # increment için çevrilen bit 0 ise dur → 'durma biti' = 0; sırayı LSB'den alırız
    stop = 0 if algorithm == "increment" else 1
    for k, b in enumerate(bits, 1):
        if b == stop:
            return k
    return len(bits)


def _exact(algorithm: str, N: int) -> Fraction:
    if N <= ENUM_MAX_N:
        total = sum(_cost(algorithm, bits) for bits in product((0, 1), repeat=N))
        return Fraction(total, 2 ** N)
    # büyük N için aynı dağılımdan kapalı biçim (sayım küçük N'lerde testlerle doğrulanır)
    return sum(Fraction(1, 2 ** k) for k in range(N))


def expected(inp: dict) -> dict:
    algorithm = inp["algorithm"]
    if algorithm not in ("compare_bits", "increment", "first_one"):
        raise ValueError("algorithm: compare_bits | increment | first_one")
    N = int(inp["N"])
    if N < 1:
        raise ValueError("N ≥ 1 olmalı")
    value = _exact(algorithm, N)
    limit = float(_exact(algorithm, LIMIT_N))
    return {"expected": str(value), "expected_float": float(value), "limit": round(limit, 9),
            "bounded": True}


def compare(computed: dict, expected: dict) -> list[str]:
    out = []
    if "expected" in expected:
        claimed = float(Fraction(str(expected["expected"])))
        if abs(claimed - computed["expected_float"]) > 1e-9:
            out.append(f"expected: iddia {expected['expected']}, hesaplanan {computed['expected']}")
    if "limit" in expected and abs(float(expected["limit"]) - computed["limit"]) > 1e-6:
        out.append(f"limit: iddia {expected['limit']}, hesaplanan {computed['limit']}")
    return out
