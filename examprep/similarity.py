"""Üretilen soruların kaynak (çıkmış) sorulara benzerliği: kopya tespiti.

Embedding benzerliği tek başına yanıltıcı: sınavın kalıp cümlesini ("Ordnen Sie die
Funktionen … bezüglich ihres asymptotischen Verhaltens") kullanan ama verisi tamamen yeni
bir soru yüksek skor alırken, aynı verinin yeniden ifade edilmiş hali düşük skor alabilir.
Bu yüzden iki sinyal birlikte kullanılır:
  - anlamsal benzerlik (embedding kosinüsü)
  - veri örtüşmesi: sorudaki sayı / formül / değişken / matematik sembollerinin kaynak
    sorudaki oranı
Kopya sayılır:
  1. kosinüs ≥ yüksek eşik (varsayılan 0.95)              → neredeyse aynı metin
  2. kosinüs ≥ 0.70 ve veri örtüşmesi ≥ 0.60             → aynı veri, yeniden ifade
  3. veri sembolü < 4 (kavramsal soru) ve kosinüs ≥ 0.85  → aynı kavramsal soru

Kaynak soruların embedding'leri bir kez hesaplanıp SourceQuestion.embedding'e yazılır.
Embedder değiştirilebilir (testlerde sahte embedder kullanılır, model indirilmez).
"""

import re
from collections import Counter
from typing import Protocol

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from examprep import config
from examprep.models import SourceDocument, SourceQuestion


class Embedder(Protocol):
    name: str

    def encode(self, texts: list[str]) -> np.ndarray: ...


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str | None = None):
        self.name = model_name or config.EMBEDDING_MODEL
        self._model = None

    def encode(self, texts: list[str]) -> np.ndarray:
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # ağır import, yalnız gerektiğinde

            self._model = SentenceTransformer(self.name)
        return np.asarray(self._model.encode(texts, normalize_embeddings=True), dtype=np.float32)


_default: Embedder | None = None


def default_embedder() -> Embedder:
    global _default
    if _default is None:
        _default = SentenceTransformerEmbedder()
    return _default


def _normalize(v: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.where(norms == 0, 1, norms)


def source_matrix(session: Session, course_id: int, embedder: Embedder) -> tuple[list[SourceQuestion], np.ndarray]:
    """Dersin kaynak sorularının embedding matrisini döndürür; eksik olanları hesaplayıp önbelleğe yazar."""
    questions = list(session.scalars(
        select(SourceQuestion).join(SourceDocument).where(SourceDocument.course_id == course_id)
        .order_by(SourceQuestion.id)
    ))
    stale = [q for q in questions if q.embedding is None or q.embedding_model != embedder.name]
    if stale:
        vectors = _normalize(embedder.encode([q.text for q in stale]))
        for q, v in zip(stale, vectors):
            q.embedding = v.astype(np.float32).tobytes()
            q.embedding_model = embedder.name
        session.flush()
    if not questions:
        return [], np.zeros((0, 0), dtype=np.float32)
    matrix = np.stack([np.frombuffer(q.embedding, dtype=np.float32) for q in questions])
    return questions, matrix


MID_EMBEDDING = 0.70
DATA_OVERLAP = 0.60
CONCEPTUAL_TOKENS = 4
CONCEPTUAL_EMBEDDING = 0.85

_DATA_TOKEN = re.compile(
    r"\d+|[A-Za-z]\d+|[A-Za-z]_\w+|\b(?:sin|cos|log|sqrt|exp|max|min)\b"
    r"|[²³√∑Σ∏∨∧¬⊆⊂∈∉∅≤≥≠→⇔ℕ∩∪]|(?<![A-Za-zÄÖÜäöüß])[A-Za-z](?![A-Za-zÄÖÜäöüß])"
)


def data_tokens(text: str) -> Counter:
    return Counter(t.lower() for t in _DATA_TOKEN.findall(text))


def data_overlap(generated: str, source: str) -> tuple[int, float]:
    """(üretilen sorudaki veri sembolü sayısı, bunların kaynakta da bulunan oranı)."""
    g, s = data_tokens(generated), data_tokens(source)
    n = sum(g.values())
    return n, (sum((g & s).values()) / n if n else 0.0)


def copy_rule(cosine: float, n_tokens: int, overlap: float, high: float) -> str | None:
    if cosine >= high:
        return "near_identical"
    if n_tokens >= CONCEPTUAL_TOKENS and cosine >= MID_EMBEDDING and overlap >= DATA_OVERLAP:
        return "same_data"
    if n_tokens < CONCEPTUAL_TOKENS and cosine >= CONCEPTUAL_EMBEDDING:
        return "same_concept"
    return None


def assess(session: Session, course_id: int, texts: list[str], embedder: Embedder | None = None,
           high: float | None = None) -> list[dict]:
    """Her metin için kopya değerlendirmesi.

    {score: en yüksek kosinüs, ref, overlap, data_tokens, too_similar, rule, source_question_id, model}
    Kopya varsa rapor o kaynak soruya göre verilir.
    """
    embedder = embedder or default_embedder()
    high = config.SIMILARITY_THRESHOLD if high is None else high
    sources, matrix = source_matrix(session, course_id, embedder)
    out = []
    if not sources:
        return [{"score": 0.0, "source_question_id": None, "ref": None, "overlap": 0.0, "data_tokens": 0,
                 "too_similar": False, "rule": None, "model": embedder.name, "threshold": high} for _ in texts]
    scores = _normalize(embedder.encode(texts)) @ matrix.T
    for text, row in zip(texts, scores):
        best, copy = None, None
        for i, q in enumerate(sources):
            cos = float(row[i])
            n_tok, ov = data_overlap(text, q.text)
            rule = copy_rule(cos, n_tok, ov, high)
            cand = {"score": round(cos, 4), "source_question_id": q.id, "ref": f"{q.document_id}:{q.label}",
                    "overlap": round(ov, 3), "data_tokens": n_tok, "rule": rule}
            if rule and (copy is None or cos > copy["score"]):
                copy = cand
            if best is None or cos > best["score"]:
                best = cand
        result = copy or best
        result.update(too_similar=copy is not None, model=embedder.name, threshold=high)
        out.append(result)
    return out
