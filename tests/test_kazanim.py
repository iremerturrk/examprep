"""Kazanım testi: üç bölümlü taslak, şık kuralları, bölüm bazlı hakem, kartlar, Anki, gönderim."""

import zipfile

import pytest
from pydantic import TypeAdapter

from examprep import cards, submissions, testgen
from examprep.analysis import AnalysisError
from examprep.models import Attempt, PerceivedDifficulty, QuestionStatus, TestFormat, TestStatus, Tier
from examprep.schemas import CardIn, CardRejectIn, GeneratedQuestionIn, JudgeIn, SubmissionIn
from test_testgen import FakeEmbedder, course_map  # noqa: F401  (fixture)


def load(adapter, raw):
    return TypeAdapter(list[adapter]).validate_python(raw)


SECTIONS = {"basic": 6, "medium": 3, "exam": 2}
SCORES = {
    Tier.basic: {"steps": 1, "input_size": 0, "concept_count": 1, "bloom_level": "remember", "est_minutes": 1},
    Tier.medium: {"steps": 4, "input_size": 4, "concept_count": 2, "bloom_level": "apply", "est_minutes": 3},
    Tier.exam: {"steps": 4, "input_size": 6, "concept_count": 1, "bloom_level": "apply", "est_minutes": 6},
}


def compose(session, m, **kw):
    return testgen.compose_kazanim_test(session, m["cid"], {**SECTIONS, **kw.pop("sections", {})}, seed=kw.pop("seed", 3), **kw)


def mc(slot, i=0, **kw):
    return {"slot_id": slot.id, "prompt": f"Frage {slot.id}-{i}: Welche Aussage über Heapsort trifft zu?",
            "answer": "B", "answer_type": "choice", "choices": ["A", "B", "C", "D"], "params": {}, **kw}


def build_ready_test(session, m):
    test = compose(session, m)
    testgen.import_generated(session, load(GeneratedQuestionIn, [mc(s) for s in test.slots]))
    testgen.verify_test(session, test.id)
    testgen.similarity_test(session, test.id, FakeEmbedder(), threshold=1.01)
    testgen.judge(session, load(JudgeIn, [{"question_id": s.current_question.id, "scores": SCORES[s.tier]}
                                          for s in test.slots]))
    testgen.finalize_test(session, test.id)
    return test


# --- Taslak


def test_sections_order_and_targets(session, course_map):
    test = compose(session, course_map)
    tiers = [s.tier for s in test.slots]
    assert test.format is TestFormat.kazanim and test.config == {"sections": SECTIONS}
    # 5 kazanımlı haritada temel bölüm 6 soru → bir kazanım iki kez
    assert tiers == [Tier.basic] * 6 + [Tier.medium] * 3 + [Tier.exam] * 2
    basic_objs = [s.objective_id for s in test.slots if s.tier is Tier.basic]
    assert len(set(basic_objs)) == 5  # önce her kazanım bir kez
    assert all(s.target_difficulty["tier"] == "basic" for s in test.slots[:6])
    exam = [s for s in test.slots if s.tier is Tier.exam]
    assert all(s.parallel_question is not None and s.parallel_question.document.doc_type.value == "exam" for s in exam)
    assert len({s.parallel_question_id for s in exam}) == 2
    assert exam[0].target_difficulty["source"] == "anchors" and exam[0].target_difficulty["tier"] == "exam"


def test_basic_section_covers_widely_before_repeating(session, course_map):
    test = compose(session, course_map, sections={"basic": 5, "medium": 0, "exam": 0})
    assert len({s.objective_id for s in test.slots}) == 5


def test_exam_section_limited_by_available_past_questions(session, course_map):
    test = compose(session, course_map, sections={"exam": 9})
    assert sum(s.tier is Tier.exam for s in test.slots) == 2  # haritada zorluklu 2 sınav sorusu var


def test_section_validation(session, course_map):
    with pytest.raises(AnalysisError, match="Bölüm boyutları"):
        compose(session, course_map, sections={"basic": -1})


# --- Şık kuralları ve hakem


def test_kazanim_requires_four_distinct_choices(session, course_map):
    slot = compose(session, course_map).slots[0]
    with pytest.raises(AnalysisError) as exc:
        testgen.import_generated(session, load(GeneratedQuestionIn, [
            {"slot_id": slot.id, "prompt": "p", "answer": "x"},
            mc(slot, choices=["A", "B", "C"]),
            mc(slot, choices=["A", "B", "B", "D"]),
        ]))
    d = exc.value.details
    assert "tam 4 şık" in d[0] and "tam 4 şık" in d[1] and "farklı" in d[2]


@pytest.mark.parametrize(("tier", "scores", "verdict"), [
    ("basic", {"steps": 1, "est_minutes": 1, "bloom_level": "understand"}, "ok"),
    ("basic", {"steps": 5, "est_minutes": 4, "bloom_level": "apply"}, "scale_down"),
    ("basic", {"steps": 1, "est_minutes": 1, "bloom_level": "evaluate"}, "scale_down"),
    ("medium", {"steps": 4, "est_minutes": 3, "bloom_level": "apply"}, "ok"),
    ("medium", {"steps": 1, "est_minutes": 1, "bloom_level": "remember"}, "scale_up"),
    ("medium", {"steps": 12, "est_minutes": 10, "bloom_level": "analyze"}, "scale_down"),
])
def test_tier_verdicts(tier, scores, verdict):
    target = testgen.BASIC_TARGET if tier == "basic" else testgen._medium_target(None)
    full = {"input_size": 0, "concept_count": 1, **scores}
    assert testgen.judge_verdict(full, target)[0] == verdict


