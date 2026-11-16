import json

import pymupdf
import pytest
from typer.testing import CliRunner

from examprep import config, db
from examprep.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    db.reset_engine()
    yield tmp_path
    db.reset_engine()


def run(*args, input=None):
    return runner.invoke(app, [str(a) for a in args], input=input)


def ok(*args, input=None):
    result = run(*args, input=input)
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def fail(*args, input=None):
    result = run(*args, input=input)
    assert result.exit_code == 1, result.output
    return json.loads(result.stderr)


@pytest.fixture
def pdf_file(tmp_path, text_pdf):
    path = tmp_path / "2023_Midterm.pdf"
    path.write_bytes(text_pdf)
    return path


@pytest.fixture
def course_id():
    return ok("course", "add", "--name", "Algoritmalar", "--exam-date", "2027-01-10")["id"]


def test_course_add_and_list(course_id):
    courses = ok("course", "list")
    assert courses == [
        {"id": course_id, "name": "Algoritmalar", "code": None, "exam_date": "2027-01-10", "document_count": 0}
    ]


def test_course_add_from_json_stdin():
    out = ok("course", "add", "--json", "-", input='{"name": "Veri Yapıları", "code": "CS202"}')
    assert out["name"] == "Veri Yapıları"
    assert out["code"] == "CS202"


def test_course_add_from_json_file(tmp_path):
    f = tmp_path / "c.json"
    f.write_text('{"name": "Ayrık Matematik"}', encoding="utf-8")
    assert ok("course", "add", "--json", f)["name"] == "Ayrık Matematik"


def test_course_add_rejects_unknown_field():
    err = fail("course", "add", "--json", "-", input='{"name": "X", "hoca": "Y"}')
    assert err["error"] == "Geçersiz ders verisi"
    assert err["details"][0]["loc"] == ["hoca"]


def test_course_add_rejects_bad_date_and_empty_name():
    assert fail("course", "add", "--name", "X", "--exam-date", "10.01.2027")["details"][0]["loc"] == ["exam_date"]
    assert fail("course", "add")["details"][0]["loc"] == ["name"]


def test_course_add_rejects_json_mixed_with_options():
    assert "birlikte" in fail("course", "add", "--name", "X", "--json", "-", input="{}")["error"]


def test_course_add_invalid_json():
    assert "Geçersiz JSON" in fail("course", "add", "--json", "-", input="{bozuk")["error"]


def test_duplicate_course_fails(course_id):
    assert "zaten var" in fail("course", "add", "--name", "Algoritmalar")["error"]


def test_ingest_guesses_type_and_is_idempotent(course_id, pdf_file):
    first = ok("ingest", pdf_file, "--course", course_id)
    assert first["created"] is True
    assert first["document"]["doc_type"] == "exam"
    assert first["document"]["page_count"] == 2

    again = ok("ingest", pdf_file, "--course", course_id, "--type", "slides")
    assert again["created"] is False
    assert again["document"]["id"] == first["document"]["id"]


def test_ingest_explicit_type(course_id, pdf_file):
    assert ok("ingest", pdf_file, "--course", course_id, "--type", "homework")["document"]["doc_type"] == "homework"


def test_ingest_unknown_course(pdf_file):
    assert "Ders bulunamadı" in fail("ingest", pdf_file, "--course", 42)["error"]


def test_ingest_corrupt_pdf(course_id, tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"pdf degil")
    assert "açılamadı" in fail("ingest", bad, "--course", course_id)["error"]


def test_doc_list_filters_by_type(course_id, pdf_file, tmp_path, scanned_pdf):
    scan = tmp_path / "hafta1.pdf"
    scan.write_bytes(scanned_pdf)
    ok("ingest", pdf_file, "--course", course_id)
    ok("ingest", scan, "--course", course_id)

    assert len(ok("doc", "list", "--course", course_id)) == 2
    slides = ok("doc", "list", "--course", course_id, "--type", "slides")
    assert [d["filename"] for d in slides] == ["hafta1.pdf"]
    assert slides[0]["status"] == "needs_ocr"


def test_doc_pages_returns_text_and_absolute_image_paths(course_id, pdf_file, data_dir):
    doc_id = ok("ingest", pdf_file, "--course", course_id)["document"]["id"]

    pages = ok("doc", "pages", doc_id)
    assert [p["page_no"] for p in pages] == [1, 2]
    assert "Merge sort" in pages[0]["text"]
    for p in pages:
        assert p["image_path"].startswith(str(data_dir.resolve()))
        assert open(p["image_path"], "rb").read(4) == b"\x89PNG"

    assert [p["page_no"] for p in ok("doc", "pages", doc_id, "--start", 2)] == [2]
    assert [p["page_no"] for p in ok("doc", "pages", doc_id, "--end", 1)] == [1]
    assert ok("doc", "pages", doc_id, "--scanned-only") == []


def test_doc_pages_unknown_document():
    assert "Belge bulunamadı" in fail("doc", "pages", 7)["error"]


def test_scanned_page_listed_with_scanned_only(course_id, tmp_path, scanned_pdf):
    scan = tmp_path / "tarama.pdf"
    scan.write_bytes(scanned_pdf)
    doc_id = ok("ingest", scan, "--course", course_id)["document"]["id"]
    pages = ok("doc", "pages", doc_id, "--scanned-only")
    assert len(pages) == 1 and pages[0]["is_scanned"]
