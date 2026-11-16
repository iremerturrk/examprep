"""Rucksack: Brute-Force (optimal), Greedy (değere / orana göre) ve DynProg tablosu (VL1)."""

from itertools import combinations


def _items(inp: dict) -> list[dict]:
    items = inp["items"]
    for it in items:
        if it["w"] < 0 or it["g"] < 0:
            raise ValueError("Değer ve ağırlıklar negatif olamaz")
    return items


def _optimal(items: list[dict], M: int) -> tuple[int, list[str]]:
    best_value, best = 0, []
    for r in range(len(items) + 1):
        for combo in combinations(items, r):
            if sum(i["g"] for i in combo) <= M:
                value = sum(i["w"] for i in combo)
                if value > best_value:
                    best_value, best = value, [i["name"] for i in combo]
    return best_value, best


def _greedy(items: list[dict], M: int, key) -> tuple[int, list[str]]:
    # slayttaki Greedy: azalan sıralama, sığan her elemanı ekle (eşitlikte girdi sırası korunur)
    chosen, weight = [], 0
    for it in sorted(items, key=key, reverse=True):
        if weight + it["g"] <= M:
            chosen.append(it)
            weight += it["g"]
    return sum(i["w"] for i in chosen), [i["name"] for i in chosen]


def solve(inp: dict) -> dict:
    items, M = _items(inp), inp["M"]
    method = inp.get("method", "optimal")
    if method == "optimal":
        value, names = _optimal(items, M)
    elif method == "greedy_value":
        value, names = _greedy(items, M, key=lambda i: i["w"])
    elif method == "greedy_ratio":
        value, names = _greedy(items, M, key=lambda i: i["w"] / i["g"] if i["g"] else float("inf"))
    else:
        raise ValueError(f"Bilinmeyen yöntem: {method}")
    optimal_value = value if method == "optimal" else _optimal(items, M)[0]
    return {"method": method, "value": value, "items": names, "optimal_value": optimal_value,
            "is_optimal": value == optimal_value}


def compare_solve(computed: dict, expected: dict) -> list[str]:
    out = []
    if "value" in expected and expected["value"] != computed["value"]:
        out.append(f"value: iddia {expected['value']}, hesaplanan {computed['value']}")
    if "items" in expected:
        claimed = set(expected["items"])
        if computed["method"] == "optimal":
            # birden fazla optimal küme olabilir: iddia edilen küme geçerli ve optimal mi?
            if claimed != set(computed["items"]) and expected.get("value") != computed["value"]:
                out.append(f"items: iddia {sorted(claimed)}, bir optimal küme {computed['items']}")
        elif claimed != set(computed["items"]):
            out.append(f"items: iddia {sorted(claimed)}, greedy {computed['items']}")
    if "is_optimal" in expected and expected["is_optimal"] != computed["is_optimal"]:
        out.append(f"is_optimal: iddia {expected['is_optimal']}, hesaplanan {computed['is_optimal']}")
    if "optimal_value" in expected and expected["optimal_value"] != computed["optimal_value"]:
        out.append(f"optimal_value: iddia {expected['optimal_value']}, hesaplanan {computed['optimal_value']}")
    return out


def dp_table(inp: dict) -> dict:
    """Slayttaki DynProg: T[i][h], i = 0..N (ilk i eleman), h = 0..M."""
    items, M = _items(inp), inp["M"]
    T = [[0] * (M + 1) for _ in range(len(items) + 1)]
    for i in range(1, len(items) + 1):
        g, w = items[i - 1]["g"], items[i - 1]["w"]
        for h in range(M + 1):
            T[i][h] = T[i - 1][h] if h < g else max(T[i - 1][h], T[i - 1][h - g] + w)
    return {"table": T, "value": T[-1][-1]}


def compare_table(computed: dict, expected: dict) -> list[str]:
    out = []
    if "value" in expected and expected["value"] != computed["value"]:
        out.append(f"value: iddia {expected['value']}, hesaplanan {computed['value']}")
    if "table" in expected:
        claimed, real = expected["table"], computed["table"]
        if len(claimed) != len(real) or any(len(a) != len(b) for a, b in zip(claimed, real)):
            out.append(f"table boyutu: iddia {len(claimed)}×{len(claimed[0]) if claimed else 0}, "
                       f"hesaplanan {len(real)}×{len(real[0])}")
        else:
            for i, (a, b) in enumerate(zip(claimed, real)):
                for h, (x, y) in enumerate(zip(a, b)):
                    if x != y:
                        out.append(f"T[{i}][{h}]: iddia {x}, hesaplanan {y}")
    return out
