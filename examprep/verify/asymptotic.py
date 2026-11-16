"""Fonksiyonların asimptotik büyümeye göre sıralanması (sympy limitleri)."""

import sympy as sp

n = sp.Symbol("n", positive=True)
eps = sp.Symbol("eps", positive=True)
_LOCALS = {"n": n, "eps": eps, "epsilon": eps, "log": sp.log, "sqrt": sp.sqrt, "factorial": sp.factorial,
           "sin": sp.sin, "cos": sp.cos, "exp": sp.exp}


def _parse(expr: str):
    try:
        return sp.sympify(expr.replace("^", "**"), locals=_LOCALS)
    except (sp.SympifyError, SyntaxError, TypeError) as exc:
        raise ValueError(f"Çözümlenemeyen fonksiyon: {expr!r}") from exc


def _direct(f, g) -> int | None:
    """-1: f ∈ o(g), 0: f ∈ Θ(g), 1: f ∈ ω(g), None: belirlenemedi."""
    try:
        lim = sp.limit(sp.simplify(f / g), n, sp.oo)
    except Exception:  # sympy bazı salınımlı ifadelerde hata fırlatır
        return None
    if isinstance(lim, sp.AccumBounds):
        lo, hi = lim.min, lim.max
        if lo.is_positive and hi.is_finite:
            return 0
        if hi == 0:
            return -1
        if lo == sp.oo:
            return 1
        return None
    if lim == 0:
        return -1
    if lim in (sp.oo, -sp.oo):
        return 1
    if lim.is_finite and lim.is_nonzero:
        return 0
    return None


def _core(f):
    """Salınımlı f için salınımsız Θ-eşdeğer çekirdek: sin/cos → 1/2.

    Çekirdek yalnızca f/çekirdek oranı pozitif ve sınırlı kalıyorsa kabul edilir
    (örn. n·(cos n + 3) → 3.5·n, 3^(sin² n) → 3^(1/4)); aksi halde None.
    """
    trig = [a for a in f.atoms(sp.sin, sp.cos) if a.has(n)]
    if not trig:
        return f
    core = f.subs({a: sp.Rational(1, 2) for a in trig})
    if core == 0 or not core.has(n) and not core.is_positive:
        return None
    return core if _direct(f, core) == 0 else None


def _cmp_with_cores(f, g) -> int | None:
    c = _direct(f, g)
    if c is not None:
        return c
    cf, cg = _core(f), _core(g)
    if cf is None or cg is None:
        return None
    return _direct(cf, cg)


def order(inp: dict) -> dict:
    """Artan sırada Θ-sınıfı grupları döndürür: [["sqrt(n)"], ["n", "2*n"], ...]."""
    names = inp["functions"]
    funcs = {name: _parse(name) for name in names}
    groups: list[list[str]] = []
    for name in names:
        placed = False
        for gi, group in enumerate(groups):
            c = _cmp_with_cores(funcs[name], funcs[group[0]])
            if c is None:
                return {"undetermined": True, "pair": [name, group[0]]}
            if c == 0:
                group.append(name)
                placed = True
                break
            if c == -1:
                groups.insert(gi, [name])
                placed = True
                break
        if not placed:
            groups.append([name])
    return {"order": groups}


def compare(computed: dict, expected: dict) -> list[str]:
    if "order" not in expected:
        return []
    norm = lambda gs: [sorted(str(sp.simplify(_parse(x))) for x in g) for g in gs]  # noqa: E731
    if norm(expected["order"]) != norm(computed["order"]):
        return [f"order: iddia {expected['order']}, hesaplanan {computed['order']}"]
    return []
