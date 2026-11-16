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


def test_weekly_plan_links_objectives_and_cascades(session, course):
    from datetime import date

    from examprep.models import WeeklyPlan, weekly_plan_objective

    topic = Topic(course=course, key="graflar", name="Graflar")
    lo1 = LearningObjective(
        course_id=course.id, topic=topic, key="g.bfs", text="BFS izle", bloom_level=BloomLevel.apply
    )
    lo2 = LearningObjective(
        course_id=course.id, topic=topic, key="g.dij", text="Dijkstra uygula", bloom_level=BloomLevel.apply
    )
    plan = WeeklyPlan(
        course=course, week_no=1, start_date=date(2026, 11, 16), end_date=date(2026, 11, 22),
        objectives=[lo1, lo2],
    )
    session.add_all([topic, plan])
    session.commit()

    assert [p.week_no for p in session.get(Course, course.id).weekly_plans] == [1]
    assert {o.text for o in plan.objectives} == {"BFS izle", "Dijkstra uygula"}

    session.add(WeeklyPlan(course=course, week_no=1, start_date=date(2026, 11, 23), end_date=date(2026, 11, 29)))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    session.delete(lo1)
    session.commit()
    assert [o.text for o in session.get(WeeklyPlan, plan.id).objectives] == ["Dijkstra uygula"]

    session.delete(course)
    session.commit()
    assert session.scalar(select(func.count(WeeklyPlan.id))) == 0
    assert session.scalar(select(func.count()).select_from(weekly_plan_objective)) == 0
