import pytest
from pydantic import TypeAdapter, ValidationError

from examprep import analysis
from examprep.analysis import AnalysisError
from examprep.models import (
    ArchetypeOrigin,
    LearningObjective,
    QuestionArchetype,
    SourceQuestion,
    Topic,
)
from examprep.schemas import (
    ArchetypeEdit,
    ArchetypeIn,
    ObjectiveEdit,
    ObjectiveIn,
    SourceQuestionIn,
    TopicNode,
)


def topics(raw):
    return TypeAdapter(list[TopicNode]).validate_python(raw)


def objectives(raw):
    return TypeAdapter(list[ObjectiveIn]).validate_python(raw)


def questions(raw):
    return TypeAdapter(list[SourceQuestionIn]).validate_python(raw)


def archetypes(raw):
    return TypeAdapter(list[ArchetypeIn]).validate_python(raw)


DIFF = {
    "steps": 4,
    "input_size": 8,
    "concept_count": 2,
    "bloom_level": "apply",
    "est_minutes": 10,
    "edge_cases": ["tekrar eden eleman"],
}

TREE = [
    {
        "key": "siralama",
        "name": "Sıralama",
        "children": [{"key": "siralama.karsilastirma", "name": "Karşılaştırma tabanlı"}],
    },
    {"key": "graf", "name": "Graflar"},
]


def arch(key, objective_key, angle="trace", origin="model", refs=()):
    return {
        "key": key,
        "objective_key": objective_key,
        "skill": "Verilen girdide algoritmayı adım adım izle",
        "angle": angle,
        "variation_axes": {"algoritma": ["merge", "quick"], "girdi": ["sıralı", "ters"]},
        "origin": origin,
        "source_questions": [{"document_id": d, "label": l} for d, l in refs],
    }


@pytest.fixture
def seeded(session, course, course_docs):
    """Konu ağacı + 2 kazanım + 3 kaynak soru (2 sınav, 1 ödev)."""
    cid = course.id
    analysis.import_topics(session, cid, topics(TREE))
    analysis.import_objectives(
        session,
        cid,
        objectives(
            [
                {"key": "sort.trace", "topic_key": "siralama.karsilastirma", "text": "Sıralamayı izle",
                 "bloom_level": "apply", "source_document_id": course_docs["slides"], "source_pages": [1]},
                {"key": "graf.bfs", "topic_key": "graf", "text": "BFS uygula", "bloom_level": "apply"},
            ]
        ),
    )
    exam, hw = course_docs["exam"], course_docs["homework"]
    analysis.import_questions(
        session,
        cid,
        questions(
            [
                {"document_id": exam, "label": "1", "page_no": 1, "text": "Merge sort izle", "points": 20,
                 "difficulty": DIFF},
                {"document_id": exam, "label": "2", "page_no": 2, "text": "BFS sırası",
                 "difficulty": {**DIFF, "steps": 6, "bloom_level": "analyze", "edge_cases": []}},
                {"document_id": hw, "label": "1", "page_no": 1, "text": "Quicksort izle",
                 "solution": "pivot=..."},
            ]
        ),
    )
    return {"cid": cid, "exam": exam, "hw": hw, "slides": course_docs["slides"]}


# --- Konular ---


def test_topic_tree_created_with_parents_and_order(session, seeded):
    by_key = {t.key: t for t in session.query(Topic)}
    assert by_key["siralama.karsilastirma"].parent.key == "siralama"
    assert by_key["graf"].parent is None
    assert by_key["graf"].order == 1


def test_topic_reimport_updates_and_skips_approved(session, seeded):
    cid = seeded["cid"]
    graf = session.query(Topic).filter_by(key="graf").one()
    analysis.set_approved(session, Topic, graf.id, True)

    renamed = [{**TREE[0], "name": "Sıralama Algoritmaları"}, {"key": "graf", "name": "DEĞİŞMEMELİ"}]
    result = analysis.import_topics(session, cid, topics(renamed))

    assert result.created == []
    assert set(result.updated) == {"siralama", "siralama.karsilastirma"}
    assert result.skipped_approved == ["graf"]
    assert session.query(Topic).filter_by(key="siralama").one().name == "Sıralama Algoritmaları"
    assert graf.name == "Graflar"


