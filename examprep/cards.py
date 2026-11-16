"""Kazanım kartları: içe aktarma, teste göre listeleme, tekrar kaydı ve Anki (.apkg) dışa aktarma."""

import hashlib
import re
from pathlib import Path

import genanki
from sqlalchemy import select
from sqlalchemy.orm import Session

from examprep.analysis import AnalysisError, _by_key, _require_course
from examprep.models import CardReview, Flashcard, LearningObjective, Test
from examprep.schemas import CardIn, CardOut, CardRejectIn, ImportResult

MAX_CARDS_PER_OBJECTIVE = 6


def import_cards(session: Session, course_id: int, items: list[CardIn]) -> ImportResult:
    _require_course(session, course_id)
    objectives = _by_key(session, LearningObjective, course_id)
    errors = [f"[{n}] kazanım yok: {c.objective_key}" for n, c in enumerate(items) if c.objective_key not in objectives]
    if errors:
        raise AnalysisError("Kartlar içe aktarılamadı", errors)
    result = ImportResult()
    for c in items:
        obj = objectives[c.objective_key]
        existing = {(x.front.strip().lower()) for x in obj.cards if x.active}
        if c.front.strip().lower() in existing:
            result.skipped_approved.append(f"{c.objective_key}: aynı ön yüz zaten var")
            continue
        if sum(x.active for x in obj.cards) >= MAX_CARDS_PER_OBJECTIVE:
            result.skipped_approved.append(f"{c.objective_key}: en fazla {MAX_CARDS_PER_OBJECTIVE} kart")
            continue
        card = Flashcard(objective=obj, kind=c.kind, front=c.front, back=c.back)
        session.add(card)
        session.flush()
        result.created.append(str(card.id))
    session.commit()
    return result


def reject_cards(session: Session, items: list[CardRejectIn]) -> list[dict]:
    out = []
    for item in items:
        card = session.get(Flashcard, item.card_id)
        if card is None:
            raise AnalysisError(f"Kart bulunamadı: {item.card_id}")
        card.active, card.reject_reason = False, item.reason
        out.append({"card_id": card.id, "active": False})
    session.commit()
    return out


def _card_out(c: Flashcard) -> CardOut:
    return CardOut(id=c.id, objective_key=c.objective.key, objective_text=c.objective.text, kind=c.kind,
                   front=c.front, back=c.back, known=sum(r.known for r in c.reviews),
                   unknown=sum(not r.known for r in c.reviews))


def objectives_of_test(session: Session, test_id: int) -> list[LearningObjective]:
    test = session.get(Test, test_id)
    if test is None:
        raise AnalysisError(f"Test bulunamadı: {test_id}")
    seen, out = set(), []
    for slot in sorted(test.slots, key=lambda s: s.position):
        if slot.objective_id not in seen:
            seen.add(slot.objective_id)
            out.append(slot.objective)
    return out


def cards_for_test(session: Session, test_id: int) -> list[CardOut]:
    """Testin ölçtüğü kazanımların aktif kartları (test sırasıyla)."""
    return [_card_out(c) for o in objectives_of_test(session, test_id) for c in o.cards if c.active]


def list_cards(session: Session, course_id: int) -> list[CardOut]:
    _require_course(session, course_id)
    cards = session.scalars(select(Flashcard).join(LearningObjective)
                            .where(LearningObjective.course_id == course_id, Flashcard.active.is_(True))
                            .order_by(Flashcard.id)).all()
    return [_card_out(c) for c in cards]


def record_review(session: Session, card_id: int, known: bool) -> None:
    card = session.get(Flashcard, card_id)
    if card is None:
        raise AnalysisError(f"Kart bulunamadı: {card_id}")
    card.reviews.append(CardReview(known=known))
    session.commit()


# --- Anki ---

_MODEL_ID = 1_607_392_319  # sabit: Anki aynı not tipini tanısın
_MODEL = genanki.Model(
    _MODEL_ID,
    "ExamPrep Kazanım Kartı",
    fields=[{"name": "Front"}, {"name": "Back"}, {"name": "Kazanim"}, {"name": "CardId"}],
    templates=[{
        "name": "Kart",
        "qfmt": "<div class='front'>{{Front}}</div>",
        "afmt": "{{FrontSide}}<hr id='answer'><div class='back'>{{Back}}</div><div class='obj'>{{Kazanim}}</div>",
    }],
    css=(".card{font-family:-apple-system,Helvetica,Arial,sans-serif;font-size:20px;text-align:left;"
         "color:#1f2328;background:#fff;line-height:1.5;padding:12px}"
         ".back{color:#1f2328}.obj{margin-top:14px;font-size:13px;color:#6e7781}"),
)


def _to_anki(text: str) -> str:
    """Markdown/LaTeX → Anki HTML: $$..$$ → \\[..\\], $..$ → \\(..\\), **x** → <b>, satır sonları."""
    text = re.sub(r"\$\$(.+?)\$\$", r"\\[\1\\]", text, flags=re.S)
    text = re.sub(r"(?<!\\)\$(.+?)(?<!\\)\$", r"\\(\1\\)", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text.replace("\n", "<br>")


def _stable_id(name: str) -> int:
    return int(hashlib.sha1(name.encode()).hexdigest()[:8], 16)


def export_apkg(session: Session, test_id: int, path: Path) -> dict:
    test = session.get(Test, test_id)
    if test is None:
        raise AnalysisError(f"Test bulunamadı: {test_id}")
    deck_name = f"ExamPrep::{test.course.name}::Test {test.id}"
    deck = genanki.Deck(_stable_id(deck_name), deck_name)
    n = 0
    for o in objectives_of_test(session, test_id):
        for c in o.cards:
            if not c.active:
                continue
            note = genanki.Note(model=_MODEL, fields=[_to_anki(c.front), _to_anki(c.back), _to_anki(o.text), str(c.id)],
                                guid=genanki.guid_for(f"examprep-card-{c.id}"), tags=[o.key.replace(" ", "_")])
            deck.add_note(note)
            n += 1
    if n == 0:
        raise AnalysisError("Bu testin kazanımları için kart yok")
    path.parent.mkdir(parents=True, exist_ok=True)
    genanki.Package(deck).write_to_file(str(path))
    return {"path": str(path), "cards": n, "deck": deck_name}
