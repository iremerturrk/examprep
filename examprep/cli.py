"""Komut satırı arayüzü: `python -m examprep ...`

Tüm çıktılar stdout'a JSON olarak yazılır. Hatalar stderr'e {"error": ...} olarak
yazılır ve çıkış kodu 1 olur. Claude Code skill'leri veritabanına yalnızca bu
komutlar üzerinden erişir.
"""

import json
import sys
from pathlib import Path
from typing import Annotated, NoReturn

import typer
from pydantic import BaseModel, TypeAdapter, ValidationError
from sqlalchemy import select

from examprep import analysis, config
from examprep.analysis import AnalysisError
from examprep.courses import CourseExistsError, create_course, list_courses
from examprep.db import init_db, session_scope
from examprep.ingest import IngestError, guess_doc_type, ingest_document
from examprep.models import DocType, DocumentPage, SourceDocument
from examprep.schemas import (
    ArchetypeIn,
    CourseIn,
    DocumentOut,
    IngestResult,
    ObjectiveIn,
    PageOut,
    SourceQuestionIn,
    TopicNode,
)

app = typer.Typer(no_args_is_help=True, add_completion=False, help="ExamPrep CLI")
course_app = typer.Typer(no_args_is_help=True, help="Ders işlemleri")
doc_app = typer.Typer(no_args_is_help=True, help="Belge ve sayfa okuma")
app.add_typer(course_app, name="course")
app.add_typer(doc_app, name="doc")
topic_app = typer.Typer(no_args_is_help=True, help="Konu ağacı")
objective_app = typer.Typer(no_args_is_help=True, help="Kazanımlar")
question_app = typer.Typer(no_args_is_help=True, help="Kaynak (çıkmış) sorular")
archetype_app = typer.Typer(no_args_is_help=True, help="Soru kalıpları")
profile_app = typer.Typer(no_args_is_help=True, help="Zorluk profili")
app.add_typer(topic_app, name="topic")
app.add_typer(objective_app, name="objective")
app.add_typer(question_app, name="question")
app.add_typer(archetype_app, name="archetype")
app.add_typer(profile_app, name="profile")

CourseOpt = Annotated[int, typer.Option("--course", help="Ders id")]
JsonOpt = Annotated[str, typer.Option("--json", help="JSON dosyası ('-' = stdin)")]
DryRunOpt = Annotated[bool, typer.Option("--dry-run", help="Doğrula ve raporla, yazma")]


@app.callback()
def _setup() -> None:
    init_db()


def _emit(data: BaseModel | list[BaseModel]) -> None:
    if isinstance(data, list):
        payload = [d.model_dump(mode="json") for d in data]
    else:
        payload = data.model_dump(mode="json")
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def _fail(message: str, details: object = None) -> NoReturn:
    err: dict[str, object] = {"error": message}
    if details is not None:
        err["details"] = details
    typer.echo(json.dumps(err, ensure_ascii=False), err=True)
    raise typer.Exit(1)


def _read_json(source: str) -> object:
    """Dosya yolundan ya da '-' ise stdin'den JSON okur."""
    try:
        raw = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
        return json.loads(raw)
    except FileNotFoundError:
        _fail(f"JSON dosyası bulunamadı: {source}")
    except json.JSONDecodeError as exc:
        _fail(f"Geçersiz JSON: {exc}")


def _validation_details(exc: ValidationError) -> list[dict]:
    return [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]


