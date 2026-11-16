"""RAM simülatörü (ders notu 2.3 ve sınav eki gösterimi).

Desteklenen satırlar (etiket "A: ..." önekiyle ya da satır sonunda "(A)" olarak verilebilir):
  R[<ifade>] = <ifade>            ifade: terim [op terim], op ∈ + - * // %
  IF <ifade> <karş> <ifade>: GOTO L | END     karş ∈ = == != < <= > >=
  GOTO L
  END
Terim: tamsayı ya da R[<ifade>] (dolaylı adresleme iç içe olabilir).
"""

import re

_TOKEN = re.compile(r"\s*(R\[|\]|//|<=|>=|==|!=|[-+*%<>=]|\d+)")
_LINE = re.compile(r"^\s*(?:([A-Za-z]\w*)\s*:(?!\s*(?:GOTO|END)\b)\s*)?(.*?)\s*(?:\(([A-Za-z]\w*)\))?\s*$")
_RESERVED = {"IF", "GOTO", "END", "HALT"}
_CMP = {"=": lambda a, b: a == b, "==": lambda a, b: a == b, "!=": lambda a, b: a != b,
        "<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, ">=": lambda a, b: a >= b}


class _Expr:
    def __init__(self, text: str):
        self.tokens = []
        pos, text = 0, text.strip()
        while pos < len(text):
            m = _TOKEN.match(text, pos)
            if not m:
                raise ValueError(f"Çözümlenemeyen ifade: {text!r} (konum {pos})")
            self.tokens.append(m.group(1))
            pos = m.end()
        self.i = 0

    def _peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def _take(self):
        tok = self._peek()
        self.i += 1
        return tok

    def term(self):
        tok = self._take()
        if tok == "-":
            inner = self.term()
            return ("neg", inner)
        if tok == "R[":
            idx = self.expr()
            if self._take() != "]":
                raise ValueError("']' bekleniyordu")
            return ("reg", idx)
        if tok is not None and tok.isdigit():
            return ("num", int(tok))
        raise ValueError(f"Terim bekleniyordu, bulunan: {tok!r}")

    def expr(self):
        left = self.term()
        if self._peek() in ("+", "-", "*", "//", "%"):
            op = self._take()
            return ("op", op, left, self.term())
        return left

    def parse(self):
        node = self.expr()
        if self._peek() is not None:
            raise ValueError(f"Fazladan sembol: {self._peek()!r}")
        return node


def _parse(text: str):
    return _Expr(text).parse()


def _eval(node, R: dict[int, int]) -> int:
    kind = node[0]
    if kind == "num":
        return node[1]
    if kind == "neg":
        return -_eval(node[1], R)
    if kind == "reg":
        return R.get(_eval(node[1], R), 0)
    _, op, a, b = node
    x, y = _eval(a, R), _eval(b, R)
    return {"+": x + y, "-": x - y, "*": x * y, "//": x // y if y else 0, "%": x % y if y else 0}[op]


def _compile(lines: list[str]):
    program, labels = [], {}
    for raw in lines:
        if not raw.strip():
            continue
        m = _LINE.match(raw)
        label, body, trailing = m.group(1), m.group(2).strip(), m.group(3)
        for lab in (label, trailing):
            if lab:
                if lab.upper() in _RESERVED:
                    raise ValueError(f"Etiket adı ayrılmış kelime olamaz: {lab}")
                labels[lab] = len(program)
        upper = body.upper()
        if upper in ("END", "HALT"):
            program.append(("end",))
        elif upper.startswith("GOTO "):
            program.append(("goto", body[5:].strip()))
        elif upper.startswith("IF "):
            cond, sep, action = body[3:].rpartition(":")
            if not sep:
                raise ValueError(f"IF satırında ':' yok: {raw!r}")
            m2 = re.match(r"(.*?)(<=|>=|==|!=|<|>|=)(.*)", cond)
            if not m2:
                raise ValueError(f"Karşılaştırma bulunamadı: {raw!r}")
            action = action.strip()
            target = None if action.upper() in ("END", "HALT") else action.upper().removeprefix("GOTO").strip()
            if target is not None and not action.upper().startswith("GOTO"):
                raise ValueError(f"IF sonrası GOTO ya da END bekleniyordu: {raw!r}")
            program.append(("if", _parse(m2.group(1)), m2.group(2), _parse(m2.group(3)), target))
        else:
            lhs, sep, rhs = body.partition("=")
            if not sep or not lhs.strip().startswith("R["):
                raise ValueError(f"Atama bekleniyordu: {raw!r}")
            target = _parse(lhs)
            if target[0] != "reg":
                raise ValueError(f"Sol taraf bir register olmalı: {raw!r}")
            program.append(("set", target[1], _parse(rhs)))
    for ins in program:
        tgt = ins[1] if ins[0] == "goto" else ins[4] if ins[0] == "if" else None
        if tgt is not None and tgt not in labels:
            raise ValueError(f"Tanımsız etiket: {tgt}")
    return program, labels


def run(inp: dict) -> dict:
    program, labels = _compile(inp["program"])
    R = {int(k): int(v) for k, v in inp.get("registers", {}).items()}
    pc, steps, limit = 0, 0, inp.get("max_steps", 100_000)
    while pc < len(program):
        ins = program[pc]
        steps += 1
        if steps > limit:
            raise ValueError(f"{limit} adımda durmadı")
        if ins[0] == "end":
            break
        if ins[0] == "goto":
            pc = labels[ins[1]]
            continue
        if ins[0] == "if":
            _, a, cmp, b, target = ins
            if _CMP[cmp](_eval(a, R), _eval(b, R)):
                if target is None:
                    break
                pc = labels[target]
                continue
        elif ins[0] == "set":
            R[_eval(ins[1], R)] = _eval(ins[2], R)
        pc += 1
    return {"registers": {str(k): v for k, v in sorted(R.items())}, "steps": steps}


def compare_run(computed: dict, expected: dict) -> list[str]:
    out = []
    for k, v in expected.get("registers", {}).items():
        got = computed["registers"].get(str(k), 0)
        if got != v:
            out.append(f"R[{k}]: iddia {v}, hesaplanan {got}")
    if "steps" in expected and expected["steps"] != computed["steps"]:
        out.append(f"steps: iddia {expected['steps']}, hesaplanan {computed['steps']}")
    return out
