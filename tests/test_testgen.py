from datetime import datetime, timedelta

import numpy as np
import pytest
from pydantic import TypeAdapter, ValidationError

from examprep import analysis, testgen
from examprep.analysis import AnalysisError
from examprep.models import (
    Attempt,
    GeneratedQuestion,
    LearningObjective,
    QuestionKind,
    QuestionStatus,
    SlotType,
    Test,
    TestSlot,
    TestStatus,
)
from examprep.schemas import (
    ArchetypeIn,
    GeneratedQuestionIn,
    JudgeIn,
    ObjectiveIn,
    SourceQuestionIn,
    TopicNode,
)

DIFF = {"steps": 4, "input_size": 6, "concept_count": 1, "bloom_level": "apply", "est_minutes": 6, "edge_cases": []}
EXAM_Q1 = "Sortieren Sie das Array [5, 3, 8, 1] mit MergeSort und zeigen Sie alle Schritte."


class FakeEmbedder:
    """Kelime torbası: aynı kelimeler → yüksek benzerlik. Model indirmez."""

    name = "fake-bow"

    def encode(self, texts):
        vecs = np.zeros((len(texts), 64), dtype=np.float32)
        for i, t in enumerate(texts):
            for w in t.lower().split():
                vecs[i, hash(w) % 64] += 1
        return vecs


def load(adapter, raw):
    return TypeAdapter(list[adapter]).validate_python(raw)


def arch(key, obj, angle, origin="model", refs=()):
    return {"key": key, "objective_key": obj, "skill": f"{key} becerisi", "angle": angle,
            "variation_axes": {"algoritma": ["merge", "quick", "heap"], "boyut": ["4", "6"]},
            "origin": origin, "source_questions": [{"document_id": d, "label": l} for d, l in refs]}


@pytest.fixture
def course_map(session, course, course_docs):
    cid, exam, hw = course.id, course_docs["exam"], course_docs["homework"]
    analysis.import_topics(session, cid, load(TopicNode, [{"key": "t", "name": "T"}]))
    analysis.import_objectives(session, cid, load(ObjectiveIn, [
        {"key": f"o{i}", "topic_key": "t", "text": f"Kazanım {i}", "bloom_level": "apply"} for i in range(1, 6)]))
    analysis.import_questions(session, cid, load(SourceQuestionIn, [
        {"document_id": exam, "label": "1", "page_no": 1, "text": EXAM_Q1, "points": 6, "difficulty": DIFF},
        {"document_id": exam, "label": "2", "page_no": 2, "text": "Erklären Sie Quicksort.", "difficulty": DIFF},
        {"document_id": hw, "label": "1", "page_no": 1, "text": "Heapsort Übung", "solution": "..."},
    ]))
    analysis.import_archetypes(session, cid, load(ArchetypeIn, [
        arch("o1.trace", "o1", "trace", "exam", [(exam, "1")]), arch("o1.edge", "o1", "edge_case"),
        arch("o2.explain", "o2", "explain", "exam", [(exam, "2")]), arch("o2.compare", "o2", "compare"),
        arch("o3.compute", "o3", "compute", "homework", [(hw, "1")]), arch("o3.trace", "o3", "trace"),
        arch("o4.trace", "o4", "trace"), arch("o4.explain", "o4", "explain"),
        arch("o5.design", "o5", "design"), arch("o5.find", "o5", "find_error"),
    ]))
    analysis.compute_profile(session, cid)
    return {"cid": cid, "exam": exam, "hw": hw}


def compose(session, m, **kw):
    return testgen.compose_test(session, m["cid"], **{"size": 10, "seed": 1, **kw})


# --- Taslak


def test_compose_structure_and_quotas(session, course_map):
    test = compose(session, course_map)
    types = [s.slot_type for s in test.slots]
    assert len(test.slots) == 10
    assert types.count(SlotType.past) == 2  # %20
    assert all(t in (SlotType.new, SlotType.past) for t in types)  # ilk test: her şey yeni
    assert [s.position for s in test.slots] == list(range(1, 11))
    per_obj = {}
    for s in test.slots:
        if s.slot_type is not SlotType.past:
            per_obj[s.objective_id] = per_obj.get(s.objective_id, 0) + 1
    assert max(per_obj.values()) <= testgen.MAX_PER_OBJECTIVE
    past = [s for s in test.slots if s.slot_type is SlotType.past]
    assert all(s.source_question_id for s in past)
    assert len({s.source_question_id for s in past}) == 2


