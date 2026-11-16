import streamlit as st
from pydantic import ValidationError

from examprep.courses import CourseExistsError, create_course, list_courses
from examprep.db import session_scope
from examprep.schemas import CourseIn

st.title("Dersler")

with st.form("new_course", clear_on_submit=True):
    st.subheader("Yeni ders")
    name = st.text_input("Ders adı *")
    code = st.text_input("Ders kodu")
    has_date = st.checkbox("Sınav tarihi belli")
    exam_date = st.date_input("Sınav tarihi", format="DD.MM.YYYY")
    submitted = st.form_submit_button("Oluştur")

if submitted:
    try:
        data = CourseIn(name=name, code=code, exam_date=exam_date if has_date else None)
        with session_scope() as s:
            course = create_course(s, data)
        st.success(f"'{course.name}' oluşturuldu (id: {course.id}).")
    except ValidationError:
        st.error("Ders adı boş olamaz.")
    except CourseExistsError:
        st.error("Bu isimde bir ders zaten var.")

st.subheader("Mevcut dersler")
with session_scope() as s:
    courses = list_courses(s)

if courses:
    st.dataframe(
        [
            {
                "id": c.id,
                "Ders": c.name,
                "Kod": c.code or "",
                "Sınav tarihi": c.exam_date.strftime("%d.%m.%Y") if c.exam_date else "",
                "Belge sayısı": c.document_count,
            }
            for c in courses
        ],
        hide_index=True,
        width="stretch",
    )
else:
    st.info("Henüz ders yok.")
