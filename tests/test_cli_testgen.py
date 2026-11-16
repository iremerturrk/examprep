"""Test üretim komutlarının uçtan uca CLI testi (skill'in izleyeceği sıra)."""

import json

import pytest
from typer.testing import CliRunner

from conftest import make_pdf
from examprep import config, db, similarity
from examprep.cli import app
from test_testgen import FakeEmbedder

runner = CliRunner()


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(similarity, "_default", FakeEmbedder())
    db.reset_engine()
    yield
    db.reset_engine()


def ok(*args, input=None):
    r = runner.invoke(app, [str(a) for a in args], input=input)
    assert r.exit_code == 0, r.output
    return json.loads(r.stdout)


def fail(*args, input=None):
    r = runner.invoke(app, [str(a) for a in args], input=input)
    assert r.exit_code == 1, r.output
    return json.loads(r.stderr)


@pytest.fixture
def course_id(tmp_path):
    cid = ok("course", "add", "--name", "Algo")["id"]
    f = tmp_path / "klausur.pdf"
    f.write_bytes(make_pdf("Aufgabe 1"))
    exam = ok("ingest", f, "--course", cid, "--type", "exam")["document"]["id"]
    ok("topic", "import", "--course", cid, "--json", "-", input='[{"key": "t", "name": "T"}]')
    ok("objective", "import", "--course", cid, "--json", "-",
       input=json.dumps([{"key": f"o{i}", "topic_key": "t", "text": f"K{i}", "bloom_level": "apply"} for i in (1, 2)]))
    diff = {"steps": 3, "input_size": 3, "concept_count": 1, "bloom_level": "apply", "est_minutes": 4}
    ok("question", "import", "--course", cid, "--json", "-", input=json.dumps(
        [{"document_id": exam, "label": "1", "page_no": 1, "text": "Rucksack mit drei Gegenständen lösen", "difficulty": diff}]))
    axes = {"n": ["3", "4"]}
    ok("archetype", "import", "--course", cid, "--json", "-", input=json.dumps([
        {"key": "a1", "objective_key": "o1", "skill": "s", "angle": "compute", "variation_axes": axes, "origin": "exam",
         "source_questions": [{"document_id": exam, "label": "1"}]},
        {"key": "a2", "objective_key": "o2", "skill": "s", "angle": "explain", "variation_axes": axes, "origin": "model"},
    ]))
    return cid


def test_compose_generate_check_finalize(course_id):
    test = ok("test", "compose", "--course", course_id, "--size", 3, "--seed", 5)
    assert test["status"] == "draft" and len(test["slots"]) == 3
    tid = test["id"]

    check = {"checker": "knapsack.solve", "input": {"items": [{"name": "a", "w": 2, "g": 1}], "M": 1},
             "expected": {"value": 2}}
    items = []
    for s in test["slots"]:
        if s["slot_type"] == "past":
            items.append({"slot_id": s["slot_id"], "answer": "Musterlösung"})
        else:
            items.append({"slot_id": s["slot_id"], "prompt": f"Neue Aufgabe {s['slot_id']} Graph Färbung",
                          "answer": "2", "answer_type": "numeric", "params": {"n": "4"}, "check": check})
    created = ok("gen", "import", "--json", "-", input=json.dumps(items))
    assert len(created) == 3

    verified = ok("verify", "run", tid)
    assert {v["verification"] for v in verified} <= {"passed", "unverified"}
    ok("similarity", "check", tid, "--threshold", "0.99")
    judge = [{"question_id": c["question_id"],
              "scores": {"steps": 3, "input_size": 3, "concept_count": 1, "bloom_level": "apply", "est_minutes": 4}}
             for c in created]
    verdicts = ok("gen", "judge", "--json", "-", input=json.dumps(judge))
    assert {v["verdict"] for v in verdicts} == {"ok"}

    final = ok("test", "finalize", tid)
    assert final["status"] == "ready" and final["counts"]["q_accepted"] == 3
    assert [t["id"] for t in ok("test", "list", "--course", course_id)] == [tid]
    assert "zaten" in fail("test", "finalize", tid)["error"]
    assert "Tamamlanmış" in fail("test", "discard", tid)["error"]


def test_import_errors_are_reported(course_id):
    test = ok("test", "compose", "--course", course_id, "--size", 2, "--seed", 1)
    slot = test["slots"][0]
    err = fail("gen", "import", "--json", "-",
               input=json.dumps([{"slot_id": slot["slot_id"], "prompt": "p", "answer": "x", "params": {"n": "9"}}]))
    assert "kapsam kilidi" in err["details"][0]
    err = fail("gen", "import", "--json", "-", input='[{"slot_id": 1, "answer": "x", "answer_type": "choice"}]')
    assert err["error"] == "Geçersiz JSON şeması"


def test_verify_list_and_unknown_test(course_id):
    assert "knapsack.solve" in ok("verify", "list")
    assert "Test bulunamadı" in fail("test", "show", 99)["error"]
    assert "Test bulunamadı" in fail("verify", "run", 99)["error"]


def test_discard_draft(course_id):
    tid = ok("test", "compose", "--course", course_id, "--size", 2)["id"]
    assert ok("test", "discard", tid) == {"discarded": tid}
    assert ok("test", "list", "--course", course_id) == []
