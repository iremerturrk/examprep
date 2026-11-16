"""Doğrulayıcılar slayt/sınav örnekleriyle test edilir."""

from fractions import Fraction
from itertools import product

import pytest

from examprep.verify import CHECKERS, run_check
from examprep.verify import average_case

INC_TM = [  # VL2 slayt 4: Eins-Inkrement
    ["I", "0", "I", "0", "R"], ["I", "1", "I", "1", "R"], ["I", "_", "X", "_", "L"],
    ["X", "_", "A", "1", "N"], ["X", "0", "A", "1", "L"], ["X", "1", "X", "0", "L"],
]
FLIP_TM = [["I", "0", "I", "1", "R"], ["I", "1", "I", "0", "R"], ["I", "_", "A", "_", "N"]]  # Wdh 3.1


def check(name, inp, expected):
    return run_check({"checker": name, "input": inp, "expected": expected})


# --- Rucksack
SLIDE_GREEDY = [{"name": "e1", "w": 3, "g": 2}, {"name": "e2", "w": 2, "g": 1}, {"name": "e3", "w": 2, "g": 1}]
HW_ITEMS = [{"name": "A", "w": 3, "g": 2}, {"name": "B", "w": 2, "g": 1},
            {"name": "C", "w": 5, "g": 3}, {"name": "D", "w": 2, "g": 3}]


def test_knapsack_greedy_counterexample_from_slide():
    r = check("knapsack.solve", {"items": SLIDE_GREEDY, "M": 2, "method": "greedy_value"},
              {"value": 3, "items": ["e1"], "is_optimal": False, "optimal_value": 4})
    assert r["status"] == "passed", r


def test_knapsack_optimal_and_wrong_claim():
    assert check("knapsack.solve", {"items": HW_ITEMS, "M": 5}, {"value": 8, "items": ["A", "C"]})["status"] == "passed"
    r = check("knapsack.solve", {"items": HW_ITEMS, "M": 5}, {"value": 7})
    assert r["status"] == "failed" and "hesaplanan 8" in r["mismatches"][0]


def test_knapsack_dp_table_from_slide():
    items = [{"name": "e1", "w": 2, "g": 1}, {"name": "e2", "w": 1, "g": 2}]
    table = [[0, 0, 0, 0], [0, 2, 2, 2], [0, 2, 2, 3]]
    assert check("knapsack.dp_table", {"items": items, "M": 3}, {"table": table, "value": 3})["status"] == "passed"
    bad = [row[:] for row in table]
    bad[2][3] = 2
    r = check("knapsack.dp_table", {"items": items, "M": 3}, {"table": bad})
    assert r["mismatches"] == ["T[2][3]: iddia 2, hesaplanan 3"]


# --- TM
def test_tm_increment_slide_example():
    r = check("tm.run", {"transitions": INC_TM, "input": "1011"},
              {"tape": "1100", "accepted": True, "steps": 8})
    assert r["status"] == "passed", r


def test_tm_runtime_matches_slide_formula():
    computed = CHECKERS["tm.runtime"].compute({"transitions": INC_TM, "N": 4})
    assert computed["wc"] == 2 * 4 + 2  # slayt: wc-time = 2N + 2


def test_tm_multiple_inputs_wdh_klausur():
    r = check("tm.run", {"transitions": FLIP_TM, "inputs": ["000", "011", "111"]},
              {"runs": {"000": {"tape": "111"}, "011": {"tape": "100"}, "111": {"tape": "001"}}})
    assert r["status"] == "failed" and r["mismatches"] == ["111: tape: iddia '001', hesaplanan '000'"]


def test_tm_nondeterministic_rejected():
    r = check("tm.run", {"transitions": FLIP_TM + [["I", "0", "A", "0", "N"]], "input": "0"}, {})
    assert r["status"] == "error" and "Deterministik" in r["error"]