def test_topic_duplicate_keys_in_file_rejected(session, course):
    with pytest.raises(AnalysisError, match="tekrar eden") as exc:
        analysis.import_topics(session, course.id, topics([{"key": "a", "name": "A"}, {"key": "a", "name": "B"}]))
    assert exc.value.details == ["a"]


def test_topic_dry_run_writes_nothing(session, course):
    result = analysis.import_topics(session, course.id, topics(TREE), dry_run=True)
    assert result.dry_run and len(result.created) == 3
    assert session.query(Topic).count() == 0


def test_invalid_key_rejected_by_schema():
    with pytest.raises(ValidationError):
        topics([{"key": "Büyük Harf", "name": "x"}])


# --- Kazanımlar ---


def test_objective_unknown_topic_rolls_back_whole_batch(session, seeded):
    with pytest.raises(AnalysisError) as exc:
        analysis.import_objectives(
            session,
            seeded["cid"],
            objectives(
                [
                    {"key": "yeni", "topic_key": "graf", "text": "x", "bloom_level": "remember"},
                    {"key": "bozuk", "topic_key": "olmayan", "text": "y", "bloom_level": "remember"},
                ]
            ),
        )
    assert "[1] bozuk" in exc.value.details[0]
    session.rollback()
    assert session.query(LearningObjective).count() == 2


def test_objective_document_from_other_course_rejected(session, seeded):
    with pytest.raises(AnalysisError, match="Kazanımlar"):
        analysis.import_objectives(
            session, seeded["cid"],
            objectives([{"key": "x", "topic_key": "graf", "text": "x", "bloom_level": "apply",
                         "source_document_id": 999}]),
        )


# --- Kaynak sorular ---


def test_questions_upsert_by_document_and_label(session, seeded):
    result = analysis.import_questions(
        session, seeded["cid"],
        questions([{"document_id": seeded["exam"], "label": "1", "page_no": 1, "text": "Yeni metin"}]),
    )
    assert result.updated == [f"{seeded['exam']}:1"]
    assert session.query(SourceQuestion).count() == 3
    q = session.query(SourceQuestion).filter_by(document_id=seeded["exam"], label="1").one()
    assert q.text == "Yeni metin" and q.difficulty is None


@pytest.mark.parametrize(
    ("doc_key", "page_no", "message"),
    [("slides", 1, "yalnızca sınav/ödev"), ("exam", 5, "sayfa 5 yok")],
)
def test_question_validation(session, seeded, doc_key, page_no, message):
    with pytest.raises(AnalysisError) as exc:
        analysis.import_questions(
            session, seeded["cid"],
            questions([{"document_id": seeded[doc_key], "label": "9", "page_no": page_no, "text": "x"}]),
        )
    assert message in exc.value.details[0]


# --- Kalıplar ---


def test_archetype_links_questions_and_weights(session, seeded):
    e, h, cid = seeded["exam"], seeded["hw"], seeded["cid"]
    analysis.import_archetypes(
        session, cid,
        archetypes([
            arch("sort.trace.a", "sort.trace", origin="exam", refs=[(e, "1"), (h, "1")]),
            arch("sort.trace.edge", "sort.trace", angle="edge_case"),
        ]),
    )
    obj = session.query(LearningObjective).filter_by(key="sort.trace").one()
    assert obj.weight == 1 + 1 + 0.5
    assert [q.label for q in obj.archetypes[0].source_questions] == ["1", "1"]
    assert session.query(LearningObjective).filter_by(key="graf.bfs").one().weight == 1


def test_archetype_requires_existing_objective(session, seeded):
    with pytest.raises(AnalysisError) as exc:
        analysis.import_archetypes(session, seeded["cid"], archetypes([arch("x", "olmayan")]))
    assert "kapsam kilidi" in exc.value.details[0]


def test_archetype_origin_must_match_linked_questions(session, seeded):
    with pytest.raises(AnalysisError) as exc:
        analysis.import_archetypes(
            session, seeded["cid"],
            archetypes([arch("x", "sort.trace", origin="homework", refs=[(seeded["exam"], "1")])]),
        )
    assert "origin=exam olmalı" in exc.value.details[0]