def test_compose_is_deterministic_for_seed(session, course_map):
    a = compose(session, course_map, seed=42)
    b = compose(session, course_map, seed=42)
    sig = lambda t: [(s.slot_type, s.objective_id, s.archetype_id, s.source_question_id) for s in t.slots]  # noqa: E731
    assert sig(a) == sig(b)


def test_anchors_and_target_difficulty(session, course_map):
    test = compose(session, course_map)
    o1 = [s for s in test.slots if s.objective.key == "o1" and s.slot_type is not SlotType.past]
    if o1:
        assert o1[0].anchor_ids and o1[0].target_difficulty["source"] == "anchors"
        assert o1[0].target_difficulty["steps"] == 4
    o4 = [s for s in test.slots if s.objective.key == "o4"]
    if o4:
        assert o4[0].target_difficulty["source"] == "course_profile"


def test_small_test_has_no_past_slots(session, course_map):
    test = testgen.compose_test(session, course_map["cid"], size=2, seed=3)
    assert all(s.slot_type is not SlotType.past for s in test.slots)


def test_size_validation_and_empty_map(session, course):
    with pytest.raises(AnalysisError, match="Kalıbı olan kazanım yok"):
        testgen.compose_test(session, course.id)
    with pytest.raises(AnalysisError, match="1 ile 40"):
        testgen.compose_test(session, course.id, size=0)


# --- Öncelik


def _fake_ready_test(session, cid, objective, created, archetype=None, past_question=None):
    t = Test(course_id=cid, seed=0, size=1, status=TestStatus.ready, created_at=created)
    t.slots.append(TestSlot(position=1, slot_type=SlotType.past if past_question else SlotType.new,
                            objective=objective, archetype=archetype or objective.archetypes[0],
                            source_question=past_question))
    session.add(t)
    session.commit()
    return t


def test_priorities_new_vs_review(session, course_map):
    o1 = session.query(LearningObjective).filter_by(key="o1").one()
    now = datetime(2026, 12, 1)
    _fake_ready_test(session, course_map["cid"], o1, now - timedelta(days=14))
    pri = {o.key: (p, new) for o, p, new in testgen.objective_priorities(session, course_map["cid"], now)}
    assert pri["o1"] == (pytest.approx(o1.effective_weight * 3), False)  # 1 + 14/7
    assert pri["o4"] == (pytest.approx(1.0 * testgen.NEW_BOOST), True)
    later = {o.key: p for o, p, _ in testgen.objective_priorities(session, course_map["cid"], now + timedelta(days=60))}
    assert later["o1"] == pytest.approx(o1.effective_weight * 5)  # en fazla 5


def test_wrong_answers_raise_priority(session, course_map):
    o4 = session.query(LearningObjective).filter_by(key="o4").one()
    now = datetime(2026, 12, 1)
    t = _fake_ready_test(session, course_map["cid"], o4, now)
    q = GeneratedQuestion(archetype=o4.archetypes[0], slot=t.slots[0], prompt="p", answer="a",
                          status=QuestionStatus.accepted)
    session.add_all([q, Attempt(question=q, correct=False), Attempt(question=q, correct=True)])
    session.commit()
    pri = {o.key: p for o, p, _ in testgen.objective_priorities(session, course_map["cid"], now)}
    assert pri["o4"] == pytest.approx(1.0 * 1 * 1.5)


def test_recent_past_questions_not_repeated(session, course_map):
    o1 = session.query(LearningObjective).filter_by(key="o1").one()
    sq = o1.archetypes[0].source_questions[0]
    _fake_ready_test(session, course_map["cid"], o1, datetime(2026, 11, 1), o1.archetypes[0], past_question=sq)
    for seed in range(5):
        test = compose(session, course_map, seed=seed)
        assert sq.id not in {s.source_question_id for s in test.slots}


