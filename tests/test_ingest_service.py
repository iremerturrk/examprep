import pytest
from sqlalchemy import func, select

from examprep.ingest import IngestError, guess_doc_type, ingest_document
from examprep.ingest import service
from examprep.models import DocStatus, DocType, DocumentPage, SourceDocument


def test_ingest_saves_document_and_pages(session, course, text_pdf, tmp_path):
    doc, created = ingest_document(session, course.id, "hafta1.pdf", text_pdf, DocType.slides, tmp_path)

    assert created
    assert doc.page_count == 2
    assert doc.status is DocStatus.processed
    assert [p.page_no for p in doc.pages] == [1, 2]
    first = doc.pages[0]
    assert first.image_path == f"pages/{doc.id}/page_001.png"
    assert (tmp_path / first.image_path).exists()
    assert "Merge sort" in first.text


def test_duplicate_upload_returns_existing(session, course, text_pdf, tmp_path):
    first, _ = ingest_document(session, course.id, "a.pdf", text_pdf, DocType.slides, tmp_path)
    second, created = ingest_document(session, course.id, "kopya.pdf", text_pdf, DocType.exam, tmp_path)

    assert not created
    assert second.id == first.id
    assert session.scalar(select(func.count(SourceDocument.id))) == 1


def test_scanned_pdf_marks_needs_ocr(session, course, scanned_pdf, tmp_path):
    doc, _ = ingest_document(session, course.id, "tarama.pdf", scanned_pdf, DocType.exam, tmp_path)
    assert doc.status is DocStatus.needs_ocr
    assert doc.pages[0].is_scanned


def test_failure_rolls_back_and_cleans_files(session, course, text_pdf, tmp_path, monkeypatch):
    def broken_extract(pdf_bytes, out_dir):
        out_dir.mkdir(parents=True)
        (out_dir / "page_001.png").write_bytes(b"partial")
        raise IngestError("bozuk")

    monkeypatch.setattr(service, "extract_pages", broken_extract)
    with pytest.raises(IngestError):
        ingest_document(session, course.id, "x.pdf", text_pdf, DocType.slides, tmp_path)

    assert session.scalar(select(func.count(SourceDocument.id))) == 0
    assert session.scalar(select(func.count(DocumentPage.id))) == 0
    pages_dir = tmp_path / "pages"
    assert not pages_dir.exists() or not any(pages_dir.iterdir())


def test_unknown_course_raises(session, text_pdf, tmp_path):
    with pytest.raises(IngestError, match="Ders bulunamadı"):
        ingest_document(session, 999, "x.pdf", text_pdf, DocType.slides, tmp_path)


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("Hafta3_Sorting.pdf", DocType.slides),
        ("2023_Midterm.pdf", DocType.exam),
        ("final-cozumlu.pdf", DocType.exam),
        ("Sınav_2022.pdf", DocType.exam),
        ("odev2.pdf", DocType.homework),
        ("Ödev_3.pdf", DocType.homework),
        ("cs201_hw1.pdf", DocType.homework),
        ("PS4.pdf", DocType.homework),
        ("graphs.pdf", DocType.slides),
    ],
)
def test_guess_doc_type(filename, expected):
    assert guess_doc_type(filename) is expected
