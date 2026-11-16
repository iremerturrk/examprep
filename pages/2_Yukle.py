import streamlit as st
from sqlalchemy import select

from examprep import config
from examprep.db import session_scope
from examprep.ingest import IngestError, guess_doc_type, ingest_document
from examprep.models import Course, DocType, DocumentPage, SourceDocument

TYPE_LABELS = {DocType.slides: "Slayt", DocType.homework: "Ödev", DocType.exam: "Sınav"}
STATUS_LABELS = {"processed": "İşlendi", "needs_ocr": "Taranmış sayfa var", "failed": "Hata"}

st.title("PDF Yükle")

with session_scope() as s:
    courses = {c.id: c.name for c in s.scalars(select(Course).order_by(Course.name))}

if not courses:
    st.warning("Önce 'Dersler' sayfasından bir ders oluşturun.")
    st.stop()

course_id = st.selectbox("Ders", options=list(courses), format_func=courses.get)

files = st.file_uploader("PDF dosyaları", type="pdf", accept_multiple_files=True)

if files:
    st.subheader("Dosya türleri")
    types: dict[str, DocType] = {}
    for f in files:
        guess = guess_doc_type(f.name)
        types[f.file_id] = st.radio(
            f.name,
            options=list(DocType),
            index=list(DocType).index(guess),
            format_func=TYPE_LABELS.get,
            horizontal=True,
            key=f"type_{f.file_id}",
        )

    if st.button("İşle", type="primary"):
        progress = st.progress(0.0)
        for i, f in enumerate(files):
            progress.progress(i / len(files), text=f"İşleniyor: {f.name}")
            try:
                with session_scope() as s:
                    doc, created = ingest_document(
                        s, course_id, f.name, f.getvalue(), types[f.file_id]
                    )
                    page_count, status = doc.page_count, doc.status
                if not created:
                    st.info(f"{f.name}: bu dosya zaten yüklü, atlandı.")
                elif status.value == "needs_ocr":
                    st.warning(
                        f"{f.name}: {page_count} sayfa işlendi, taranmış sayfalar var, metinleri /ders-analiz sırasında görüntüden okunacak."
                    )
                else:
                    st.success(f"{f.name}: {page_count} sayfa işlendi.")
            except IngestError as exc:
                st.error(f"{f.name}: {exc}")
        progress.progress(1.0, text="Tamamlandı")

st.divider()
st.subheader("Yüklenen belgeler")

with session_scope() as s:
    docs = s.scalars(
        select(SourceDocument)
        .where(SourceDocument.course_id == course_id)
        .order_by(SourceDocument.uploaded_at.desc())
    ).all()
    doc_rows = [
        {
            "id": d.id,
            "Dosya": d.filename,
            "Tür": TYPE_LABELS[d.doc_type],
            "Sayfa": d.page_count,
            "Durum": STATUS_LABELS[d.status.value],
        }
        for d in docs
    ]

if not doc_rows:
    st.info("Bu derse henüz belge yüklenmedi.")
    st.stop()

st.dataframe(doc_rows, hide_index=True, width="stretch", column_order=["Dosya", "Tür", "Sayfa", "Durum"])

st.subheader("Önizleme")
doc_names = {r["id"]: r["Dosya"] for r in doc_rows}
doc_id = st.selectbox("Belge", options=list(doc_names), format_func=doc_names.get)

with session_scope() as s:
    pages = s.scalars(
        select(DocumentPage).where(DocumentPage.document_id == doc_id).order_by(DocumentPage.page_no)
    ).all()
    page_data = [(p.page_no, p.image_path, p.text, p.is_scanned) for p in pages]

if page_data:
    page_no = st.number_input("Sayfa", min_value=1, max_value=len(page_data), value=1)
    _, image_path, text, is_scanned = page_data[page_no - 1]
    left, right = st.columns(2)
    with left:
        image_file = config.DATA_DIR / image_path
        if image_file.exists():
            st.image(str(image_file), width="stretch")
        else:
            st.error("Sayfa görüntüsü bulunamadı.")
    with right:
        if is_scanned:
            st.warning("Taranmış sayfa: metin /ders-analiz sırasında görüntüden okunacak.")
        st.text_area("Çıkarılan metin", text, height=500, disabled=True)