# --- İçe aktarma


def _first(test, slot_type):
    return next(s for s in test.slots if s.slot_type is slot_type)


def gen_item(slot, **kw):
    return {"slot_id": slot.id, "prompt": "Sortieren Sie [9, 2, 7] mit Heapsort.", "answer": "2, 7, 9",
            "params": {"algoritma": "heap"}, **kw}


def test_import_validates_axes_and_past_slots(session, course_map):
    test = compose(session, course_map)
    gen, past = _first(test, SlotType.new), _first(test, SlotType.past)
    with pytest.raises(AnalysisError) as exc:
        testgen.import_generated(session, load(GeneratedQuestionIn, [
            gen_item(gen, params={"algoritma": "bubble"}),
            gen_item(gen, params={"renk": "mavi"}),
            {"slot_id": past.id, "answer": "x", "params": {"algoritma": "merge"}},
            {"slot_id": 99999, "answer": "x"},
        ]))
    joined = " | ".join(exc.value.details)
    assert "kapsam kilidi" in joined and "bilinmeyen eksen" in joined
    assert "çıkmış soru slotunda" in joined and "Slot bulunamadı" in joined


def test_past_slot_uses_source_text(session, course_map):
    test = compose(session, course_map)
    past = _first(test, SlotType.past)
    testgen.import_generated(session, load(GeneratedQuestionIn, [{"slot_id": past.id, "answer": "Lösung"}]))
    q = past.current_question
    assert q.kind is QuestionKind.past and q.prompt == past.source_question.text


def test_choice_schema_rules():
    with pytest.raises(ValidationError, match="seçeneklerden"):
        GeneratedQuestionIn(slot_id=1, prompt="p", answer="d", answer_type="choice", choices=["a", "b"])
    with pytest.raises(ValidationError, match="sayı"):
        GeneratedQuestionIn(slot_id=1, prompt="p", answer="vier", answer_type="numeric")
    assert GeneratedQuestionIn(slot_id=1, prompt="p", answer="7/4", answer_type="numeric")


def test_reimport_replaces_and_attempt_limit(session, course_map):
    test = compose(session, course_map)
    slot = _first(test, SlotType.new)
    for _ in range(testgen.MAX_ATTEMPTS_PER_SLOT):
        testgen.import_generated(session, load(GeneratedQuestionIn, [gen_item(slot)]))
    assert [q.status for q in slot.questions][:-1] == [QuestionStatus.rejected] * 2
    with pytest.raises(AnalysisError) as exc:
        testgen.import_generated(session, load(GeneratedQuestionIn, [gen_item(slot)]))
    assert "en fazla" in exc.value.details[0]


# --- Kapılar ve tamamlama


GOOD_CHECK = {"checker": "knapsack.solve",
              "input": {"items": [{"name": "a", "w": 3, "g": 2}, {"name": "b", "w": 2, "g": 1}], "M": 2},
              "expected": {"value": 3}}
BAD_CHECK = {**GOOD_CHECK, "expected": {"value": 5}}
SCORES_OK = {"steps": 4, "input_size": 6, "concept_count": 1, "bloom_level": "apply", "est_minutes": 6}


