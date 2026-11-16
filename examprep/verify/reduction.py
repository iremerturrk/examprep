"""3-SAT ≤p Rucksack / SubsetSum indirgemesi (VL7, sınav 'Teilsummen').

Basamaklar (onluk): önce N değişken basamağı, sonra C kloz basamağı.
- x_i = T elemanı: değişken basamağında 1 + x_i'nin geçtiği her kloz basamağında 1
- x_i = F elemanı: değişken basamağında 1 + ¬x_i'nin geçtiği her kloz basamağında 1
- Kloz başına iki yardımcı eleman:
    variant "slides": 1 ve 1, kloz basamağı hedefi 3   (slayt: M = 11133)
    variant "exam":   2 ve 1, kloz basamağı hedefi 4   (sınav: e7 = 2, e8 = 1)
"""

from collections import Counter

VARIANTS = {"slides": ((1, 1), 3), "exam": ((2, 1), 4)}


def three_sat_subsetsum(inp: dict) -> dict:
    cnf = inp["cnf"]
    if any(len(c) != 3 for c in cnf):
        raise ValueError("Her kloz tam 3 literal içermeli")
    variant = inp.get("variant", "slides")
    if variant not in VARIANTS:
        raise ValueError(f"variant: {sorted(VARIANTS)}")
    (s1, s2), clause_target = VARIANTS[variant]
    N = inp.get("num_vars") or max(abs(l) for c in cnf for l in c)
    C = len(cnf)
    var_digit = lambda i: 10 ** (C + N - i)  # noqa: E731
    clause_digit = lambda j: 10 ** (C - j)  # noqa: E731
    elements = []
    for i in range(1, N + 1):
        for positive in (True, False):
            lit = i if positive else -i
            value = var_digit(i) + sum(clause_digit(j) for j, c in enumerate(cnf, 1) if lit in c)
            elements.append({"name": f"x{i}={'T' if positive else 'F'}", "value": value})
    for j in range(1, C + 1):
        elements.append({"name": f"a{j}", "value": s1 * clause_digit(j)})
        elements.append({"name": f"b{j}", "value": s2 * clause_digit(j)})
    target = int("1" * N + str(clause_target) * C)
    return {"elements": elements, "values": sorted(e["value"] for e in elements), "target": target,
            "element_count": len(elements), "element_count_formula": "2N + 2C"}


def compare(computed: dict, expected: dict) -> list[str]:
    out = []
    if "target" in expected and int(expected["target"]) != computed["target"]:
        out.append(f"target: iddia {expected['target']}, hesaplanan {computed['target']}")
    if "values" in expected:
        claimed, real = Counter(int(v) for v in expected["values"]), Counter(computed["values"])
        if claimed != real:
            out.append(f"eleman değerleri: fazla {sorted((claimed - real).elements())}, "
                       f"eksik {sorted((real - claimed).elements())}")
    if "element_count" in expected and expected["element_count"] != computed["element_count"]:
        out.append(f"element_count: iddia {expected['element_count']}, hesaplanan {computed['element_count']}")
    return out