def test_judge_quality_flags_reject(session, course_map):
    test = compose(session, course_map)
    slot = test.slots[0]
    testgen.import_generated(session, load(GeneratedQuestionIn, [mc(slot)]))
    res = testgen.judge(session, load(JudgeIn, [{"question_id": slot.current_question.id, "scores": SCORES[Tier.basic],
                                                 "single_correct": False, "comment": "B und C sind beide richtig"}]))
    assert res[0]["verdict"] == "reject" and "birden fazla doğru şık" in res[0]["issues"][0]
    assert slot.current_question is None


# --- Kartlar ve Anki


def test_cards_import_dedupe_and_test_view(session, course_map, tmp_path):
    test = build_ready_test(session, course_map)
    keys = [o.key for o in cards.objectives_of_test(session, test.id)]
    raw = [{"objective_key": k, "kind": "definition", "front": f"Was ist $O({k})$?", "back": f"**{k}**: tanım"}
           for k in keys]
    res = cards.import_cards(session, course_map["cid"], load(CardIn, raw + [raw[0]]))
    assert len(res.created) == len(keys) and len(res.skipped_approved) == 1
    listed = cards.cards_for_test(session, test.id)
    assert [c.objective_key for c in listed] == keys

    cards.reject_cards(session, load(CardRejectIn, [{"card_id": listed[0].id, "reason": "falsch"}]))
    assert len(cards.cards_for_test(session, test.id)) == len(keys) - 1
    cards.record_review(session, listed[1].id, known=True)
    assert cards.cards_for_test(session, test.id)[0].known == 1

    out = cards.export_apkg(session, test.id, tmp_path / "deck.apkg")
    assert out["cards"] == len(keys) - 1
    with zipfile.ZipFile(out["path"]) as z:
        assert "collection.anki2" in z.namelist()
    with pytest.raises(AnalysisError) as exc:
        cards.import_cards(session, course_map["cid"], load(CardIn, [{**raw[0], "objective_key": "yok"}]))
    assert "kazanım yok" in exc.value.details[0]


def test_to_anki_converts_latex_and_markdown():
    assert cards._to_anki("Ist $n^2 \\in O(n^3)$? **ja**\n$$x$$") == \
        "Ist \\(n^2 \\in O(n^3)\\)? <b>ja</b><br>\\[x\\]"


# --- Gönderim


def test_submit_scores_by_section_and_weak_objectives(session, course_map):
    test = build_ready_test(session, course_map)
    slots = test.slots
    answers = [{"slot_id": s.id, "selected": "B" if i % 3 else "A"} for i, s in enumerate(slots)]
    answers[-1]["selected"] = None  # boş bırakıldı
    out = submissions.submit(session, SubmissionIn(test_id=test.id, answers=answers, duration_s=600))
    wrong = {0, 3, 6, 9, 10}  # i % 3 == 0 → A (yanlış) + son soru boş
    assert out.total == 11 and out.score == 11 - len(wrong)
    assert out.section_scores["basic"] == {"total": 6, "correct": 4}
    assert out.section_scores["exam"]["total"] == 2
    assert {r.position for r in out.results if not r.correct} == {i + 1 for i in wrong}
    assert sum(w["wrong"] for w in out.weak_objectives) == len(wrong)
    blank = out.results[-1]
    assert blank.selected is None and not blank.correct

    submissions.set_perceived(session, blank.attempt_id, PerceivedDifficulty.hard)
    assert session.get(Attempt, blank.attempt_id).perceived_difficulty is PerceivedDifficulty.hard
    assert len(submissions.list_submissions(session, test.id)) == 1


def test_submit_validation(session, course_map):
    draft = compose(session, course_map)
    with pytest.raises(AnalysisError, match="tamamlanmış"):
        submissions.submit(session, SubmissionIn(test_id=draft.id, answers=[]))
    ready = build_ready_test(session, course_map)
    with pytest.raises(AnalysisError, match="ait olmayan"):
        submissions.submit(session, SubmissionIn(test_id=ready.id, answers=[{"slot_id": 99999, "selected": "A"}]))


def test_wrong_answers_raise_next_priority(session, course_map):
    test = build_ready_test(session, course_map)
    submissions.submit(session, SubmissionIn(test_id=test.id, answers=[{"slot_id": s.id, "selected": "A"}
                                                                       for s in test.slots]))
    rates = testgen._wrong_rates(session, course_map["cid"])
    assert rates and all(r == 1.0 for r in rates.values())


def test_finalized_kazanim_test_accepted_questions(session, course_map):
    test = build_ready_test(session, course_map)
    assert test.status is TestStatus.ready
    assert all(s.current_question.status is QuestionStatus.accepted for s in test.slots)


def test_exam_section_prefers_substantial_questions(session, course_map):
    # course_map'te sınav sorusu 1: 6 puan, sınav sorusu 2: puansız → tek slotluk bölümde 6 puanlık seçilmeli
    for seed in range(5):
        test = testgen.compose_kazanim_test(session, course_map["cid"], {"basic": 0, "medium": 0, "exam": 1}, seed=seed)
        assert test.slots[0].parallel_question.points == 6


def test_exam_tier_time_target_halved_for_multiple_choice():
    target = {"steps": 7, "input_size": 7, "est_minutes": 13.2, "bloom_level": 4, "tier": "exam"}
    scores = {"steps": 6, "input_size": 5, "concept_count": 2, "bloom_level": "analyze", "est_minutes": 4}
    assert testgen.judge_verdict(scores, target)[0] == "ok"  # 4 / (13.2 · 0.5) ≈ 0.61
    assert testgen.judge_verdict({**scores, "est_minutes": 2}, target)[0] == "scale_up"
