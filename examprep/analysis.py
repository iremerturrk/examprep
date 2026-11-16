"""Kazanım haritası işlemleri: toplu import (upsert), düzenleme, ağırlık ve profil hesabı.

CLI ve Streamlit aynı fonksiyonları kullanır. Import kuralları:
- Kayıtlar ders içinde tekil `key` ile (kaynak sorular belge_id + etiket ile) eşleşir.
- Kullanıcının onayladığı kayıtların üzerine yazılmaz, `skipped_approved` olarak raporlanır.
- Bir import tek işlemdir: herhangi bir satırda hata varsa hiçbir şey yazılmaz.
"""

from collections import Counter
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from examprep.models import (
    ArchetypeOrigin,
    BloomLevel,
    Course,
    DifficultyProfile,
    DocType,
    LearningObjective,
    QuestionArchetype,
    SourceDocument,
    SourceQuestion,
    Topic,
)
from examprep.schemas import (
    ArchetypeEdit,
    ArchetypeIn,
    ArchetypeOut,
    CourseMap,
    CoverageOut,
    ImportResult,
    ObjectiveEdit,
    ObjectiveIn,
    ObjectiveOut,
    ProfileOut,
    SourceQuestionIn,
    SourceQuestionOut,
    TopicNode,
    TopicOut,
)

MIN_ANGLES = 2  # her kazanım en az bu kadar farklı açıdan kalıpla kapsanmalı
EXAM_WEIGHT = 1.0
HOMEWORK_WEIGHT = 0.5


class AnalysisError(Exception):
    def __init__(self, message: str, details: list[str] | None = None):
        super().__init__(message)
        self.details = details or []


def _require_course(session: Session, course_id: int) -> Course:
    course = session.get(Course, course_id)
    if course is None:
        raise AnalysisError(f"Ders bulunamadı: {course_id}")
    return course


def _check_duplicates(keys: list[str], what: str) -> None:
    dupes = [k for k, n in Counter(keys).items() if n > 1]
    if dupes:
        raise AnalysisError(f"Dosyada tekrar eden {what}", dupes)


def _finish(session: Session, result: ImportResult, dry_run: bool) -> ImportResult:
    if dry_run:
        session.rollback()
        result.dry_run = True
    else:
        session.commit()
    return result


def _by_key(session: Session, model, course_id: int) -> dict:
    return {o.key: o for o in session.scalars(select(model).where(model.course_id == course_id))}


# --- Import ---


def import_topics(
    session: Session, course_id: int, nodes: list[TopicNode], dry_run: bool = False
) -> ImportResult:
    _require_course(session, course_id)
    flat: list[tuple[TopicNode, str | None, int]] = []

    def walk(items: list[TopicNode], parent_key: str | None) -> None:
        for order, node in enumerate(items):
            flat.append((node, parent_key, order))
            walk(node.children, node.key)

    walk(nodes, None)
    _check_duplicates([n.key for n, _, _ in flat], "konu anahtarları")

    existing = _by_key(session, Topic, course_id)
    result = ImportResult()
    for node, parent_key, order in flat:  # ebeveyn her zaman çocuktan önce gelir
        topic = existing.get(node.key)
        if topic is not None and topic.approved:
            result.skipped_approved.append(node.key)
            continue
        parent = existing[parent_key] if parent_key else None
        if topic is None:
            topic = Topic(course_id=course_id, key=node.key)
            session.add(topic)
            existing[node.key] = topic
            result.created.append(node.key)
        else:
            result.updated.append(node.key)
        topic.name = node.name
        topic.parent = parent
        topic.order = order

    session.flush()
    _check_topic_cycles(list(existing.values()))
    return _finish(session, result, dry_run)


def _check_topic_cycles(topics: list[Topic]) -> None:
    for topic in topics:
        seen, node = set(), topic
        while node is not None:
            if node.key in seen:
                raise AnalysisError("Konu ağacında döngü oluştu", [topic.key])
            seen.add(node.key)
            node = node.parent


