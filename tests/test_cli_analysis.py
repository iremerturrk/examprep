"""Analiz komutlarının uçtan uca testi: skill'in izleyeceği akışın aynısı."""

import json

import pytest
from typer.testing import CliRunner

from conftest import make_pdf
from examprep import config, db
from examprep.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    db.reset_engine()
    yield tmp_path
    db.reset_engine()


def invoke(*args, input=None):
    return runner.invoke(app, [str(a) for a in args], input=input)


def ok(*args, input=None):
    r = invoke(*args, input=input)
    assert r.exit_code == 0, r.output
    return json.loads(r.stdout)


def fail(*args, input=None):
    r = invoke(*args, input=input)
    assert r.exit_code == 1, r.output
    return json.loads(r.stderr)


def write(tmp_path, name, payload):
    path = tmp_path / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def setup(tmp_path):
    cid = ok("course", "add", "--name", "Algoritmalar")["id"]
    docs = {}
    for name, pages in [("slayt.pdf", ["Siralama"]), ("midterm.pdf", ["S1", "S2"])]:
        f = tmp_path / name
        f.write_bytes(make_pdf(*pages))
        docs[name] = ok("ingest", f, "--course", cid)["document"]["id"]
    return cid, docs["slayt.pdf"], docs["midterm.pdf"]


DIFF = {"steps": 3, "input_size": 6, "concept_count": 1, "bloom_level": "apply", "est_minutes": 8}


def test_full_analysis_flow(tmp_path, setup):
    cid, slides, exam = setup

    t = ok("topic", "import", "--course", cid, "--json",
           write(tmp_path, "t.json", [{"key": "sort", "name": "Sıralama"}]))
    assert t["created"] == ["sort"]

    ok("objective", "import", "--course", cid, "--json", write(tmp_path, "o.json", [
        {"key": "sort.trace", "topic_key": "sort", "text": "Sıralamayı izle", "bloom_level": "apply",
         "source_document_id": slides, "source_pages": [1]},
    ]))

    q = ok("question", "import", "--course", cid, "--json", write(tmp_path, "q.json", [
        {"document_id": exam, "label": "1", "page_no": 1, "text": "Merge sort izle", "points": 15,
         "difficulty": DIFF},
        {"document_id": exam, "label": "2", "page_no": 2, "text": "Konu dışı soru", "difficulty": DIFF},
    ]))
    assert q["created"] == [f"{exam}:1", f"{exam}:2"]

    axes = {"algoritma": ["merge", "quick", "heap"]}
    ok("archetype", "import", "--course", cid, "--json", write(tmp_path, "a.json", [
        {"key": "sort.trace.exam", "objective_key": "sort.trace", "skill": "Sıralamayı izle",
         "angle": "trace", "variation_axes": axes, "origin": "exam",
         "source_questions": [{"document_id": exam, "label": "1"}]},
        {"key": "sort.trace.edge", "objective_key": "sort.trace", "skill": "Kenar durumlarda davranış",
         "angle": "edge_case", "variation_axes": {"girdi": ["boş", "tek eleman", "hepsi eşit"]},
         "origin": "model"},
    ]))

    profile = ok("profile", "compute", "--course", cid)
    assert profile["sample_size"] == 2 and profile["steps"] == 3

    check = ok("course", "check", "--course", cid)
    assert check["ok"] is True
    assert check["unmapped_questions"] == [f"{exam}:2"]

    m = ok("course", "map", "--course", cid, "--no-text")
    obj = m["topics"][0]["objectives"][0]
    assert obj["weight"] == 2.0
    assert [a["angle"] for a in obj["archetypes"]] == ["trace", "edge_case"]
    assert obj["archetypes"][0]["source_questions"][0]["text"] is None
    assert m["profile"]["sample_size"] == 2

    unmapped = ok("question", "list", "--course", cid, "--unmapped")
    assert [u["label"] for u in unmapped] == ["2"]


def test_import_from_stdin_and_dry_run(setup):
    cid, _, _ = setup
    r = ok("topic", "import", "--course", cid, "--json", "-", "--dry-run",
           input='[{"key": "graf", "name": "Graflar"}]')
    assert r["dry_run"] is True
    assert ok("course", "map", "--course", cid)["topics"] == []


def test_schema_error_reports_location(setup):
    cid, _, _ = setup
    err = fail("objective", "import", "--course", cid, "--json", "-",
               input='[{"key": "x", "topic_key": "t", "text": "x", "bloom_level": "ezber"}]')
    assert err["error"] == "Geçersiz JSON şeması"
    assert err["details"][0]["loc"] == [0, "bloom_level"]


def test_reference_error_reports_details(setup):
    cid, _, _ = setup
    err = fail("objective", "import", "--course", cid, "--json", "-",
               input='[{"key": "x", "topic_key": "yok", "text": "x", "bloom_level": "apply"}]')
    assert "konu yok" in err["details"][0]


def test_merge_command(tmp_path, setup):
    cid, _, exam = setup
    ok("topic", "import", "--course", cid, "--json", "-", input='[{"key": "s", "name": "S"}]')
    ok("objective", "import", "--course", cid, "--json", "-",
       input='[{"key": "o", "topic_key": "s", "text": "x", "bloom_level": "apply"}]')
    ok("question", "import", "--course", cid, "--json", write(tmp_path, "q.json", [
        {"document_id": exam, "label": l, "page_no": 1, "text": f"soru {l}"} for l in ("1", "2")
    ]))
    base = {"objective_key": "o", "skill": "izle", "angle": "trace",
            "variation_axes": {"a": ["1", "2"]}, "origin": "exam"}
    ok("archetype", "import", "--course", cid, "--json", write(tmp_path, "a.json", [
        {**base, "key": "a1", "source_questions": [{"document_id": exam, "label": "1"}]},
        {**base, "key": "a2", "source_questions": [{"document_id": exam, "label": "2"}]},
    ]))

    merged = ok("archetype", "merge", "--course", cid, "--into", "a1", "--from", "a2")
    assert [q["label"] for q in merged["source_questions"]] == ["1", "2"]
    assert "bulunamadı" in fail("archetype", "merge", "--course", cid, "--into", "a1", "--from", "a2")["error"]


def test_profile_without_questions_fails(setup):
    cid, _, _ = setup
    assert "Zorluk bilgisi" in fail("profile", "compute", "--course", cid)["error"]


def test_unknown_course(setup):
    assert "Ders bulunamadı" in fail("course", "map", "--course", 99)["error"]
    assert "Ders bulunamadı" in fail("course", "check", "--course", 99)["error"]
