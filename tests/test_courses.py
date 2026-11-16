import pytest
from pydantic import ValidationError

from examprep.courses import CourseExistsError, create_course, list_courses
from examprep.ingest import ingest_document
from examprep.models import DocType
from examprep.schemas import CourseIn


def test_create_and_list_with_document_count(session, text_pdf, tmp_path):
    a = create_course(session, CourseIn(name="  Algoritmalar ", code=""))
    create_course(session, CourseIn(name="Veri Yapıları"))
    ingest_document(session, a.id, "s.pdf", text_pdf, DocType.slides, tmp_path)

    assert a.name == "Algoritmalar"
    assert a.code is None
    counts = {c.name: c.document_count for c in list_courses(session)}
    assert counts == {"Algoritmalar": 1, "Veri Yapıları": 0}


def test_duplicate_raises_and_session_stays_usable(session):
    create_course(session, CourseIn(name="A"))
    with pytest.raises(CourseExistsError):
        create_course(session, CourseIn(name="A"))
    create_course(session, CourseIn(name="B"))
    assert [c.name for c in list_courses(session)] == ["A", "B"]


def test_blank_name_rejected():
    with pytest.raises(ValidationError):
        CourseIn(name="   ")