def test_archetype_unknown_question_ref(session, seeded):
    with pytest.raises(AnalysisError) as exc:
        analysis.import_archetypes(
            session, seeded["cid"], archetypes([arch("x", "sort.trace", origin="exam", refs=[(seeded["exam"], "7")])])
        )
    assert f"{seeded['exam']}:7" in exc.value.details[0]


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"origin": "model", "source_questions": [{"document_id": 1, "label": "1"}]}, "origin=model"),
        ({"origin": "exam"}, "en az bir kaynak soru"),
        ({"origin": "web"}, "source_url"),
        ({"variation_axes": {"algoritma": ["merge"]}}, "en az 2 farklı değer"),
        ({"variation_axes": {}}, "En az bir varyasyon"),
        ({"angle": "guess"}, "angle"),
    ],
)
def test_archetype_schema_rules(override, message):
    with pytest.raises(ValidationError, match=message):
        archetypes([{**arch("x", "y"), **override}])


def test_archetype_reimport_skips_approved(session, seeded):
    cid = seeded["cid"]
    analysis.import_archetypes(session, cid, archetypes([arch("a", "sort.trace")]))
    a = session.query(QuestionArchetype).filter_by(key="a").one()
    analysis.set_approved(session, QuestionArchetype, a.id, True)

    changed = {**arch("a", "sort.trace"), "skill": "değişmemeli"}
    result = analysis.import_archetypes(session, cid, archetypes([changed]))
    assert result.skipped_approved == ["a"]
    assert a.skill != "değişmemeli"


def test_merge_moves_questions_and_updates_origin(session, seeded):
    e, h, cid = seeded["exam"], seeded["hw"], seeded["cid"]
    analysis.import_archetypes(
        session, cid,
        archetypes([
            arch("hw", "sort.trace", origin="homework", refs=[(h, "1")]),
            arch("ex", "sort.trace", origin="exam", refs=[(e, "1")]),
            arch("bfs", "graf.bfs"),
        ]),
    )
    merged = analysis.merge_archetypes(session, cid, "hw", ["ex"])

    assert merged.origin is ArchetypeOrigin.exam
    assert {q.ref for q in merged.source_questions} == {f"{h}:1", f"{e}:1"}
    assert session.query(QuestionArchetype).filter_by(key="ex").count() == 0
    assert session.query(LearningObjective).filter_by(key="sort.trace").one().weight == 2.5

    with pytest.raises(AnalysisError, match="aynı kazanımın"):
        analysis.merge_archetypes(session, cid, "hw", ["bfs"])
    with pytest.raises(AnalysisError, match="bulunamadı"):
        analysis.merge_archetypes(session, cid, "hw", ["yok"])


# --- Kapsam, profil, harita ---


def test_coverage_reports_gaps(session, seeded):
    e, cid = seeded["exam"], seeded["cid"]
    analysis.import_archetypes(session, cid, archetypes([arch("a", "sort.trace", origin="exam", refs=[(e, "1")])]))

    cov = analysis.coverage(session, cid)
    assert cov.objectives_without_archetypes == ["graf.bfs"]
    assert cov.objectives_with_few_angles == ["sort.trace"]
    assert set(cov.unmapped_questions) == {f"{e}:2", f"{seeded['hw']}:1"}
    assert not cov.ok

    analysis.import_archetypes(
        session, cid,
        archetypes([
            arch("b", "sort.trace", angle="edge_case"),
            arch("c", "graf.bfs", angle="trace"),
            arch("d", "graf.bfs", angle="compare"),
        ]),
    )
    assert analysis.coverage(session, cid).ok


def test_compute_profile_uses_exam_questions_only(session, seeded):
    profile = analysis.compute_profile(session, seeded["cid"])
    assert profile.sample_size == 2
    assert profile.steps == 5  # medyan(4, 6)
    assert profile.bloom_level == 3.5  # apply=3, analyze=4
    assert profile.edge_cases["frequency"] == {"tekrar eden eleman": 1}

    again = analysis.compute_profile(session, seeded["cid"])  # upsert, yeni kayıt açmaz
    assert again.sample_size == 2