def import_objectives(
    session: Session, course_id: int, items: list[ObjectiveIn], dry_run: bool = False
) -> ImportResult:
    _require_course(session, course_id)
    _check_duplicates([i.key for i in items], "kazanım anahtarları")
    topics = _by_key(session, Topic, course_id)
    doc_ids = set(session.scalars(select(SourceDocument.id).where(SourceDocument.course_id == course_id)))

    errors = []
    for n, item in enumerate(items):
        if item.topic_key not in topics:
            errors.append(f"[{n}] {item.key}: konu yok: {item.topic_key}")
        if item.source_document_id is not None and item.source_document_id not in doc_ids:
            errors.append(f"[{n}] {item.key}: belge bu derse ait değil: {item.source_document_id}")
    if errors:
        raise AnalysisError("Kazanımlar içe aktarılamadı", errors)

    existing = _by_key(session, LearningObjective, course_id)
    order_in_topic: Counter[str] = Counter()
    result = ImportResult()
    for item in items:
        order = order_in_topic[item.topic_key]
        order_in_topic[item.topic_key] += 1
        obj = existing.get(item.key)
        if obj is not None and obj.approved:
            result.skipped_approved.append(item.key)
            continue
        if obj is None:
            obj = LearningObjective(course_id=course_id, key=item.key)
            session.add(obj)
            result.created.append(item.key)
        else:
            result.updated.append(item.key)
        obj.topic = topics[item.topic_key]
        obj.text = item.text
        obj.bloom_level = item.bloom_level
        obj.order = order
        obj.source_document_id = item.source_document_id
        obj.source_pages = list(item.source_pages)
    return _finish(session, result, dry_run)


def import_questions(
    session: Session, course_id: int, items: list[SourceQuestionIn], dry_run: bool = False
) -> ImportResult:
    _require_course(session, course_id)
    _check_duplicates([f"{i.document_id}:{i.label}" for i in items], "soru referansları")
    docs = {
        d.id: d
        for d in session.scalars(select(SourceDocument).where(SourceDocument.course_id == course_id))
    }

    errors = []
    for n, item in enumerate(items):
        doc = docs.get(item.document_id)
        ref = f"{item.document_id}:{item.label}"
        if doc is None:
            errors.append(f"[{n}] {ref}: belge bu derse ait değil")
        elif doc.doc_type is DocType.slides:
            errors.append(f"[{n}] {ref}: kaynak soru yalnızca sınav/ödev belgesinden gelebilir")
        elif item.page_no > doc.page_count:
            errors.append(f"[{n}] {ref}: sayfa {item.page_no} yok (belge {doc.page_count} sayfa)")
    if errors:
        raise AnalysisError("Sorular içe aktarılamadı", errors)

    existing = {
        (q.document_id, q.label): q
        for q in session.scalars(
            select(SourceQuestion).where(SourceQuestion.document_id.in_(docs.keys()))
        )
    }
    result = ImportResult()
    for item in items:
        ref = f"{item.document_id}:{item.label}"
        q = existing.get((item.document_id, item.label))
        if q is None:
            q = SourceQuestion(document_id=item.document_id, label=item.label)
            session.add(q)
            result.created.append(ref)
        else:
            result.updated.append(ref)
        q.page_no = item.page_no
        q.text = item.text
        q.points = item.points
        q.solution = item.solution
        q.difficulty = item.difficulty.model_dump(mode="json") if item.difficulty else None
    return _finish(session, result, dry_run)


def _course_questions(session: Session, course_id: int) -> dict[str, SourceQuestion]:
    rows = session.scalars(
        select(SourceQuestion).join(SourceDocument).where(SourceDocument.course_id == course_id)
    )
    return {f"{q.document_id}:{q.label}": q for q in rows}


def _origin_from_questions(questions: list[SourceQuestion]) -> ArchetypeOrigin | None:
    if not questions:
        return None
    if any(q.document.doc_type is DocType.exam for q in questions):
        return ArchetypeOrigin.exam
    return ArchetypeOrigin.homework


