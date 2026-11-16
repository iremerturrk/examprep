import pymupdf
import pytest
from sqlalchemy.orm import Session

from examprep.db import init_db, make_engine
from examprep.models import Course


@pytest.fixture
def session():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    with Session(engine, expire_on_commit=False) as s:
        yield s
    engine.dispose()


@pytest.fixture
def course(session):
    c = Course(name="Algoritmalar", code="CS201")
    session.add(c)
    session.commit()
    return c


@pytest.fixture
def text_pdf() -> bytes:
    """İki sayfalık, metin içeren PDF."""
    doc = pymupdf.open()
    for body in ("Merge sort: böl ve fethet, O(n log n).", "Quicksort pivot seçimi ve bölümleme."):
        page = doc.new_page()
        page.insert_text((72, 72), body)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def scanned_pdf() -> bytes:
    """Metni olmayan, yalnızca görüntü içeren tek sayfalık PDF (taranmış belgeyi taklit eder)."""
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 100), False)
    pix.clear_with(200)
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_image(page.rect, stream=pix.tobytes("png"))
    data = doc.tobytes()
    doc.close()
    return data


def make_pdf(*page_texts: str) -> bytes:
    doc = pymupdf.open()
    for body in page_texts:
        doc.new_page().insert_text((72, 72), body)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def course_docs(session, course, tmp_path):
    """Derse bir slayt, bir sınav (2 sayfa) ve bir ödev belgesi yükler. {tür: belge_id} döndürür."""
    from examprep.ingest import ingest_document
    from examprep.models import DocType

    ids = {}
    for doc_type, pages in [
        (DocType.slides, ["Siralama algoritmalari", "Graflar"]),
        (DocType.exam, ["Soru 1: merge sort izle", "Soru 2: BFS"]),
        (DocType.homework, ["Odev 1: quicksort"]),
    ]:
        doc, _ = ingest_document(
            session, course.id, f"{doc_type.value}.pdf", make_pdf(*pages), doc_type, tmp_path
        )
        ids[doc_type.value] = doc.id
    return ids
