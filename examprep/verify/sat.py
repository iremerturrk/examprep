"""SAT doğrulayıcıları. Formüller KNF, DIMACS tarzı: [[1, -2, 3], [-1, 4]] (i ≡ x_i, -i ≡ ¬x_i)."""

from itertools import product

MAX_VARS = 20


def _cnf(inp: dict) -> list[list[int]]:
    cnf = inp["cnf"]
    if any(lit == 0 for clause in cnf for lit in clause):
        raise ValueError("Literal 0 olamaz")
    return cnf


def _vars(cnf) -> list[int]:
    return sorted({abs(lit) for clause in cnf for lit in clause})


def _sat(cnf, assignment: dict[int, bool]) -> bool:
    return all(any(assignment[abs(l)] == (l > 0) for l in clause) for clause in cnf)


def _models(cnf, variables):
    if len(variables) > MAX_VARS:
        raise ValueError(f"En fazla {MAX_VARS} değişken")
    for bits in product([False, True], repeat=len(variables)):
        a = dict(zip(variables, bits))
        if _sat(cnf, a):
            yield a


def solve(inp: dict) -> dict:
    cnf = _cnf(inp)
    variables = sorted(set(_vars(cnf)) | set(range(1, inp.get("num_vars", 0) + 1)))
    models = list(_models(cnf, variables))
    return {"satisfiable": bool(models), "count": len(models),
            "example": {str(k): v for k, v in models[0].items()} if models else None}


def compare_solve(computed: dict, expected: dict) -> list[str]:
    return [f"{k}: iddia {v}, hesaplanan {computed[k]}"
            for k, v in expected.items() if k in ("satisfiable", "count") and k in computed and computed[k] != v]


def evaluate(inp: dict) -> dict:
    cnf = _cnf(inp)
    a = {int(k): bool(v) for k, v in inp["assignment"].items()}
    missing = [v for v in _vars(cnf) if v not in a]
    if missing:
        raise ValueError(f"Atanmamış değişkenler: {missing}")
    return {"value": _sat(cnf, a), "false_clauses": [i for i, c in enumerate(cnf) if not _sat([c], a)]}


def compare_eval(computed: dict, expected: dict) -> list[str]:
    return [] if "value" not in expected or expected["value"] == computed["value"] else [
        f"value: iddia {expected['value']}, hesaplanan {computed['value']}"]


def two_sat(inp: dict) -> dict:
    """Implikasyon grafiği (¬a → b, ¬b → a) + güçlü bağlı bileşenler (Kosaraju)."""
    cnf = _cnf(inp)
    if any(len(c) > 2 for c in cnf):
        raise ValueError("2-SAT için her klozda en fazla 2 literal olmalı")
    graph: dict[int, set[int]] = {}
    for clause in cnf:
        a, b = (clause[0], clause[0]) if len(clause) == 1 else clause
        graph.setdefault(-a, set()).add(b)
        graph.setdefault(-b, set()).add(a)
    nodes = {l for v in _vars(cnf) for l in (v, -v)}
    order, seen = [], set()

    def dfs(u, g, acc):
        stack = [(u, iter(g.get(u, ())))]
        seen.add(u)
        while stack:
            node, it = stack[-1]
            nxt = next((w for w in it if w not in seen), None)
            if nxt is None:
                stack.pop()
                acc.append(node)
            else:
                seen.add(nxt)
                stack.append((nxt, iter(g.get(nxt, ()))))

    for n in sorted(nodes):
        if n not in seen:
            dfs(n, graph, order)
    rev: dict[int, set[int]] = {}
    for u, vs in graph.items():
        for w in vs:
            rev.setdefault(w, set()).add(u)
    seen.clear()
    comp = {}
    for n in reversed(order):
        if n not in seen:
            acc = []
            dfs(n, rev, acc)
            for m in acc:
                comp[m] = n
    conflicts = sorted(v for v in _vars(cnf) if comp[v] == comp[-v])
    edges = sorted(f"{-u if u < 0 else u}{'' if u > 0 else '̄'}→{w}" for u, vs in graph.items() for w in vs)
    return {"satisfiable": not conflicts, "conflict_vars": conflicts, "edge_count": sum(len(v) for v in graph.values()),
            "edges": edges}


def horn(inp: dict) -> dict:
    """Horn formülü (her klozda en fazla bir pozitif literal) için birim yayılımı."""
    cnf = _cnf(inp)
    if any(sum(l > 0 for l in c) > 1 for c in cnf):
        raise ValueError("Horn formülünde her klozda en fazla bir pozitif literal olmalı")
    true_vars: set[int] = set()
    changed = True
    while changed:
        changed = False
        for clause in cnf:
            pos = [l for l in clause if l > 0]
            if pos and pos[0] not in true_vars and all(-l in true_vars for l in clause if l < 0):
                true_vars.add(pos[0])
                changed = True
    satisfiable = all(any(l > 0 and l in true_vars for l in c) or any(l < 0 and -l not in true_vars for l in c)
                      for c in cnf)
    return {"satisfiable": satisfiable, "true_vars": sorted(true_vars) if satisfiable else None}


def compare_horn(computed: dict, expected: dict) -> list[str]:
    out = compare_solve(computed, expected)
    if "true_vars" in expected and computed["satisfiable"] and sorted(expected["true_vars"]) != computed["true_vars"]:
        out.append(f"true_vars (minimal model): iddia {sorted(expected['true_vars'])}, hesaplanan {computed['true_vars']}")
    return out


def to_3sat(inp: dict) -> dict:
    """Standart bölme: k > 3 literallik kloz → k − 2 kloz ve k − 3 ek değişken."""
    cnf = _cnf(inp)
    clauses = sum(1 if len(c) <= 3 else len(c) - 2 for c in cnf)
    new_vars = sum(max(0, len(c) - 3) for c in cnf)
    result = {"clauses": clauses, "new_vars": new_vars}
    if "cnf_3" in inp:
        result.update(_check_equisat(cnf, inp["cnf_3"]))
    return result


def _check_equisat(original, transformed) -> dict:
    """Her orijinal atama için: orijinal doğru ⇔ ek değişkenlerin bir ataması dönüşmüş formülü sağlar."""
    if any(len(c) > 3 for c in transformed):
        return {"equisatisfiable": False, "reason": "3'ten uzun kloz var"}
    orig_vars = _vars(original)
    extra = sorted(set(_vars(transformed)) - set(orig_vars))
    if len(orig_vars) + len(extra) > MAX_VARS:
        raise ValueError(f"Eşdeğerlik kontrolü için en fazla {MAX_VARS} değişken")
    for bits in product([False, True], repeat=len(orig_vars)):
        a = dict(zip(orig_vars, bits))
        ext = any(_sat(transformed, {**a, **dict(zip(extra, eb))}) for eb in product([False, True], repeat=len(extra)))
        if _sat(original, a) != ext:
            return {"equisatisfiable": False, "reason": f"atama {a} için farklı"}
    return {"equisatisfiable": True}


def compare_to_3sat(computed: dict, expected: dict) -> list[str]:
    out = [f"{k}: iddia {expected[k]}, hesaplanan {computed[k]}"
           for k in ("clauses", "new_vars") if k in expected and expected[k] != computed[k]]
    if computed.get("equisatisfiable") is False:
        out.append(f"dönüşmüş formül eşdeğer değil: {computed.get('reason')}")
    return out
