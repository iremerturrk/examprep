import streamlit as st
from pydantic import ValidationError

from examprep.courses import CourseExistsError, create_course, list_courses
from examprep.db import session_scope
from examprep.i18n import t
from examprep.schemas import CourseIn

st.title(t("courses.title"))

with st.form("new_course", clear_on_submit=True):
    st.subheader(t("courses.new"))
    name = st.text_input(t("courses.name"))
    code = st.text_input(t("courses.code"))
    has_date = st.checkbox(t("courses.has_date"))
    exam_date = st.date_input(t("courses.date"), format="DD.MM.YYYY")
    submitted = st.form_submit_button(t("courses.create"))

if submitted:
    try:
        data = CourseIn(name=name, code=code, exam_date=exam_date if has_date else None)
        with session_scope() as s:
            course = create_course(s, data)
        st.success(t("courses.created", name=course.name, id=course.id))
    except ValidationError:
        st.error(t("courses.name_empty"))
    except CourseExistsError:
        st.error(t("courses.exists"))

st.subheader(t("courses.existing"))
with session_scope() as s:
    courses = list_courses(s)

if courses:
    st.dataframe(
        [
            {
                "id": c.id,
                t("common.course"): c.name,
                t("courses.col_code"): c.code or "",
                t("courses.date"): c.exam_date.strftime("%d.%m.%Y") if c.exam_date else "",
                t("courses.col_docs"): c.document_count,
            }
            for c in courses
        ],
        hide_index=True,
        width="stretch",
    )
else:
    st.info(t("courses.empty"))