def import_archetypes(
    session: Session, course_id: int, items: list[ArchetypeIn], dry_run: bool = False
) -> ImportResult:
    _require_course(session, course_id)
    _check_duplicates([i.key for i in items], "kalıp anahtarları")
    objectives = _by_key(session, LearningObjective, course_id)
    questions = _course_questions(session, course_id)

    errors = []
    for n, item in enumerate(items):
        if item.objective_key not in objectives:
            errors.append(f"[{n}] {item.key}: kazanım yok: {item.objective_key} (kapsam kilidi)")
        missing = [r.ref for r in item.source_questions if r.ref not in questions]
        if missing:
            errors.append(f"[{n}] {item.key}: kaynak soru yok: {', '.join(missing)}")
            continue
        expected = _origin_from_questions([questions[r.ref] for r in item.source_questions])
        if expected is not None and item.origin is not expected:
            errors.append(
                f"[{n}] {item.key}: bağlı sorulara göre origin={expected.value} olmalı "
                f"(verilen: {item.origin.value})"
            )
    if errors:
        raise AnalysisError("Kalıplar içe aktarılamadı", errors)

    existing = _by_key(session, QuestionArchetype, course_id)
    result = ImportResult()
    for item in items:
        arch = existing.get(item.key)
        if arch is not None and arch.approved:
            result.skipped_approved.append(item.key)
            continue
        if arch is None:
            arch = QuestionArchetype(course_id=course_id, key=item.key)
            session.add(arch)
            result.created.append(item.key)
        else:
            result.updated.append(item.key)
        arch.objective = objectives[item.objective_key]
        arch.skill = item.skill
        arch.angle = item.angle
        arch.variation_axes = item.variation_axes
        arch.origin = item.origin
        arch.source_url = item.source_url
        arch.source_questions = [questions[r.ref] for r in item.source_questions]
    session.flush()
    recompute_weights(session, course_id)
    return _finish(session, result, dry_run)


def merge_archetypes(
    session: Session, course_id: int, into_key: str, from_keys: list[str]
) -> ArchetypeOut:
    """from_keys kalıplarının kaynak sorularını into_key'e taşır ve onları siler."""
    archetypes = _by_key(session, QuestionArchetype, course_id)
    missing = [k for k in [into_key, *from_keys] if k not in archetypes]
    if missing:
        raise AnalysisError("Kalıp bulunamadı", missing)
    if into_key in from_keys:
        raise AnalysisError("Bir kalıp kendisiyle birleştirilemez", [into_key])
    target = archetypes[into_key]
    others = [archetypes[k] for k in from_keys]
    foreign = [a.key for a in others if a.learning_objective_id != target.learning_objective_id]
    if foreign:
        raise AnalysisError("Yalnızca aynı kazanımın kalıpları birleştirilebilir", foreign)

    merged = list(target.source_questions)
    for arch in others:
        merged += [q for q in arch.source_questions if q not in merged]
        session.delete(arch)
    target.source_questions = merged
    target.origin = _origin_from_questions(merged) or target.origin
    session.flush()
    recompute_weights(session, course_id)
    session.commit()
    return _archetype_out(target, with_text=True)


# --- Ağırlık ve profil ---


def recompute_weights(session: Session, course_id: int) -> None:
    """Kazanım ağırlığı = 1 + bağlı sınav sorusu × 1 + bağlı ödev sorusu × 0.5."""
    for obj in session.scalars(
        select(LearningObjective).where(LearningObjective.course_id == course_id)
    ):
        linked = {q.id: q for a in obj.archetypes for q in a.source_questions}.values()
        obj.weight = 1.0 + sum(
            EXAM_WEIGHT if q.document.doc_type is DocType.exam else HOMEWORK_WEIGHT for q in linked
        )


