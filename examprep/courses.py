"""Ders işlemleri. CLI ve Streamlit aynı fonksiyonları kullanır."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from examprep.models import Course, SourceDocument
from examprep.schemas import CourseIn, CourseOut


class CourseExistsError(Exception):
    pass


def create_course(session: Session, data: CourseIn) -> CourseOut:
    course = Course(name=data.name, code=data.code, exam_date=data.exam_date)
    session.add(course)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise CourseExistsError(f"Bu isimde bir ders zaten var: {data.name}") from exc
    return CourseOut.model_validate(course)


def list_courses(session: Session) -> list[CourseOut]:
    rows = session.execute(
        select(Course, func.count(SourceDocument.id))
        .outerjoin(SourceDocument)
        .group_by(Course.id)
        .order_by(Course.name)
    ).all()
    return [
        CourseOut(id=c.id, name=c.name, code=c.code, exam_date=c.exam_date, document_count=n)
        for c, n in rows
    ]
