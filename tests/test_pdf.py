import pymupdf
import pytest

from examprep.ingest.pdf import IngestError, extract_pages


def test_text_pdf_extracts_text_and_images(tmp_path, text_pdf):
    pages = extract_pages(text_pdf, tmp_path / "out")

    assert [p.page_no for p in pages] == [1, 2]
    assert "Merge sort" in pages[0].text
    assert "Quicksort" in pages[1].text
    assert not any(p.is_scanned for p in pages)
    for p in pages:
        assert p.image_file.exists()
        assert p.image_file.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        assert p.char_count == len(p.text)


def test_image_only_page_marked_scanned(tmp_path, scanned_pdf):
    (page,) = extract_pages(scanned_pdf, tmp_path)
    assert page.is_scanned
    assert page.text == ""


def test_blank_page_without_image_not_scanned(tmp_path):
    doc = pymupdf.open()
    doc.new_page()
    (page,) = extract_pages(doc.tobytes(), tmp_path)
    assert not page.is_scanned


def test_corrupt_pdf_raises(tmp_path):
    with pytest.raises(IngestError, match="açılamadı"):
        extract_pages(b"bu bir pdf degil", tmp_path)


def test_encrypted_pdf_raises(tmp_path, text_pdf):
    doc = pymupdf.open(stream=text_pdf)
    encrypted = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="gizli", owner_pw="gizli")
    with pytest.raises(IngestError, match="şifreli"):
        extract_pages(encrypted, tmp_path)
