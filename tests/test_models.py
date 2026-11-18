import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from examprep.models import (
    Angle,
    ArchetypeOrigin,
    BloomLevel,
    Attempt,
    Course,
    DocType,
    DocumentPage,
    GeneratedQuestion,
    LearningObjective,
    PerceivedDifficulty,
    QuestionArchetype,
    SourceDocument,
    Topic,
)


def _doc(course, sha="a" * 64):
    return SourceDocument(course=course, filename="s.pdf", doc_type=DocType.slides, sha256=sha)


def test_full_hierarchy_roundtrip(session, course):
    topic = Topic(course=course, key="siralama", name="Sıralama")
    lo = LearningObjective(
        course_id=course.id,
        topic=topic,
        key="siralama.izle",
        text="Karşılaştırma tabanlı sıralamayı izle",
        bloom_level=BloomLevel.apply,
    )
    arch = QuestionArchetype(
        course_id=course.id,
        key="siralama.izle.trace",
        objective=lo,
        skill="Verilen dizide sıralama algoritmasını izle",
        angle=Angle.trace,
        variation_axes={"algorithm": ["merge", "quick", "heap"]},
        origin=ArchetypeOrigin.exam,
    )
    q = GeneratedQuestion(archetype=arch, prompt="...", answer="...")
    Attempt(question=q, correct=True, perceived_difficulty=PerceivedDifficulty.exam_like)
    session.add(topic)
    session.commit()

    loaded = session.get(Course, course.id)
    attempt = loaded.topics[0].objectives[0].archetypes[0].questions[0].attempts[0]
    assert attempt.perceived_difficulty is PerceivedDifficulty.exam_like
    assert loaded.topics[0].objectives[0].archetypes[0].variation_axes["algorithm"][1] == "quick"


def test_same_sha_rejected_within_course(session, course):
    session.add_all([_doc(course), _doc(course)])
    with pytest.raises(IntegrityError):
        session.commit()


def test_same_sha_allowed_across_courses(session, course):
    other = Course(name="Veri Yapıları")
    session.add_all([_doc(course), _doc(other)])
    session.commit()
    assert session.scalar(select(func.count(SourceDocument.id))) == 2


def test_course_name_unique(session, course):
    session.add(Course(name=course.name))
    with pytest.raises(IntegrityError):
        session.commit()


def test_deleting_course_cascades_to_pages(session, course):
    doc = _doc(course)
    doc.pages.append(DocumentPage(page_no=1, text="x", image_path="pages/1/page_001.png"))
    session.add(doc)
    session.commit()

    session.delete(course)
    session.commit()
    assert session.scalar(select(func.count(SourceDocument.id))) == 0
    assert session.scalar(select(func.count(DocumentPage.id))) == 0



def test_test_slots_cascade_with_test(session, course):
    from examprep.models import (
        GeneratedQuestion,
        QuestionStatus,
        SlotType,
        Test,
        TestSlot,
    )

    topic = Topic(course=course, key="t", name="T")
    lo = LearningObjective(course_id=course.id, topic=topic, key="o", text="x", bloom_level=BloomLevel.apply)
    arch = QuestionArchetype(
        course_id=course.id, key="a", objective=lo, skill="s", angle=Angle.trace,
        variation_axes={"x": ["1", "2"]}, origin=ArchetypeOrigin.model,
    )
    test = Test(course_id=course.id, seed=1, size=1)
    slot = TestSlot(test=test, position=1, slot_type=SlotType.new, objective=lo, archetype=arch)
    q1 = GeneratedQuestion(archetype=arch, slot=slot, prompt="p1", answer="a", status=QuestionStatus.rejected)
    q2 = GeneratedQuestion(archetype=arch, slot=slot, prompt="p2", answer="a")
    session.add_all([topic, test, q1, q2])
    session.commit()

    assert slot.current_question is q2
    session.delete(test)
    session.commit()
    assert session.scalar(select(func.count(TestSlot.id))) == 0
    assert session.scalar(select(func.count(GeneratedQuestion.id))) == 0


def test_add_missing_columns_migrates_old_schema(tmp_path):
    from sqlalchemy import create_engine, inspect, text

    from examprep.db import add_missing_columns, init_db

    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:  # 2. aşamadaki generated_question tablosunun eski hali
        conn.execute(text(
            "CREATE TABLE generated_question (id INTEGER PRIMARY KEY, archetype_id INTEGER, prompt TEXT, "
            "answer TEXT, explanation TEXT, params JSON, verified BOOLEAN, difficulty_scores JSON, created_at DATETIME)"
        ))
        conn.execute(text("INSERT INTO generated_question (archetype_id, prompt, answer) VALUES (1, 'p', 'a')"))
    init_db(engine)

    cols = {c["name"] for c in inspect(engine).get_columns("generated_question")}
    assert {"kind", "status", "answer_type", "slot_id", "check", "verification"} <= cols
    with engine.connect() as conn:
        assert conn.execute(text("SELECT kind, status, answer_type FROM generated_question")).one() == (
            "generated", "draft", "open")
    assert add_missing_columns(engine) == []  # ikinci çalıştırma bir şey yapmaz
