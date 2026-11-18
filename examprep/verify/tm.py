"""Deterministik Turing makinesi simülasyonu (VL2 gösterimi)."""

from fractions import Fraction
from itertools import product

MOVES = {"R": 1, "→": 1, "L": -1, "←": -1, "N": 0, "↓": 0, "S": 0}


def _machine(inp: dict) -> tuple[dict, dict]:
    delta = {}
    for state, read, nxt, write, move in inp["transitions"]:
        if move not in MOVES:
            raise ValueError(f"Bilinmeyen hareket: {move}")
        if (state, read) in delta:
            raise ValueError(f"Deterministik değil: ({state}, {read}) için birden fazla geçiş")
        delta[(state, read)] = (nxt, write, MOVES[move])
    cfg = {
        "start": inp.get("start", "I"),
        "accept": set(inp.get("accept", ["A"])),
        "reject": set(inp.get("reject", ["R"])),
        "blank": inp.get("blank", "_"),
        "max_steps": inp.get("max_steps", 100_000),
    }
    return delta, cfg


def _simulate(delta: dict, cfg: dict, word: str, head: int = 0) -> dict:
    blank = cfg["blank"]
    tape = {i: c for i, c in enumerate(word)}
    state, steps = cfg["start"], 0
    while state not in cfg["accept"] and state not in cfg["reject"]:
        key = (state, tape.get(head, blank))
        if key not in delta:  # geçiş yoksa makine durur ve reddeder
            break
        state, write, move = delta[key]
        tape[head] = write
        head += move
        steps += 1
        if steps > cfg["max_steps"]:
            raise ValueError(f"{cfg['max_steps']} adımda durmadı")
    cells = [i for i, c in tape.items() if c != blank]
    content = "".join(tape.get(i, blank) for i in range(min(cells), max(cells) + 1)) if cells else ""
    return {"final_state": state, "accepted": state in cfg["accept"], "tape": content,
            "steps": steps, "head": head}


def run(inp: dict) -> dict:
    delta, cfg = _machine(inp)
    words = inp["inputs"] if "inputs" in inp else [inp["input"]]
    results = [_simulate(delta, cfg, w, inp.get("head", 0)) for w in words]
    return {"runs": dict(zip(words, results))} if "inputs" in inp else results[0]


def compare_run(computed: dict, expected: dict) -> list[str]:
    if "runs" in computed:
        out = []
        for word, exp in expected.get("runs", {}).items():
            if word not in computed["runs"]:
                out.append(f"{word}: hesaplanmadı")
                continue
            out += [f"{word}: {m}" for m in compare_run(computed["runs"][word], exp)]
        return out
    return [f"{k}: iddia {v!r}, hesaplanan {computed[k]!r}"
            for k, v in expected.items() if k in computed and computed[k] != v]


def runtime(inp: dict) -> dict:
    """Σ^N'deki tüm girdiler için adım sayısının max / min / uniform ortalaması."""
    delta, cfg = _machine(inp)
    alphabet, N = inp.get("alphabet", ["0", "1"]), inp["N"]
    if len(alphabet) ** N > 200_000:
        raise ValueError("Girdi uzayı çok büyük; daha küçük N seçin")
    steps = [_simulate(delta, cfg, "".join(w))["steps"] for w in product(alphabet, repeat=N)]
    av = Fraction(sum(steps), len(steps))
    return {"wc": max(steps), "bc": min(steps), "av": str(av), "av_float": float(av)}


def compare_runtime(computed: dict, expected: dict) -> list[str]:
    out = []
    for k in ("wc", "bc"):
        if k in expected and expected[k] != computed[k]:
            out.append(f"{k}: iddia {expected[k]}, hesaplanan {computed[k]}")
    if "av" in expected and abs(float(Fraction(str(expected["av"]))) - computed["av_float"]) > 1e-9:
        out.append(f"av: iddia {expected['av']}, hesaplanan {computed['av']}")
    return out