def compute_profile(session: Session, course_id: int) -> ProfileOut:
    """Sınav sorularının zorluk özelliklerinden DifficultyProfile hesaplar (medyan)."""
    _require_course(session, course_id)
    diffs = [
        q.difficulty
        for q in _course_questions(session, course_id).values()
        if q.document.doc_type is DocType.exam and q.difficulty
    ]
    if not diffs:
        raise AnalysisError("Zorluk bilgisi olan sınav sorusu yok; önce `question import` çalıştırın.")

    edge_counts = Counter(tag for d in diffs for tag in d.get("edge_cases", []))
    profile = _get_profile(session, course_id) or DifficultyProfile(course_id=course_id)
    profile.steps = median(d["steps"] for d in diffs)
    profile.input_size = median(d["input_size"] for d in diffs)
    profile.concept_count = median(d["concept_count"] for d in diffs)
    profile.bloom_level = median(BloomLevel(d["bloom_level"]).rank for d in diffs)
    profile.est_minutes = median(d["est_minutes"] for d in diffs)
    profile.edge_cases = {
        "per_question_median": median(len(d.get("edge_cases", [])) for d in diffs),
        "frequency": dict(edge_counts.most_common()),
    }
    profile.sample_size = len(diffs)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return ProfileOut.model_validate(profile)


# --- Okuma ---


def _get_profile(session: Session, course_id: int) -> DifficultyProfile | None:
    # İlişki üzerinden okumak, oturumda önbelleğe alınmış eski None değerini döndürebilir.
    return session.scalar(select(DifficultyProfile).where(DifficultyProfile.course_id == course_id))


def _question_out(q: SourceQuestion, with_text: bool) -> SourceQuestionOut:
    return SourceQuestionOut(
        id=q.id,
        ref=f"{q.document_id}:{q.label}",
        document_id=q.document_id,
        document_filename=q.document.filename,
        doc_type=q.document.doc_type,
        label=q.label,
        page_no=q.page_no,
        text=q.text if with_text else None,
        points=q.points,
        solution=q.solution if with_text else None,
        difficulty=q.difficulty,
        archetype_keys=[a.key for a in q.archetypes],
    )


def _archetype_out(a: QuestionArchetype, with_text: bool) -> ArchetypeOut:
    return ArchetypeOut(
        id=a.id,
        key=a.key,
        skill=a.skill,
        angle=a.angle,
        variation_axes=a.variation_axes,
        origin=a.origin,
        source_url=a.source_url,
        approved=a.approved,
        source_questions=[_question_out(q, with_text) for q in a.source_questions],
    )


def _objective_out(o: LearningObjective, with_text: bool) -> ObjectiveOut:
    return ObjectiveOut(
        id=o.id,
        key=o.key,
        text=o.text,
        bloom_level=o.bloom_level,
        source_document_id=o.source_document_id,
        source_pages=o.source_pages,
        weight=o.weight,
        weight_override=o.weight_override,
        effective_weight=o.effective_weight,
        approved=o.approved,
        archetypes=[_archetype_out(a, with_text) for a in o.archetypes],
    )


def _topic_out(t: Topic, with_text: bool) -> TopicOut:
    return TopicOut(
        id=t.id,
        key=t.key,
        name=t.name,
        approved=t.approved,
        objectives=[_objective_out(o, with_text) for o in t.objectives],
        children=[_topic_out(c, with_text) for c in t.children],
    )


def list_questions(
    session: Session, course_id: int, unmapped_only: bool = False, with_text: bool = True
) -> list[SourceQuestionOut]:
    _require_course(session, course_id)
    qs = sorted(_course_questions(session, course_id).values(), key=lambda q: (q.document_id, q.id))
    if unmapped_only:
        qs = [q for q in qs if not q.archetypes]
    return [_question_out(q, with_text) for q in qs]


