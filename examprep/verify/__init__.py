"""Algoritmik soruların cevaplarını Python ile hesaplayıp doğrular.

Üretilen sorunun `check` bloğu: {"checker": "<ad>", "input": {...}, "expected": {...}}
- input: doğrulayıcının hesaplayacağı örnek (sorudaki veriyle birebir aynı)
- expected: sorunun cevabında iddia edilen yapılandırılmış sonuç

Doğrulayıcı sonucu kendisi hesaplar; iddia ile uyuşmazsa soru reddedilir. LLM cevabına güvenilmez.
"""

from dataclasses import dataclass
from typing import Any, Callable

from examprep.verify import asymptotic, average_case, knapsack, ram, reduction, sat, tm


@dataclass(frozen=True)
class Checker:
    compute: Callable[[dict], dict]
    compare: Callable[[dict, dict], list[str]]  # (computed, expected) -> uyuşmazlıklar
    description: str


CHECKERS: dict[str, Checker] = {
    "knapsack.solve": Checker(knapsack.solve, knapsack.compare_solve, "Rucksack: optimal / greedy çözüm ve değer"),
    "knapsack.dp_table": Checker(knapsack.dp_table, knapsack.compare_table, "Rucksack DynProg tablosu T[i][h]"),
    "tm.run": Checker(tm.run, tm.compare_run, "TM simülasyonu: son bant, durum, adım sayısı"),
    "tm.runtime": Checker(tm.runtime, tm.compare_runtime, "TM'nin N uzunluklu tüm girdiler için wc/bc/av adım sayısı"),
    "ram.run": Checker(ram.run, ram.compare_run, "RAM programı simülasyonu: son register değerleri"),
    "sat.solve": Checker(sat.solve, sat.compare_solve, "KNF: tatmin edilebilirlik ve sağlayan atama sayısı"),
    "sat.eval": Checker(sat.evaluate, sat.compare_eval, "KNF formülünü verilen atamada değerlendirme"),
    "sat.2sat": Checker(sat.two_sat, sat.compare_solve, "2-SAT implikasyon grafiği ile karar"),
    "sat.horn": Checker(sat.horn, sat.compare_horn, "Horn-SAT (birim yayılımı) ile karar ve minimal model"),
    "sat.to3sat": Checker(sat.to_3sat, sat.compare_to_3sat, "k-SAT → 3-SAT: kloz ve ek değişken sayıları, eşdeğerlik"),
    "reduction.3sat_subsetsum": Checker(
        reduction.three_sat_subsetsum, reduction.compare, "3-SAT ≤p Rucksack/SubsetSum: elemanlar ve hedef"
    ),
    "average_case.expected": Checker(
        average_case.expected, average_case.compare, "Erken sonlanan döngülerin beklenen maliyeti ve limiti"
    ),
    "asymptotic.order": Checker(asymptotic.order, asymptotic.compare, "Fonksiyonların asimptotik sıralaması (sympy)"),
}


class CheckerError(Exception):
    pass


def run_check(check: dict[str, Any]) -> dict[str, Any]:
    """check bloğunu çalıştırır: {status, checker, computed, mismatches[, error]}.

    status: passed | failed | error (girdi geçersiz / hesaplanamadı) | undetermined
    """
    name = check.get("checker")
    checker = CHECKERS.get(name)
    if checker is None:
        return {"status": "error", "checker": name, "error": f"Bilinmeyen doğrulayıcı: {name}",
                "available": sorted(CHECKERS)}
    try:
        computed = checker.compute(check.get("input") or {})
    except (CheckerError, ValueError, KeyError, TypeError, IndexError) as exc:
        return {"status": "error", "checker": name, "error": f"{type(exc).__name__}: {exc}"}
    if computed.get("undetermined"):
        return {"status": "undetermined", "checker": name, "computed": computed}
    mismatches = checker.compare(computed, check.get("expected") or {})
    return {"status": "failed" if mismatches else "passed", "checker": name,
            "computed": computed, "mismatches": mismatches}