@course_app.command("add")
def course_add(
    name: Annotated[str | None, typer.Option(help="Ders adı")] = None,
    code: Annotated[str | None, typer.Option(help="Ders kodu")] = None,
    exam_date: Annotated[str | None, typer.Option(help="Sınav tarihi (YYYY-AA-GG)")] = None,
    json_input: Annotated[
        str | None, typer.Option("--json", help="CourseIn JSON dosyası ('-' = stdin)")
    ] = None,
) -> None:
    """Yeni ders oluşturur."""
    if json_input is not None:
        if any(v is not None for v in (name, code, exam_date)):
            _fail("--json ile diğer seçenekler birlikte kullanılamaz.")
        raw = _read_json(json_input)
    else:
        raw = {"name": name or "", "code": code, "exam_date": exam_date}
    try:
        data = CourseIn.model_validate(raw)
    except ValidationError as exc:
        _fail("Geçersiz ders verisi", _validation_details(exc))
    with session_scope() as s:
        try:
            _emit(create_course(s, data))
        except CourseExistsError as exc:
            _fail(str(exc))


@course_app.command("list")
def course_list() -> None:
    """Dersleri listeler."""
    with session_scope() as s:
        _emit(list_courses(s))


@app.command("ingest")
def ingest(
    pdf: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    course: Annotated[int, typer.Option(help="Ders id")],
    doc_type: Annotated[
        DocType | None,
        typer.Option("--type", help="Belge türü (verilmezse dosya adından tahmin edilir)"),
    ] = None,
) -> None:
    """PDF'i işler: sayfa metni + görüntüsü çıkarır ve kaydeder."""
    with session_scope() as s:
        try:
            doc, created = ingest_document(
                s, course, pdf.name, pdf.read_bytes(), doc_type or guess_doc_type(pdf.name)
            )
        except IngestError as exc:
            _fail(str(exc))
        _emit(IngestResult(document=DocumentOut.model_validate(doc), created=created))


@doc_app.command("list")
def doc_list(
    course: Annotated[int, typer.Option(help="Ders id")],
    doc_type: Annotated[DocType | None, typer.Option("--type", help="Türe göre filtrele")] = None,
) -> None:
    """Bir dersin belgelerini listeler."""
    with session_scope() as s:
        q = select(SourceDocument).where(SourceDocument.course_id == course)
        if doc_type is not None:
            q = q.where(SourceDocument.doc_type == doc_type)
        docs = s.scalars(q.order_by(SourceDocument.id)).all()
        _emit([DocumentOut.model_validate(d) for d in docs])


@doc_app.command("pages")
def doc_pages(
    document_id: Annotated[int, typer.Argument(help="Belge id")],
    start: Annotated[int, typer.Option(min=1, help="İlk sayfa")] = 1,
    end: Annotated[int | None, typer.Option(min=1, help="Son sayfa (dahil)")] = None,
    scanned_only: Annotated[bool, typer.Option(help="Yalnızca taranmış sayfalar")] = False,
) -> None:
    """Belgenin sayfa metinlerini ve görüntü yollarını verir."""
    with session_scope() as s:
        if s.get(SourceDocument, document_id) is None:
            _fail(f"Belge bulunamadı: {document_id}")
        q = select(DocumentPage).where(
            DocumentPage.document_id == document_id, DocumentPage.page_no >= start
        )
        if end is not None:
            q = q.where(DocumentPage.page_no <= end)
        if scanned_only:
            q = q.where(DocumentPage.is_scanned.is_(True))
        pages = s.scalars(q.order_by(DocumentPage.page_no)).all()
        _emit(
            [
                PageOut(
                    page_no=p.page_no,
                    text=p.text,
                    image_path=str((config.DATA_DIR / p.image_path).resolve()),
                    char_count=p.char_count,
                    is_scanned=p.is_scanned,
                )
                for p in pages
            ]
        )


def _import(source: str, schema, run) -> None:
    """JSON listesini doğrular, import fonksiyonunu çalıştırır ve sonucu yazar."""
    raw = _read_json(source)
    try:
        items = TypeAdapter(list[schema]).validate_python(raw)
    except ValidationError as exc:
        _fail("Geçersiz JSON şeması", _validation_details(exc))
    with session_scope() as s:
        try:
            _emit(run(s, items))
        except AnalysisError as exc:
            _fail(str(exc), exc.details or None)