def test_compute_profile_without_exam_difficulty_fails(session, course):
    with pytest.raises(AnalysisError, match="Zorluk bilgisi"):
        analysis.compute_profile(session, course.id)


def test_course_map_structure(session, seeded):
    e, cid = seeded["exam"], seeded["cid"]
    analysis.import_archetypes(session, cid, archetypes([arch("a", "sort.trace", origin="exam", refs=[(e, "1")])]))

    m = analysis.get_course_map(session, cid)
    assert [t.key for t in m.topics] == ["siralama", "graf"]
    obj = m.topics[0].children[0].objectives[0]
    assert obj.key == "sort.trace"
    sq = obj.archetypes[0].source_questions[0]
    assert sq.text == "Merge sort izle" and sq.archetype_keys == ["a"]
    assert {q.ref for q in m.unmapped_questions} == {f"{e}:2", f"{seeded['hw']}:1"}

    brief = analysis.get_course_map(session, cid, with_text=False)
    assert brief.topics[0].children[0].objectives[0].archetypes[0].source_questions[0].text is None


# --- Arayüz düzenlemeleri ---


def test_edits(session, seeded):
    cid = seeded["cid"]
    analysis.import_archetypes(session, cid, archetypes([arch("a", "sort.trace")]))
    obj = session.query(LearningObjective).filter_by(key="sort.trace").one()
    a = obj.archetypes[0]

    analysis.update_objective(session, obj.id, ObjectiveEdit(text="Yeni", bloom_level="analyze", weight_override=3))
    assert obj.effective_weight == 3 and obj.bloom_level.value == "analyze"

    analysis.update_archetype(
        session, a.id, ArchetypeEdit(skill="Hata bul", angle="find_error", variation_axes={"x": ["1", "2"]})
    )
    assert a.angle.value == "find_error"

    topic = session.query(Topic).filter_by(key="graf").one()
    analysis.rename_topic(session, topic.id, "  Graf Teorisi ")
    assert topic.name == "Graf Teorisi"
    with pytest.raises(AnalysisError):
        analysis.rename_topic(session, topic.id, " ")


def test_unlink_question_downgrades_origin_and_weight(session, seeded):
    e, cid = seeded["exam"], seeded["cid"]
    analysis.import_archetypes(session, cid, archetypes([arch("a", "sort.trace", origin="exam", refs=[(e, "1")])]))
    a = session.query(QuestionArchetype).filter_by(key="a").one()
    q = a.source_questions[0]

    analysis.unlink_question(session, a.id, q.id)
    assert a.origin is ArchetypeOrigin.model
    assert a.objective.weight == 1
    assert session.get(SourceQuestion, q.id) is not None  # soru silinmez


def test_delete_objective_keeps_questions_and_reweights(session, seeded):
    e, cid = seeded["exam"], seeded["cid"]
    analysis.import_archetypes(session, cid, archetypes([arch("a", "sort.trace", origin="exam", refs=[(e, "1")])]))
    obj = session.query(LearningObjective).filter_by(key="sort.trace").one()

    analysis.delete_item(session, LearningObjective, obj.id)
    assert session.query(QuestionArchetype).count() == 0
    assert session.query(SourceQuestion).count() == 3
    assert f"{e}:1" in analysis.coverage(session, cid).unmapped_questions


def test_delete_topic_removes_subtree(session, seeded):
    root = session.query(Topic).filter_by(key="siralama").one()
    analysis.delete_item(session, Topic, root.id)
    assert {t.key for t in session.query(Topic)} == {"graf"}
    assert {o.key for o in session.query(LearningObjective)} == {"graf.bfs"}


def test_approve_topic_tree(session, seeded):
    cid = seeded["cid"]
    analysis.import_archetypes(session, cid, archetypes([arch("a", "sort.trace")]))
    root = session.query(Topic).filter_by(key="siralama").one()

    assert analysis.approve_topic_tree(session, root.id) == 4  # 2 konu + 1 kazanım + 1 kalıp
    assert analysis.coverage(session, cid).unapproved_count == 2  # graf + graf.bfs
