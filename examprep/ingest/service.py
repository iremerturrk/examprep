"""PDF'i işleyip SourceDocument + DocumentPage kayıtları olarak saklar."""

import hashlib
import re
import shutil
import unicodedata
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from examprep import config
from examprep.ingest.pdf import IngestError, extract_pages
from examprep.models import Course, DocStatus, DocType, DocumentPage, SourceDocument

_EXAM_PATTERN = re.compile(r"s[ıi]nav|midterm|final|exam|quiz|vize", re.IGNORECASE)
_HOMEWORK_PATTERN = re.compile(r"[öo]dev|homework|(?<![a-z])hw|assignment|problem.?set|(?<![a-z])ps\d", re.IGNORECASE)


def guess_doc_type(filename: str) -> DocType:
    """Dosya adından tür tahmini. Arayüzde yalnızca ön seçim olarak kullanılır."""
    filename = unicodedata.normalize("NFC", filename)  # macOS ayrışık (NFD) adlar için
    if _EXAM_PATTERN.search(filename):
        return DocType.exam
    if _HOMEWORK_PATTERN.search(filename):
        return DocType.homework
    return DocType.slides


def ingest_document(
    session: Session,
    course_id: int,
    filename: str,
    pdf_bytes: bytes,
    doc_type: DocType,
    data_dir: Path | None = None,
) -> tuple[SourceDocument, bool]:
    """PDF'i işler ve kaydeder. (belge, yeni_mi) döndürür.

    Aynı derse aynı içerik daha önce yüklendiyse mevcut belge döndürülür.
    Hata olursa oturum geri alınır, yazılmış görüntüler silinir.
    """
    data_dir = data_dir or config.DATA_DIR
    if session.get(Course, course_id) is None:
        raise IngestError(f"Ders bulunamadı: {course_id}")

    sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    existing = session.scalar(
        select(SourceDocument).where(
            SourceDocument.course_id == course_id, SourceDocument.sha256 == sha256
        )
    )
    if existing is not None:
        return existing, False

    doc = SourceDocument(
        course_id=course_id,
        filename=filename,
        doc_type=doc_type,
        sha256=sha256,
        status=DocStatus.processed,
    )
    out_dir: Path | None = None
    try:
        session.add(doc)
        session.flush()  # doc.id için
        out_dir = data_dir / config.PAGES_DIRNAME / str(doc.id)
        pages = extract_pages(pdf_bytes, out_dir)
        for p in pages:
            doc.pages.append(
                DocumentPage(
                    page_no=p.page_no,
                    text=p.text,
                    image_path=p.image_file.relative_to(data_dir).as_posix(),
                    char_count=p.char_count,
                    is_scanned=p.is_scanned,
                )
            )
        doc.page_count = len(pages)
        if any(p.is_scanned for p in pages):
            doc.status = DocStatus.needs_ocr
        session.commit()
    except Exception:
        session.rollback()
        if out_dir is not None:
            shutil.rmtree(out_dir, ignore_errors=True)
        raise
    return doc, True
