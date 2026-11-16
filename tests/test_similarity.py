"""Kopya tespiti kuralları (kalibrasyon örnekleri gerçek modelle ölçülen değerlerdir)."""

import pytest

from examprep.similarity import copy_rule, data_overlap

S_ORDER = "Ordnen Sie die Funktionen f_k bezüglich ihres asymptotischen Verhaltens: n²(sin(n)+2), 2^(cos²(n)), n², 10^23·n"
S_PART = ('Das Entscheidungsproblem Partition(A, ω) lautet: "Gibt es zu einer gegebenen Menge A = {a1, a2, … aN} mit '
          'zugeordneten positiven Werten w: A → ℕ eine Partition A = A1 + A2 deren Wertesummen identisch sind?" '
          "Zeigen Sie: Partition ∈ NP")
S_KSAT = ("Reduzieren Sie die folgende 4-SAT Klausel auf eine 3-SAT Instanz unter Verwendung einer zusätzlichen "
          "Variable: x1 ∨ x2 ∨ x3 ∨ x4")

# (açıklama, kaynak, üretilen, gerçek modelin kosinüsü, kopya mı)
CASES = [
    ("aynı fonksiyonlar, sıra farklı", S_ORDER,
     "Ordnen Sie die Funktionen bezüglich ihres asymptotischen Verhaltens: 10^23·n, n², 2^(cos²(n)), n²(sin(n)+2)", 0.954, True),
    ("aynı fonksiyonlar, yeniden ifade", S_ORDER,
     "Sortieren Sie n²(sin(n)+2), 2^(cos²(n)), n² und 10^23·n nach ihrem asymptotischen Wachstum.", 0.757, True),
    ("yeni fonksiyonlar, sınavın kalıp cümlesi", S_ORDER,
     "Ordnen Sie die folgenden Funktionen bezüglich ihres asymptotischen Verhaltens: f1(n) = n·(cos(n) + 3), "
     "f2(n) = 3^(sin²(n)), f3(n) = n·log(n²), f4(n) = 10^9·n.", 0.926, False),
    ("Partition yeniden ifade", S_PART,
     "Zeigen Sie, dass Partition in NP liegt: Gegeben eine Menge A mit Werten w, gibt es eine Aufteilung in A1 "
     "und A2 mit gleicher Wertesumme?", 0.821, True),
    ("SubsetSum ∈ NP", S_PART,
     "Das Entscheidungsproblem SubsetSum(I, c) lautet: Gibt es zu einer endlichen Menge I ⊂ ℕ und einer Zahl "
     "c ∈ ℕ eine Teilmenge S ⊆ I mit Σ e = c? Zeigen Sie: SubsetSum ∈ NP.", 0.768, False),
    ("değişkenleri yeniden adlandırılmış kopya", S_KSAT, S_KSAT.replace("x", "y"), 0.977, True),
    ("yeni 5-SAT klozu", S_KSAT,
     "Wandeln Sie die Klausel ¬a ∨ b ∨ ¬c ∨ d ∨ e in eine äquivalente 3-KNF-Formel mit Hilfsvariablen um.", 0.613, False),
]


@pytest.mark.parametrize(("name", "source", "generated", "cosine", "is_copy"), CASES, ids=[c[0] for c in CASES])
def test_copy_rule_on_calibration_cases(name, source, generated, cosine, is_copy):
    n_tok, overlap = data_overlap(generated, source)
    assert (copy_rule(cosine, n_tok, overlap, high=0.95) is not None) is is_copy


def test_conceptual_questions_use_embedding_only():
    n_tok, ov = data_overlap("Was ist ein Entscheidungsproblem?", "Was versteht man unter einem Entscheidungsproblem?")
    assert n_tok < 4
    assert copy_rule(0.9, n_tok, ov, high=0.95) == "same_concept"
    assert copy_rule(0.7, n_tok, ov, high=0.95) is None
