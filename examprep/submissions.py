"""Test çözme: gönderim, puanlama, sonuç ve algılanan zorluk geri bildirimi."""

from collections import Counter, defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from examprep.analysis import AnalysisError
from examprep.models import Attempt, PerceivedDifficulty, Test, TestStatus, TestSubmission
from examprep.schemas import QuestionResultOut, SubmissionIn, SubmissionOut


def _normalize(answer: str | None) -> str:
    return " ".join((answer or "").split()).casefold()


def submit(session: Session, data: SubmissionIn) -> SubmissionOut:
    test = session.get(Test, data.test_id)
    if test is None:
        raise AnalysisError(f"Test bulunamadı: {data.test_id}")
    if test.status is not TestStatus.ready:
        raise AnalysisError("Yalnızca tamamlanmış testler çözülebilir")
    given = {a.slot_id: a.selected for a in data.answers}
    unknown = set(given) - {s.id for s in test.slots}
    if unknown:
        raise AnalysisError("Teste ait olmayan slotlar", sorted(unknown))

    sub = TestSubmission(test=test, score=0, total=len(test.slots), duration_s=data.duration_s)
    session.add(sub)
    sections: dict[str, Counter] = defaultdict(Counter)
    for slot in test.slots:
        q = slot.current_question
        selected = given.get(slot.id)
        correct = selected is not None and _normalize(selected) == _normalize(q.answer)
        sub.attempts.append(Attempt(question=q, correct=correct, selected=selected))
        tier = slot.tier.value if slot.tier else "all"
        sections[tier]["total"] += 1
        sections[tier]["correct"] += correct
        sub.score += correct
    sub.section_scores = {k: dict(v) for k, v in sections.items()}
    session.commit()
    return submission_out(session, sub.id)


def submission_out(session: Session, submission_id: int) -> SubmissionOut:
    sub = session.get(TestSubmission, submission_id)
    if sub is None:
        raise AnalysisError(f"Gönderim bulunamadı: {submission_id}")
    by_question = {a.question_id: a for a in sub.attempts}
    results, per_obj = [], defaultdict(Counter)
    for slot in sub.test.slots:
        q = slot.current_question
        a = by_question.get(q.id)
        if a is None:
            continue
        o = slot.objective
        per_obj[(o.key, o.text)]["total"] += 1
        per_obj[(o.key, o.text)]["wrong"] += not a.correct
        results.append(QuestionResultOut(
            position=slot.position, tier=slot.tier, slot_id=slot.id, question_id=q.id, attempt_id=a.id,
            prompt=q.prompt, choices=q.choices, selected=a.selected, answer=q.answer, correct=a.correct,
            explanation=q.explanation, objective_key=o.key, objective_text=o.text,
            perceived_difficulty=a.perceived_difficulty.value if a.perceived_difficulty else None))
    weak = sorted(({"key": k, "text": t, "wrong": c["wrong"], "total": c["total"]}
                   for (k, t), c in per_obj.items() if c["wrong"]), key=lambda x: (-x["wrong"], x["key"]))
    return SubmissionOut(id=sub.id, test_id=sub.test_id, submitted_at=sub.submitted_at, score=sub.score,
                         total=sub.total, section_scores=sub.section_scores, duration_s=sub.duration_s,
                         results=results, weak_objectives=weak)


def list_submissions(session: Session, test_id: int) -> list[SubmissionOut]:
    ids = session.scalars(select(TestSubmission.id).where(TestSubmission.test_id == test_id)
                          .order_by(TestSubmission.id)).all()
    return [submission_out(session, i).model_copy(update={"results": []}) for i in ids]


def set_perceived(session: Session, attempt_id: int, value: PerceivedDifficulty | None) -> None:
    attempt = session.get(Attempt, attempt_id)
    if attempt is None:
        raise AnalysisError(f"Deneme bulunamadı: {attempt_id}")
    attempt.perceived_difficulty = value
    session.commit()