# --- RAM (Wiederholungsklausur 2.2, 'R[R-1]' baskı hatası düzeltilmiş hali)
RAM_PROG = ["R[-1] = R[0]", "IF R[-1] = 0: END (A)", "IF R[R[-1]] = 0: GOTO B", "R[R[-1]] = 0",
            "R[-1] = R[-1] - 1", "GOTO A", "R[R[-1]] = 1 (B)", "END"]


@pytest.mark.parametrize(("regs", "result"), [
    ((0, 0, 0), (0, 0, 1)), ((0, 0, 1), (0, 1, 0)), ((0, 1, 0), (0, 1, 1)), ((1, 1, 1), (0, 0, 0)),
])
def test_ram_program_increments(regs, result):
    registers = {"0": 3, "1": regs[0], "2": regs[1], "3": regs[2]}
    expected = {"registers": {"1": result[0], "2": result[1], "3": result[2]}}
    assert check("ram.run", {"program": RAM_PROG, "registers": registers}, expected)["status"] == "passed"


def test_ram_label_prefix_and_errors():
    prog = ["R[1] = 0", "L: IF R[1] >= R[0]: END", "R[1] = R[1] + 1", "R[-2] = R[-2] + R[R[1]]", "GOTO L"]
    # R[1] sayaç: R[R[1]] sırayla R[1] (=1, sayacın kendisi), R[2], R[3] -> 1 + 5 + 7
    r = check("ram.run", {"program": prog, "registers": {"0": 3, "2": 5, "3": 7}}, {"registers": {"-2": 13}})
    assert r["status"] == "passed", r
    assert check("ram.run", {"program": ["R[R-1] = 1"]}, {})["status"] == "error"
    assert check("ram.run", {"program": ["GOTO X"]}, {})["status"] == "error"


# --- SAT
def test_sat_solve_and_eval():
    cnf = [[1, 2], [-1, 2], [1, -2]]
    assert check("sat.solve", {"cnf": cnf}, {"satisfiable": True, "count": 1})["status"] == "passed"
    assert check("sat.eval", {"cnf": cnf, "assignment": {"1": False, "2": True}}, {"value": False})["status"] == "passed"


def test_two_sat_unsatisfiable_cycle():
    cnf = [[1, 2], [-1, 2], [1, -2], [-1, -2]]
    r = check("sat.2sat", {"cnf": cnf}, {"satisfiable": False})
    assert r["status"] == "passed" and r["computed"]["conflict_vars"] == [1, 2]
    assert check("sat.2sat", {"cnf": [[1, 2, 3]]}, {})["status"] == "error"


def test_two_sat_agrees_with_brute_force():
    import random
    rng = random.Random(7)
    for _ in range(200):
        cnf = [[rng.choice([-1, 1]) * rng.randint(1, 4) for _ in range(2)] for _ in range(rng.randint(1, 7))]
        assert (CHECKERS["sat.2sat"].compute({"cnf": cnf})["satisfiable"]
                == CHECKERS["sat.solve"].compute({"cnf": cnf})["satisfiable"]), cnf


def test_horn():
    r = check("sat.horn", {"cnf": [[1], [-1, 2], [-2, -3]]}, {"satisfiable": True, "true_vars": [1, 2]})
    assert r["status"] == "passed"
    assert check("sat.horn", {"cnf": [[1], [-1]]}, {"satisfiable": False})["status"] == "passed"
    assert check("sat.horn", {"cnf": [[1, 2]]}, {})["status"] == "error"  # Horn değil


def test_to_3sat_counts_and_equisatisfiability():
    good = check("sat.to3sat", {"cnf": [[1, 2, 3, 4]], "cnf_3": [[1, 2, 5], [-5, 3, 4]]}, {"clauses": 2, "new_vars": 1})
    assert good["status"] == "passed"
    bad = check("sat.to3sat", {"cnf": [[1, 2, 3, 4]], "cnf_3": [[1, 2, 5], [5, 3, 4]]}, {"clauses": 2})
    assert bad["status"] == "failed" and "eşdeğer değil" in bad["mismatches"][0]
    m = CHECKERS["sat.to3sat"].compute({"cnf": [[1, 2, 3, 4, 5, 6]] * 3})
    assert m == {"clauses": 12, "new_vars": 9}  # 6-SAT, M=3: (k−2)·M kloz, (k−3)·M ek değişken