@topic_app.command("import")
def topic_import(course: CourseOpt, json_input: JsonOpt, dry_run: DryRunOpt = False) -> None:
    """İç içe konu ağacını içe aktarır: [{key, name, children: [...]}]."""
    _import(json_input, TopicNode, lambda s, items: analysis.import_topics(s, course, items, dry_run))


@objective_app.command("import")
def objective_import(course: CourseOpt, json_input: JsonOpt, dry_run: DryRunOpt = False) -> None:
    """Kazanımları içe aktarır: [{key, topic_key, text, bloom_level, ...}]."""
    _import(
        json_input, ObjectiveIn, lambda s, items: analysis.import_objectives(s, course, items, dry_run)
    )


@question_app.command("import")
def question_import(course: CourseOpt, json_input: JsonOpt, dry_run: DryRunOpt = False) -> None:
    """Sınav/ödev sorularını içe aktarır: [{document_id, label, page_no, text, ...}]."""
    _import(
        json_input,
        SourceQuestionIn,
        lambda s, items: analysis.import_questions(s, course, items, dry_run),
    )


@question_app.command("list")
def question_list(
    course: CourseOpt,
    unmapped: Annotated[bool, typer.Option(help="Yalnızca hiçbir kalıba bağlı olmayanlar")] = False,
    text: Annotated[bool, typer.Option(help="Soru metni ve çözümü dahil et")] = True,
) -> None:
    """Dersin kaynak sorularını listeler."""
    with session_scope() as s:
        try:
            _emit(analysis.list_questions(s, course, unmapped_only=unmapped, with_text=text))
        except AnalysisError as exc:
            _fail(str(exc))


@archetype_app.command("import")
def archetype_import(course: CourseOpt, json_input: JsonOpt, dry_run: DryRunOpt = False) -> None:
    """Soru kalıplarını içe aktarır: [{key, objective_key, skill, angle, variation_axes, origin, ...}]."""
    _import(
        json_input, ArchetypeIn, lambda s, items: analysis.import_archetypes(s, course, items, dry_run)
    )


@archetype_app.command("merge")
def archetype_merge(
    course: CourseOpt,
    into: Annotated[str, typer.Option("--into", help="Kalacak kalıbın anahtarı")],
    sources: Annotated[list[str], typer.Option("--from", help="Birleştirilecek kalıp (tekrarlanabilir)")],
) -> None:
    """Aynı kazanımdaki kalıpları birleştirir; kaynak sorular --into kalıbında toplanır."""
    with session_scope() as s:
        try:
            _emit(analysis.merge_archetypes(s, course, into, sources))
        except AnalysisError as exc:
            _fail(str(exc), exc.details or None)


@profile_app.command("compute")
def profile_compute(course: CourseOpt) -> None:
    """Sınav sorularının zorluk özelliklerinden DifficultyProfile hesaplar."""
    with session_scope() as s:
        try:
            _emit(analysis.compute_profile(s, course))
        except AnalysisError as exc:
            _fail(str(exc))


@course_app.command("map")
def course_map(
    course: CourseOpt,
    text: Annotated[bool, typer.Option(help="Soru metni ve çözümü dahil et")] = True,
) -> None:
    """Dersin tüm kazanım haritası: konu ağacı, kazanımlar, kalıplar, kaynak sorular, kapsam."""
    with session_scope() as s:
        try:
            _emit(analysis.get_course_map(s, course, with_text=text))
        except AnalysisError as exc:
            _fail(str(exc))


@course_app.command("check")
def course_check(course: CourseOpt) -> None:
    """Kapsam kontrolü: kalıbı olmayan / tek açılı kazanımlar, eşlenmemiş sorular."""
    with session_scope() as s:
        try:
            _emit(analysis.coverage(s, course))
        except AnalysisError as exc:
            _fail(str(exc))


def main() -> None:
    app()