def coverage(session: Session, course_id: int) -> CoverageOut:
    _require_course(session, course_id)
    objectives = session.scalars(
        select(LearningObjective).where(LearningObjective.course_id == course_id)
    ).all()
    archetypes = session.scalars(
        select(QuestionArchetype).where(QuestionArchetype.course_id == course_id)
    ).all()
    topics = session.scalars(select(Topic).where(Topic.course_id == course_id)).all()
    questions = list(_course_questions(session, course_id).values())

    without = [o.key for o in objectives if not o.archetypes]
    few = [
        o.key for o in objectives if o.archetypes and len({a.angle for a in o.archetypes}) < MIN_ANGLES
    ]
    no_diff = [
        f"{q.document_id}:{q.label}"
        for q in questions
        if q.document.doc_type is DocType.exam and not q.difficulty
    ]
    unapproved = sum(not x.approved for x in [*topics, *objectives, *archetypes])
    return CoverageOut(
        objective_count=len(objectives),
        archetype_count=len(archetypes),
        source_question_count=len(questions),
        objectives_without_archetypes=without,
        objectives_with_few_angles=few,
        unmapped_questions=[f"{q.document_id}:{q.label}" for q in questions if not q.archetypes],
        questions_without_difficulty=no_diff,
        unapproved_count=unapproved,
        ok=bool(objectives) and not without and not few and not no_diff,
    )


def get_course_map(session: Session, course_id: int, with_text: bool = True) -> CourseMap:
    course = _require_course(session, course_id)
    roots = session.scalars(
        select(Topic)
        .where(Topic.course_id == course_id, Topic.parent_id.is_(None))
        .order_by(Topic.order, Topic.id)
    ).all()
    profile = _get_profile(session, course_id)
    return CourseMap(
        course_id=course.id,
        course_name=course.name,
        topics=[_topic_out(t, with_text) for t in roots],
        unmapped_questions=list_questions(session, course_id, unmapped_only=True, with_text=with_text),
        coverage=coverage(session, course_id),
        profile=ProfileOut.model_validate(profile) if profile else None,
    )


# --- Arayüz düzenlemeleri ---


def _get(session: Session, model, obj_id: int):
    obj = session.get(model, obj_id)
    if obj is None:
        raise AnalysisError(f"Kayıt bulunamadı: {model.__name__} {obj_id}")
    return obj


def rename_topic(session: Session, topic_id: int, name: str) -> None:
    name = name.strip()
    if not name:
        raise AnalysisError("Konu adı boş olamaz")
    _get(session, Topic, topic_id).name = name
    session.commit()


def update_objective(session: Session, objective_id: int, data: ObjectiveEdit) -> None:
    obj = _get(session, LearningObjective, objective_id)
    obj.text = data.text
    obj.bloom_level = data.bloom_level
    obj.weight_override = data.weight_override
    session.commit()


def update_archetype(session: Session, archetype_id: int, data: ArchetypeEdit) -> None:
    arch = _get(session, QuestionArchetype, archetype_id)
    arch.skill = data.skill
    arch.angle = data.angle
    arch.variation_axes = data.variation_axes
    session.commit()


def unlink_question(session: Session, archetype_id: int, question_id: int) -> None:
    arch = _get(session, QuestionArchetype, archetype_id)
    arch.source_questions = [q for q in arch.source_questions if q.id != question_id]
    if arch.origin in (ArchetypeOrigin.exam, ArchetypeOrigin.homework):
        arch.origin = _origin_from_questions(arch.source_questions) or ArchetypeOrigin.model
    session.flush()
    recompute_weights(session, arch.course_id)
    session.commit()


def delete_item(session: Session, model, obj_id: int) -> None:
    """Konu, kazanım, kalıp ya da kaynak soruyu siler (alt kayıtlar da silinir)."""
    obj = _get(session, model, obj_id)
    course_id = obj.document.course_id if model is SourceQuestion else obj.course_id
    session.delete(obj)
    session.flush()
    session.expire_all()
    recompute_weights(session, course_id)
    session.commit()


def set_approved(session: Session, model, obj_id: int, approved: bool) -> None:
    _get(session, model, obj_id).approved = approved
    session.commit()


def approve_topic_tree(session: Session, topic_id: int) -> int:
    """Konuyu, alt konularını, kazanımlarını ve kalıplarını onaylar. Onaylanan kayıt sayısını döndürür."""
    count = 0

    def walk(t: Topic) -> None:
        nonlocal count
        items = [t, *t.objectives, *(a for o in t.objectives for a in o.archetypes)]
        count += sum(not x.approved for x in items)
        for x in items:
            x.approved = True
        for child in t.children:
            walk(child)

    walk(_get(session, Topic, topic_id))
    session.commit()
    return count