def test_full_pipeline(session, course_map):
    test = compose(session, course_map, size=5, seed=7)
    gens = [s for s in test.slots if s.slot_type is not SlotType.past]
    past = [s for s in test.slots if s.slot_type is SlotType.past]
    assert len(gens) == 4 and len(past) == 1
    items = [
        gen_item(gens[0], check=GOOD_CHECK),  # geçer
        gen_item(gens[1], check=BAD_CHECK),  # doğrulamada reddedilir
        gen_item(gens[2], prompt=EXAM_Q1),  # kaynak sorunun kopyası → benzerlikte reddedilir
        gen_item(gens[3], prompt="Erklären Sie, warum Heapsort in-place arbeitet.", params={}),  # kavramsal
        {"slot_id": past[0].id, "answer": "Musterlösung"},
    ]
    testgen.import_generated(session, load(GeneratedQuestionIn, items))

    v = {r["slot_id"]: r for r in testgen.verify_test(session, test.id)}
    assert v[gens[0].id]["verification"] == "passed"
    assert v[gens[1].id]["status"] == "rejected" and "hesaplanan 3" in v[gens[1].id]["reject_reason"]
    assert v[gens[3].id]["verification"] == "unverified"

    sims = {r["slot_id"]: r for r in testgen.similarity_test(session, test.id, FakeEmbedder(), threshold=0.85)}
    assert sims[gens[2].id]["status"] == "rejected" and sims[gens[2].id]["score"] >= 0.99
    assert past[0].id not in sims  # çıkmış sorular benzerlik kontrolünden muaf
    assert gens[1].id not in sims  # reddedilenler atlanır

    live = [gens[0], gens[3], past[0]]
    res = testgen.judge(session, load(JudgeIn, [
        {"question_id": gens[0].current_question.id, "scores": SCORES_OK},
        {"question_id": gens[3].current_question.id, "scores": {**SCORES_OK, "steps": 20}},
        {"question_id": past[0].current_question.id, "scores": {**SCORES_OK, "bloom_level": "create"}},
    ]))
    verdicts = {r["slot_id"]: r["verdict"] for r in res}
    assert verdicts[gens[0].id] == "ok"
    assert gens[3].current_question is None  # scale_down → reddedildi
    assert verdicts[past[0].id] == "reject" and past[0].current_question.status is QuestionStatus.accepted

    with pytest.raises(AnalysisError, match="Kabul edilmiş sorusu olmayan"):
        testgen.finalize_test(session, test.id)
    out = testgen.finalize_test(session, test.id, allow_partial=True)
    assert out.status is TestStatus.ready and len(out.slots) == len(live) - 1  # gens[0] + past
    assert [s.position for s in out.slots] == [1, 2]
    with pytest.raises(AnalysisError, match="zaten"):
        testgen.finalize_test(session, test.id)
    with pytest.raises(AnalysisError) as exc:
        testgen.import_generated(session, load(GeneratedQuestionIn, [gen_item(gens[0])]))
    assert "tamamlanmış" in exc.value.details[0]


def test_finalized_test_changes_next_composition(session, course_map):
    first = compose(session, course_map, size=4, seed=2)
    for s in first.slots:
        testgen.import_generated(session, load(GeneratedQuestionIn, [
            {"slot_id": s.id, "answer": "x"} if s.slot_type is SlotType.past else gen_item(s, params={})]))
    testgen.verify_test(session, first.id)
    testgen.similarity_test(session, first.id, FakeEmbedder(), threshold=1.01)
    testgen.judge(session, load(JudgeIn, [{"question_id": s.current_question.id, "scores": SCORES_OK}
                                          for s in first.slots]))
    testgen.finalize_test(session, first.id)
    tested = {s.objective_id for s in first.slots}
    second = compose(session, course_map, size=4, seed=2)
    review = [s for s in second.slots if s.slot_type is SlotType.review]
    assert all(s.objective_id in tested for s in review)
    assert all(s.objective_id not in tested for s in second.slots if s.slot_type is SlotType.new)


def test_judge_verdict_rules():
    target = {"steps": 4, "input_size": 6, "est_minutes": 6, "bloom_level": 3}
    ok = {"steps": 5, "input_size": 6, "est_minutes": 7, "bloom_level": "apply", "concept_count": 1}
    assert testgen.judge_verdict(ok, target)[0] == "ok"
    assert testgen.judge_verdict({**ok, "steps": 1, "input_size": 2}, target)[0] == "scale_up"
    assert testgen.judge_verdict({**ok, "est_minutes": 20}, target)[0] == "scale_down"
    assert testgen.judge_verdict({**ok, "bloom_level": "create"}, target)[0] == "reject"
    assert testgen.judge_verdict({**ok, "input_size": 9}, {**target, "input_size": 0})[0] == "scale_down"
    assert testgen.judge_verdict(ok, None)[0] == "ok"


def test_discard_only_drafts(session, course_map):
    test = compose(session, course_map)
    testgen.discard_test(session, test.id)
    assert session.get(Test, test.id) is None
