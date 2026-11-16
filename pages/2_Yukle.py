import streamlit as st
from sqlalchemy import select

from examprep import config
from examprep.db import session_scope
from examprep.i18n import label, t
from examprep.ingest import IngestError, guess_doc_type, ingest_document
from examprep.models import Course, DocStatus, DocType, DocumentPage, SourceDocument

st.title(t("nav.upload"))

with session_scope() as s:
    courses = {c.id: c.name for c in s.scalars(select(Course).order_by(Course.name))}

if not courses:
    st.warning(t("common.need_course"))
    st.stop()

course_id = st.selectbox(t("common.course"), options=list(courses), format_func=courses.get)

files = st.file_uploader(t("upload.files"), type="pdf", accept_multiple_files=True)

if files:
    st.subheader(t("upload.types"))
    types: dict[str, DocType] = {}
    for f in files:
        guess = guess_doc_type(f.name)
        types[f.file_id] = st.radio(
            f.name,
            options=list(DocType),
            index=list(DocType).index(guess),
            format_func=label,
            horizontal=True,
            key=f"type_{f.file_id}",
        )

    if st.button(t("upload.process"), type="primary"):
        progress = st.progress(0.0)
        for i, f in enumerate(files):
            progress.progress(i / len(files), text=t("upload.processing", name=f.name))
            try:
                with session_scope() as s:
                    doc, created = ingest_document(s, course_id, f.name, f.getvalue(), types[f.file_id])
                    page_count, status = doc.page_count, doc.status
                if not created:
                    st.info(t("upload.duplicate", name=f.name))
                elif status is DocStatus.needs_ocr:
                    st.warning(t("upload.scanned", name=f.name, n=page_count))
                else:
                    st.success(t("upload.done_file", name=f.name, n=page_count))
            except IngestError as exc:
                st.error(f"{f.name}: {exc}")
        progress.progress(1.0, text=t("upload.done"))

st.divider()
st.subheader(t("upload.uploaded"))

COL_FILE, COL_TYPE, COL_PAGES, COL_STATUS = (t("upload.col_file"), t("upload.col_type"), t("common.page"),
                                             t("upload.col_status"))
with session_scope() as s:
    docs = s.scalars(
        select(SourceDocument).where(SourceDocument.course_id == course_id).order_by(SourceDocument.uploaded_at.desc())
    ).all()
    doc_rows = [
        {"id": d.id, COL_FILE: d.filename, COL_TYPE: label(d.doc_type), COL_PAGES: d.page_count,
         COL_STATUS: label(d.status)}
        for d in docs
    ]

if not doc_rows:
    st.info(t("upload.no_docs"))
    st.stop()

st.dataframe(doc_rows, hide_index=True, width="stretch", column_order=[COL_FILE, COL_TYPE, COL_PAGES, COL_STATUS])

st.subheader(t("upload.preview"))
doc_names = {r["id"]: r[COL_FILE] for r in doc_rows}
doc_id = st.selectbox(t("upload.document"), options=list(doc_names), format_func=doc_names.get)

with session_scope() as s:
    pages = s.scalars(
        select(DocumentPage).where(DocumentPage.document_id == doc_id).order_by(DocumentPage.page_no)
    ).all()
    page_data = [(p.page_no, p.image_path, p.text, p.is_scanned) for p in pages]

if page_data:
    page_no = st.number_input(t("common.page"), min_value=1, max_value=len(page_data), value=1)
    _, image_path, text, is_scanned = page_data[page_no - 1]
    left, right = st.columns(2)
    with left:
        image_file = config.DATA_DIR / image_path
        if image_file.exists():
            st.image(str(image_file), width="stretch")
        else:
            st.error(t("upload.no_image"))
    with right:
        if is_scanned:
            st.warning(t("upload.scanned_page"))
        st.text_area(t("upload.text"), text, height=500, disabled=True)