# --- 3-SAT ≤p Rucksack
def test_reduction_exam_teilsummen():
    r = check("reduction.3sat_subsetsum", {"cnf": [[1, 2, 3]], "variant": "exam"},
              {"values": [1001, 1000, 101, 100, 11, 10, 2, 1], "target": 1114, "element_count": 8})
    assert r["status"] == "passed", r


def test_reduction_slides_two_clauses():
    r = check("reduction.3sat_subsetsum", {"cnf": [[1, 2, 3], [-1, 2, -3]]},
              {"values": [10010, 10001, 1011, 1000, 110, 101, 10, 10, 1, 1], "target": 11133})
    assert r["status"] == "passed", r


# --- Average case
@pytest.mark.parametrize("algorithm", ["compare_bits", "increment", "first_one"])
def test_average_case_matches_closed_form(algorithm):
    for N in range(1, 7):
        got = Fraction(CHECKERS["average_case.expected"].compute({"algorithm": algorithm, "N": N})["expected"])
        assert got == 2 - Fraction(2, 2 ** N)


def test_average_case_compare_bits_by_full_enumeration():
    N = 3  # C ve D'nin tüm çiftleri (XOR indirgemesi olmadan)
    costs = []
    for c, d in product(product((0, 1), repeat=N), repeat=2):
        k = next((i for i in range(N) if c[i] != d[i]), N - 1) + 1
        costs.append(k)
    assert Fraction(sum(costs), len(costs)) == Fraction(average_case.expected({"algorithm": "compare_bits", "N": N})["expected"])


def test_average_case_limit_claim():
    assert check("average_case.expected", {"algorithm": "increment", "N": 5}, {"limit": 2})["status"] == "passed"
    assert check("average_case.expected", {"algorithm": "increment", "N": 5}, {"limit": 1})["status"] == "failed"


# --- Asimptotik sıralama
def test_asymptotic_order_klausur_1_1():
    r = check("asymptotic.order", {"functions": ["factorial(n)", "sqrt(n)", "n/log(n)"]},
              {"order": [["sqrt(n)"], ["n/log(n)"], ["factorial(n)"]]})
    assert r["status"] == "passed", r


def test_asymptotic_theta_class_and_oscillation():
    r = check("asymptotic.order", {"functions": ["n**2*(sin(n)+2)", "2**(cos(n)**2)", "n**2", "10**23*n"]},
              {"order": [["2**(cos(n)**2)"], ["10**23*n"], ["n**2*(sin(n)+2)", "n**2"]]})
    assert r["status"] == "passed", r


def test_unknown_checker():
    r = run_check({"checker": "yok", "input": {}})
    assert r["status"] == "error" and "knapsack.solve" in r["available"]


def test_asymptotic_two_oscillating_functions():
    r = check("asymptotic.order", {"functions": ["n*(cos(n)+3)", "3**(sin(n)**2)", "n*log(n**2)", "10**9*n"]},
              {"order": [["3**(sin(n)**2)"], ["n*(cos(n)+3)", "10**9*n"], ["n*log(n**2)"]]})
    assert r["status"] == "passed", r


def test_asymptotic_unbounded_oscillation_stays_undetermined():
    # n^(sin n) Θ-sınıfına sahip değil: çekirdek reddedilmeli, yanlış karar verilmemeli
    r = check("asymptotic.order", {"functions": ["n**(sin(n)+1)", "n"]}, {"order": [["n"], ["n**(sin(n)+1)"]]})
    assert r["status"] in ("undetermined", "failed") and r["status"] != "passed"
