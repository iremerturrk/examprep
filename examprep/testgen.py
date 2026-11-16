"""Test üretimi: taslak (compose), soru içe aktarma, doğrulama, benzerlik, hakem, tamamlama.

Akış (skill /hafta-testi bunu sırayla çağırır):
  compose_test → [Claude soruları yazar] → import_generated → verify_test → similarity_test
  → [ayrı hakem puanlar] → judge → finalize_test

Bir soru `accepted` olur: doğrulamadan geçmiş (ya da kavramsal / doğrulanamaz), benzerlik
eşiğinin altında (çıkmış sorularda atlanır) ve hakem kararı `ok` (çıkmış sorularda karar
yalnızca kaydedilir) ise.
"""

import math
import random
import secrets
from collections import Counter
from datetime import UTC, datetime
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from examprep.analysis import AnalysisError, _get_profile, _require_course
from examprep.models import (
    AnswerType,
    ArchetypeOrigin,
    Attempt,
    BloomLevel,
    DocType,
    GeneratedQuestion,
    LearningObjective,
    QuestionArchetype,
    QuestionKind,
    QuestionStatus,
    SlotType,
    SourceQuestion,
    Test,
    TestFormat,
    TestSlot,
    TestStatus,
    Tier,
)
from examprep.schemas import (
    AnchorOut,
    GeneratedQuestionIn,
    GeneratedQuestionOut,
    JudgeIn,
    MeasuredObjectiveOut,
    SlotOut,
    TestOut,
)
from examprep.similarity import Embedder, assess
from examprep.verify import run_check

# Öncelik ve kota ayarları
NEW_BOOST = 3.0  # hiç test edilmemiş kazanım
REVIEW_MAX_DAYS = 28  # tekrar çarpanı 1 + min(gün, 28)/7  → en fazla 5
PAST_RATIO = 0.2  # çıkmış soru slotları
NEW_RATIO = 0.4  # üretim slotlarında yeni kazanım kotası
SOURCE_ORIGIN_RATIO = 0.5  # üretim slotlarında sınav/ödev kökenli kalıp hedefi
MAX_PER_OBJECTIVE = 2
RECENT_PAST_TESTS = 3  # çıkmış soru, son bu kadar testte sorulduysa tekrar seçilmez
MAX_ATTEMPTS_PER_SLOT = 3
CHOICES = 4  # A–D
DIFF_FIELDS = ("steps", "input_size", "concept_count", "est_minutes")


def _utcnow() -> datetime:
    # SQLite server_default (CURRENT_TIMESTAMP) UTC yazar; karşılaştırmalar da UTC olmalı
    return datetime.now(UTC).replace(tzinfo=None)


# --- Öncelik ---


def _objective_history(session: Session, course_id: int) -> dict[int, datetime]:
    rows = session.execute(
        select(TestSlot.objective_id, Test.created_at)
        .join(Test, TestSlot.test_id == Test.id)
        .where(Test.course_id == course_id, Test.status == TestStatus.ready)
    ).all()
    last: dict[int, datetime] = {}
    for oid, created in rows:
        if oid not in last or created > last[oid]:
            last[oid] = created
    return last


def _wrong_rates(session: Session, course_id: int) -> dict[int, float]:
    rows = session.execute(
        select(TestSlot.objective_id, Attempt.correct)
        .join(GeneratedQuestion, GeneratedQuestion.id == Attempt.question_id)
        .join(TestSlot, TestSlot.id == GeneratedQuestion.slot_id)
        .join(Test, Test.id == TestSlot.test_id)
        .where(Test.course_id == course_id)
    ).all()
    total, wrong = Counter(), Counter()
    for oid, correct in rows:
        total[oid] += 1
        wrong[oid] += not correct
    return {oid: wrong[oid] / total[oid] for oid in total}


def objective_priorities(session: Session, course_id: int, now: datetime | None = None,
                         approved_only: bool = False) -> list[tuple[LearningObjective, float, bool]]:
    """(kazanım, öncelik, yeni_mi) listesi. Yalnızca en az bir kalıbı olan kazanımlar."""
    now = now or _utcnow()
    last, wrong = _objective_history(session, course_id), _wrong_rates(session, course_id)
    out = []
    for obj in session.scalars(select(LearningObjective).where(LearningObjective.course_id == course_id)
                               .order_by(LearningObjective.id)):
        archetypes = [a for a in obj.archetypes if a.approved or not approved_only]
        if not archetypes or (approved_only and not obj.approved):
            continue
        is_new = obj.id not in last
        factor = NEW_BOOST if is_new else 1 + min((now - last[obj.id]).days, REVIEW_MAX_DAYS) / 7
        priority = obj.effective_weight * factor * (1 + wrong.get(obj.id, 0.0))
        out.append((obj, round(priority, 4), is_new))
    return out


def _weighted_pick(rng: random.Random, items: list, weights: list[float]):
    return rng.choices(items, weights=weights, k=1)[0]


# --- Çapalar ve hedef zorluk ---


def _anchors(obj: LearningObjective, rng: random.Random, k: int = 3) -> list[SourceQuestion]:
    pool = {q.id: q for a in obj.archetypes for q in a.source_questions
            if q.document.doc_type is DocType.exam and q.difficulty}
    ids = sorted(pool)
    return [pool[i] for i in sorted(rng.sample(ids, min(k, len(ids))))]


def _target(anchors: list[SourceQuestion], profile) -> dict | None:
    if anchors:
        diffs = [q.difficulty for q in anchors]
        t = {f: median(d[f] for d in diffs) for f in DIFF_FIELDS}
        t["bloom_level"] = median(BloomLevel(d["bloom_level"]).rank for d in diffs)
        t["edge_cases"] = sorted({e for d in diffs for e in d.get("edge_cases", [])})
        t["source"] = "anchors"
        return t
    if profile is not None:
        return {"steps": profile.steps, "input_size": profile.input_size, "concept_count": profile.concept_count,
                "est_minutes": profile.est_minutes, "bloom_level": profile.bloom_level,
                "edge_cases": list(profile.edge_cases.get("frequency", {}))[:5], "source": "course_profile"}
    return None


# --- Taslak ---


def _used_count(session: Session, archetype_id: int) -> int:
    return len(session.scalars(select(GeneratedQuestion.id).where(
        GeneratedQuestion.archetype_id == archetype_id,
        GeneratedQuestion.status != QuestionStatus.rejected,
        GeneratedQuestion.kind == QuestionKind.generated)).all())


def _choose_archetype(session, obj, rng, in_test: Counter, origin_counts: Counter, n_gen: int,
                      approved_only: bool) -> QuestionArchetype:
    candidates = [a for a in obj.archetypes if a.approved or not approved_only]
    wanted_source = origin_counts["source"] < math.ceil(n_gen * SOURCE_ORIGIN_RATIO)

    def key(a: QuestionArchetype):
        is_source = a.origin in (ArchetypeOrigin.exam, ArchetypeOrigin.homework)
        balance = 0 if is_source == wanted_source else 0.5
        return (in_test[a.id], _used_count(session, a.id) + balance, rng.random())

    return min(candidates, key=key)


def compose_test(session: Session, course_id: int, size: int = 10, seed: int | None = None,
                 now: datetime | None = None, approved_only: bool = False) -> Test:
    """Haritanın tamamından yeni bir test taslağı oluşturur (deterministik: aynı seed → aynı taslak)."""
    _require_course(session, course_id)
    if not 1 <= size <= 40:
        raise AnalysisError("Test büyüklüğü 1 ile 40 arasında olmalı")
    seed = seed if seed is not None else secrets.randbelow(2**31)
    rng = random.Random(seed)
    pri = objective_priorities(session, course_id, now, approved_only)
    if not pri:
        raise AnalysisError("Kalıbı olan kazanım yok; önce /ders-analiz çalıştırın"
                            + (" ya da kazanımları onaylayın" if approved_only else ""))
    by_id = {o.id: (o, p, new) for o, p, new in pri}
    profile = _get_profile(session, course_id)

    # Çıkmış soru adayları: kalıba bağlı, son testlerde çıkmış soru olarak sorulmamış
    recent_tests = session.scalars(select(Test.id).where(Test.course_id == course_id, Test.status == TestStatus.ready)
                                   .order_by(Test.id.desc()).limit(RECENT_PAST_TESTS)).all()
    recently_asked = set(session.scalars(select(TestSlot.source_question_id).where(
        TestSlot.test_id.in_(recent_tests), TestSlot.slot_type == SlotType.past)))
    past_candidates = []
    for obj, p, _ in pri:
        for a in obj.archetypes:
            if a.origin in (ArchetypeOrigin.exam, ArchetypeOrigin.homework) and (a.approved or not approved_only):
                for q in a.source_questions:
                    if q.id not in recently_asked:
                        past_candidates.append((q, obj, a, p))
    seen_q, unique_past = set(), []
    for q, obj, a, p in past_candidates:
        if q.id not in seen_q:
            seen_q.add(q.id)
            unique_past.append((q, obj, a, p))

    n_past = min(round(size * PAST_RATIO) if size >= 3 else 0, len(unique_past))
    n_gen = size - n_past
    per_obj: Counter = Counter()
    chosen: list[tuple[str, LearningObjective, float]] = []

    # 1) yeni kazanım kotası
    new_pool = [(o, p) for o, p, new in pri if new]
    n_new = min(math.ceil(n_gen * NEW_RATIO), sum(MAX_PER_OBJECTIVE for _ in new_pool))
    while len(chosen) < n_new:
        avail = [(o, p) for o, p in new_pool if per_obj[o.id] < MAX_PER_OBJECTIVE]
        if not avail:
            break
        o, p = _weighted_pick(rng, avail, [p for _, p in avail])
        per_obj[o.id] += 1
        chosen.append((SlotType.new.value, o, p))
    # 2) kalan üretim slotları: tüm kazanımlardan ağırlıklı
    while len(chosen) < n_gen:
        avail = [(o, p, new) for o, p, new in pri if per_obj[o.id] < MAX_PER_OBJECTIVE]
        if not avail:
            break
        o, p, new = _weighted_pick(rng, avail, [p for _, p, _ in avail])
        per_obj[o.id] += 1
        chosen.append(((SlotType.new if new else SlotType.review).value, o, p))

    test = Test(course_id=course_id, seed=seed, size=size, status=TestStatus.draft)
    session.add(test)
    slots: list[TestSlot] = []
    in_test: Counter = Counter()
    origin_counts: Counter = Counter()
    for slot_type, obj, p in chosen:
        arch = _choose_archetype(session, obj, rng, in_test, origin_counts, len(chosen), approved_only)
        in_test[arch.id] += 1
        origin_counts["source" if arch.origin in (ArchetypeOrigin.exam, ArchetypeOrigin.homework) else "model"] += 1
        anchors = _anchors(obj, rng)
        slots.append(TestSlot(slot_type=SlotType(slot_type), objective=obj, archetype=arch, priority=p,
                              anchor_ids=[q.id for q in anchors], target_difficulty=_target(anchors, profile)))
    # 3) çıkmış sorular
    for _ in range(n_past):
        q, obj, a, p = _weighted_pick(rng, unique_past, [x[3] for x in unique_past])
        unique_past = [x for x in unique_past if x[0].id != q.id]
        slots.append(TestSlot(slot_type=SlotType.past, objective=obj, archetype=a, priority=p,
                              source_question=q, anchor_ids=[],
                              target_difficulty=_target([q] if q.difficulty else [], profile)))
    rng.shuffle(slots)
    for pos, slot in enumerate(slots, 1):
        slot.position = pos
        test.slots.append(slot)
    session.commit()
    return test


# --- Kazanım testi (şıklı, üç bölüm) ---

DEFAULT_SECTIONS = {"basic": 20, "medium": 10, "exam": 5}
EXAM_MIN_POINTS = 3
BASIC_TARGET = {"steps": 1, "input_size": 0, "concept_count": 1, "est_minutes": 1.0, "bloom_level": 1.5,
                "edge_cases": [], "source": "tier_basic", "tier": "basic"}


def _medium_target(profile) -> dict:
    base = {"steps": 3, "input_size": 4, "concept_count": 2, "est_minutes": 3.0, "bloom_level": 3.5}
    if profile is not None:  # profilden daha düşük olmasın
        base["steps"] = max(base["steps"], profile.steps or 0)
        base["est_minutes"] = max(base["est_minutes"], profile.est_minutes or 0)
    return {**base, "edge_cases": [], "source": "tier_medium", "tier": "medium"}


def _topic_sort_key(obj: LearningObjective) -> tuple:
    chain, t = [], obj.topic
    while t is not None:
        chain.append(t.order)
        t = t.parent
    return (*reversed(chain), obj.order, obj.id)


def _sample_objectives(rng, pool: list[tuple], n: int, taken: Counter, cap: int) -> list[tuple]:
    """Önceliğe göre ağırlıklı, tekrarsız seçim; havuz yetmezse cap'e kadar tekrar."""
    chosen = []
    for limit in range(1, cap + 1):
        while len(chosen) < n:
            avail = [x for x in pool if taken[x[0].id] < limit]
            if not avail:
                break
            pick = _weighted_pick(rng, avail, [x[1] for x in avail])
            taken[pick[0].id] += 1
            chosen.append(pick)
        if len(chosen) >= n:
            break
    return chosen


def compose_kazanim_test(session: Session, course_id: int, sections: dict | None = None, seed: int | None = None,
                         now: datetime | None = None, approved_only: bool = False) -> Test:
    """Şıklı kazanım testi taslağı: Temel (geniş kapsam) → Orta → Sınav düzeyi (çıkmış soruya paralel)."""
    _require_course(session, course_id)
    sections = {**DEFAULT_SECTIONS, **(sections or {})}
    if any(v < 0 for v in sections.values()) or not 1 <= sum(sections.values()) <= 80:
        raise AnalysisError("Bölüm boyutları 0 ya da pozitif olmalı, toplam 1–80")
    seed = seed if seed is not None else secrets.randbelow(2**31)
    rng = random.Random(seed)
    pri = objective_priorities(session, course_id, now, approved_only)
    if not pri:
        raise AnalysisError("Kalıbı olan kazanım yok; önce /ders-analiz çalıştırın")
    profile = _get_profile(session, course_id)
    usable = lambda a: a.approved or not approved_only  # noqa: E731

    # Sınav düzeyi: kalıba bağlı, zorluk bilgisi olan sınav soruları; son testlerde paralel yapılmamış
    recent = session.scalars(select(Test.id).where(Test.course_id == course_id, Test.status == TestStatus.ready)
                             .order_by(Test.id.desc()).limit(RECENT_PAST_TESTS)).all()
    recently_parallel = set(session.scalars(select(TestSlot.parallel_question_id).where(TestSlot.test_id.in_(recent))))
    by_obj = {o.id: (o, p, new) for o, p, new in pri}
    exam_cands, seen = [], set()
    for o, p, _ in pri:
        for a in o.archetypes:
            if not usable(a):
                continue
            for q in a.source_questions:
                if (q.id not in seen and q.id not in recently_parallel and q.document.doc_type is DocType.exam
                        and q.difficulty):
                    seen.add(q.id)
                    exam_cands.append((q, o, a, p * max(q.points or 1, 1) ** 1.5))
    # sınav düzeyi tipik sınav görevlerini temsil etsin: yeterince varsa ≥ EXAM_MIN_POINTS puanlılar
    substantial = [c for c in exam_cands if (c[0].points or 0) >= EXAM_MIN_POINTS]
    if len(substantial) >= sections["exam"]:
        exam_cands = substantial
    exam_slots = []
    exam_taken: Counter = Counter()
    while len(exam_slots) < sections["exam"] and exam_cands:
        avail = [c for c in exam_cands if exam_taken[c[1].id] == 0] or exam_cands
        q, o, a, w = _weighted_pick(rng, avail, [c[3] for c in avail])
        exam_cands = [c for c in exam_cands if c[0].id != q.id]
        exam_taken[o.id] += 1
        archetype = next((x for x in o.archetypes if q in x.source_questions and x.origin is ArchetypeOrigin.exam
                          and usable(x)), a)
        exam_slots.append(TestSlot(tier=Tier.exam, slot_type=SlotType.new if by_obj[o.id][2] else SlotType.review,
                                   objective=o, archetype=archetype, priority=by_obj[o.id][1],
                                   parallel_question=q, anchor_ids=[q.id],
                                   target_difficulty={**_target([q], profile), "tier": "exam"}))

    # Temel: geniş kapsam, kazanım başına bir soru (havuz yetmezse iki)
    basic_taken: Counter = Counter()
    basic = _sample_objectives(rng, pri, sections["basic"], basic_taken, cap=2)
    # Orta: yeni kazanımlar ve temel bölümdekiler öncelikli (pekiştirme), kazanım başına bir soru
    in_basic = {o.id for o, _, _ in basic}
    medium_pool = [(o, p * (1.5 if o.id in in_basic else 1.0), new) for o, p, new in pri]
    medium = _sample_objectives(rng, medium_pool, sections["medium"], Counter(), cap=2)

    in_test: Counter = Counter()
    origin_counts: Counter = Counter()

    def make(tier: Tier, o, p, new) -> TestSlot:
        cands = [a for a in o.archetypes if usable(a)]
        if tier is Tier.basic:  # temel: açıklama/hesaplama/izleme açıları, en az kullanılan
            simple = [a for a in cands if a.angle.value in ("explain", "compute", "trace")] or cands
            arch = min(simple, key=lambda a: (in_test[a.id], _used_count(session, a.id), rng.random()))
        else:
            arch = _choose_archetype(session, o, rng, in_test, origin_counts, len(medium), approved_only)
            origin_counts["source" if arch.origin is not ArchetypeOrigin.model else "model"] += 1
        in_test[arch.id] += 1
        anchors = _anchors(o, rng) if tier is Tier.medium else []
        target = BASIC_TARGET if tier is Tier.basic else _medium_target(profile)
        return TestSlot(tier=tier, slot_type=SlotType.new if new else SlotType.review, objective=o,
                        archetype=arch, priority=p, anchor_ids=[q.id for q in anchors], target_difficulty=target)

    ordered = (sorted((make(Tier.basic, *x) for x in basic), key=lambda s: _topic_sort_key(s.objective))
               + sorted((make(Tier.medium, *x) for x in medium), key=lambda s: _topic_sort_key(s.objective))
               + sorted(exam_slots, key=lambda s: _topic_sort_key(s.objective)))
    test = Test(course_id=course_id, seed=seed, size=len(ordered), format=TestFormat.kazanim,
                config={"sections": sections}, status=TestStatus.draft)
    session.add(test)
    for pos, slot in enumerate(ordered, 1):
        slot.position = pos
        test.slots.append(slot)
    session.commit()
    return test


# --- Görüntüleme ---


def _question_out(q: GeneratedQuestion) -> GeneratedQuestionOut:
    return GeneratedQuestionOut(
        id=q.id, kind=q.kind, status=q.status, reject_reason=q.reject_reason, prompt=q.prompt,
        answer=q.answer, answer_type=q.answer_type, choices=q.choices, explanation=q.explanation,
        params=q.params or {}, verification=q.verification, similarity=q.similarity,
        judge=q.difficulty_scores or None,
    )


def _anchor_out(q: SourceQuestion) -> AnchorOut:
    return AnchorOut(ref=f"{q.document_id}:{q.label}", text=q.text, points=q.points, difficulty=q.difficulty)


def _used_params(session: Session, archetype_id: int) -> list[dict]:
    return [p for p in session.scalars(select(GeneratedQuestion.params).where(
        GeneratedQuestion.archetype_id == archetype_id, GeneratedQuestion.kind == QuestionKind.generated,
        GeneratedQuestion.status != QuestionStatus.rejected)) if p]


def _get_test(session: Session, test_id: int) -> Test:
    test = session.get(Test, test_id)
    if test is None:
        raise AnalysisError(f"Test bulunamadı: {test_id}")
    return test


def test_out(session: Session, test_id: int, with_slots: bool = True) -> TestOut:
    test = _get_test(session, test_id)
    counts = Counter(s.slot_type.value for s in test.slots)
    counts.update(f"q_{s.current_question.status.value}" if s.current_question else "q_missing" for s in test.slots)
    slots = []
    if with_slots:
        for s in test.slots:
            a, o = s.archetype, s.objective
            anchors = [session.get(SourceQuestion, i) for i in s.anchor_ids]
            slots.append(SlotOut(
                slot_id=s.id, position=s.position, slot_type=s.slot_type, priority=s.priority, tier=s.tier,
                parallel_question=_anchor_out(s.parallel_question) if s.parallel_question else None,
                objective_key=o.key, objective_text=o.text, bloom_level=o.bloom_level,
                archetype_key=a.key, skill=a.skill, angle=a.angle, origin=a.origin, variation_axes=a.variation_axes,
                used_params=_used_params(session, a.id),
                anchors=[_anchor_out(q) for q in anchors if q is not None],
                target_difficulty=s.target_difficulty,
                past_question=_anchor_out(s.source_question) if s.source_question else None,
                past_solution=s.source_question.solution if s.source_question else None,
                question=_question_out(s.current_question) if s.current_question else None,
                attempts=len(s.questions),
            ))
    objectives = []
    seen = set()
    for sl in test.slots:
        o = sl.objective
        if o.id not in seen:
            seen.add(o.id)
            objectives.append(MeasuredObjectiveOut(id=o.id, key=o.key, text=o.text, bloom_level=o.bloom_level,
                                                   basis=o.basis, active_cards=sum(c.active for c in o.cards)))
    counts.update(s.tier.value for s in test.slots if s.tier is not None)
    return TestOut(id=test.id, course_id=test.course_id, format=test.format, config=test.config, status=test.status,
                   seed=test.seed, size=test.size, created_at=test.created_at, finalized_at=test.finalized_at,
                   counts=dict(counts), objectives=objectives, slots=slots)


def list_tests(session: Session, course_id: int) -> list[TestOut]:
    _require_course(session, course_id)
    ids = session.scalars(select(Test.id).where(Test.course_id == course_id).order_by(Test.id)).all()
    return [test_out(session, i, with_slots=False) for i in ids]


# --- Soru içe aktarma ---


def _draft_slot(session: Session, slot_id: int) -> TestSlot:
    slot = session.get(TestSlot, slot_id)
    if slot is None:
        raise AnalysisError(f"Slot bulunamadı: {slot_id}")
    if slot.test.status is not TestStatus.draft:
        raise AnalysisError(f"Test {slot.test_id} tamamlanmış; slot değiştirilemez")
    return slot


def import_generated(session: Session, items: list[GeneratedQuestionIn]) -> list[dict]:
    errors = []
    for n, item in enumerate(items):
        try:
            slot = _draft_slot(session, item.slot_id)
        except AnalysisError as exc:
            errors.append(f"[{n}] {exc}")
            continue
        if len(slot.questions) >= MAX_ATTEMPTS_PER_SLOT:
            errors.append(f"[{n}] slot {slot.id}: en fazla {MAX_ATTEMPTS_PER_SLOT} deneme; slotu atlayın")
        if slot.slot_type is SlotType.past:
            if item.params:
                errors.append(f"[{n}] slot {slot.id}: çıkmış soru slotunda params verilmez")
            continue
        if not item.prompt or not item.prompt.strip():
            errors.append(f"[{n}] slot {slot.id}: prompt gerekli")
        if slot.tier is not None:
            if item.answer_type is not AnswerType.choice or not item.choices or len(item.choices) != CHOICES:
                errors.append(f"[{n}] slot {slot.id}: kazanım testinde answer_type=choice ve tam {CHOICES} şık gerekli")
            elif len(set(item.choices)) != CHOICES:
                errors.append(f"[{n}] slot {slot.id}: şıklar birbirinden farklı olmalı")
        axes = slot.archetype.variation_axes
        for k, v in item.params.items():
            if k not in axes:
                errors.append(f"[{n}] slot {slot.id}: bilinmeyen eksen '{k}' (eksenler: {sorted(axes)})")
            elif v not in axes[k]:
                errors.append(f"[{n}] slot {slot.id}: '{k}' için '{v}' kalıpta yok (kapsam kilidi): {axes[k]}")
    if errors:
        raise AnalysisError("Üretilen sorular içe aktarılamadı", errors)

    created = []
    for item in items:
        slot = session.get(TestSlot, item.slot_id)
        previous = slot.current_question
        if previous is not None:
            previous.status, previous.reject_reason = QuestionStatus.rejected, "yerine yeni soru eklendi"
        past = slot.slot_type is SlotType.past
        q = GeneratedQuestion(
            archetype_id=slot.archetype_id, kind=QuestionKind.past if past else QuestionKind.generated,
            source_question_id=slot.source_question_id if past else None,
            prompt=slot.source_question.text if past else item.prompt.strip(),
            answer=item.answer, answer_type=item.answer_type, choices=item.choices, explanation=item.explanation,
            params=item.params, check=item.check.model_dump() if item.check else None, status=QuestionStatus.draft,
        )
        slot.questions.append(q)
        session.flush()
        created.append({"slot_id": slot.id, "question_id": q.id})
    session.commit()
    return created


# --- Kapılar: doğrulama, benzerlik, hakem ---


def _reject(q: GeneratedQuestion, reason: str) -> None:
    q.status, q.reject_reason = QuestionStatus.rejected, reason


def _refresh_status(q: GeneratedQuestion) -> None:
    if q.status is not QuestionStatus.draft:
        return
    verified = q.verification is not None and q.verification["status"] in ("passed", "unverified", "undetermined")
    similar_ok = q.kind is QuestionKind.past or (q.similarity is not None and not q.similarity.get("too_similar"))
    judged = bool(q.difficulty_scores) and (q.kind is QuestionKind.past or q.difficulty_scores.get("verdict") == "ok")
    if verified and similar_ok and judged:
        q.status = QuestionStatus.accepted


def _draft_questions(session: Session, test_id: int) -> list[GeneratedQuestion]:
    test = _get_test(session, test_id)
    return [s.current_question for s in test.slots
            if s.current_question is not None and s.current_question.status is QuestionStatus.draft]


def verify_test(session: Session, test_id: int) -> list[dict]:
    out = []
    for q in _draft_questions(session, test_id):
        if q.check:
            result = run_check(q.check)
            q.verification = result
            q.verified = result["status"] == "passed"
            if result["status"] in ("failed", "error"):
                detail = "; ".join(result.get("mismatches") or [result.get("error", "")])
                _reject(q, f"doğrulama ({result['checker']}): {detail}")
        else:
            q.verification = {"status": "unverified", "checker": None,
                              "details": "kavramsal soru / check bloğu yok"}
        _refresh_status(q)
        out.append({"question_id": q.id, "slot_id": q.slot_id, "verification": q.verification["status"],
                    "status": q.status.value, "reject_reason": q.reject_reason})
    session.commit()
    return out


def similarity_test(session: Session, test_id: int, embedder: Embedder | None = None,
                    threshold: float | None = None) -> list[dict]:
    test = _get_test(session, test_id)
    todo = [q for q in _draft_questions(session, test_id) if q.kind is QuestionKind.generated]
    results = assess(session, test.course_id, [q.prompt for q in todo], embedder, threshold) if todo else []
    out = []
    for q, sim in zip(todo, results):
        q.similarity = sim
        if sim["too_similar"]:
            _reject(q, f"benzerlik ({sim['rule']}): {sim['ref']} ile kosinüs {sim['score']:.2f}, "
                       f"veri örtüşmesi {sim['overlap']:.0%}")
        _refresh_status(q)
        out.append({"question_id": q.id, "slot_id": q.slot_id, "score": sim["score"], "overlap": sim["overlap"],
                    "ref": sim["ref"], "rule": sim["rule"], "status": q.status.value})
    session.commit()
    return out


def judge_verdict(scores: dict, target: dict | None) -> tuple[str, list[str]]:
    """Hakem puanlarını hedef zorlukla karşılaştırır: ok | scale_up | scale_down | reject."""
    if not target:
        return "ok", ["hedef zorluk yok (profil hesaplanmamış)"]
    tier = target.get("tier")
    if tier in ("basic", "medium"):
        return _tier_verdict(tier, scores)
    if tier == "exam" and target.get("est_minutes"):
        target = {**target, "est_minutes": float(target["est_minutes"]) * MC_TIME_FACTOR}
    issues, direction = [], []
    bloom_diff = BloomLevel(scores["bloom_level"]).rank - float(target["bloom_level"])
    if abs(bloom_diff) > 1:
        issues.append(f"bloom: {scores['bloom_level']} (hedef ~{target['bloom_level']})")
        return "reject", issues
    for f in ("steps", "input_size", "est_minutes"):
        t, s = float(target.get(f) or 0), float(scores[f])
        if t > 0:
            ratio = s / t
            if ratio < 0.5:
                issues.append(f"{f}: {s:g} < hedef {t:g}'in yarısı")
                direction.append("scale_up")
            elif ratio > 2:
                issues.append(f"{f}: {s:g} > hedef {t:g}'in iki katı")
                direction.append("scale_down")
        elif s - t > 5:
            issues.append(f"{f}: {s:g}, hedef ~0")
            direction.append("scale_down")
    if not direction:
        return "ok", issues
    return Counter(direction).most_common(1)[0][0], issues


TIER_BOUNDS = {  # (min, max) — dışında kalırsa scale_up / scale_down (şıklı sorular için kalibre)
    "basic": {"steps": (0, 4), "est_minutes": (0, 2.5), "bloom": (1, 3)},
    "medium": {"steps": (2, 8), "est_minutes": (1.0, 7), "bloom": (3, 5)},
}
MC_TIME_FACTOR = 0.5  # şıklı paralel soru, açık uçlu orijinalinden yaklaşık iki kat hızlı çözülür


def _tier_verdict(tier: str, scores: dict) -> tuple[str, list[str]]:
    b = TIER_BOUNDS[tier]
    values = {"steps": float(scores["steps"]), "est_minutes": float(scores["est_minutes"]),
              "bloom": BloomLevel(scores["bloom_level"]).rank}
    issues, direction = [], []
    for k, (lo, hi) in b.items():
        if values[k] < lo:
            issues.append(f"{k}: {values[k]:g} < {tier} alt sınırı {lo}")
            direction.append("scale_up")
        elif values[k] > hi:
            issues.append(f"{k}: {values[k]:g} > {tier} üst sınırı {hi}")
            direction.append("scale_down")
    if not direction:
        return "ok", issues
    return Counter(direction).most_common(1)[0][0], issues


def judge(session: Session, items: list[JudgeIn]) -> list[dict]:
    out = []
    for item in items:
        q = session.get(GeneratedQuestion, item.question_id)
        if q is None or q.slot is None:
            raise AnalysisError(f"Test sorusu bulunamadı: {item.question_id}")
        if q.status is not QuestionStatus.draft:
            out.append({"question_id": q.id, "skipped": f"durum {q.status.value}"})
            continue
        scores = item.scores.model_dump(mode="json")
        verdict, issues = judge_verdict(scores, q.slot.target_difficulty)
        quality = [msg for ok, msg in ((item.answer_ok, "cevap yanlış"), (item.single_correct, "birden fazla doğru şık"),
                                       (item.distractors_ok, "yanlış şıklar zayıf")) if not ok]
        if quality:
            verdict, issues = "reject", [*quality, *issues]
        q.difficulty_scores = {"scores": scores, "target": q.slot.target_difficulty, "verdict": verdict,
                               "issues": issues, "comment": item.comment}
        if verdict != "ok" and q.kind is QuestionKind.generated:
            _reject(q, f"hakem: {verdict} ({'; '.join(issues)})")
        _refresh_status(q)
        out.append({"question_id": q.id, "slot_id": q.slot_id, "verdict": verdict, "issues": issues,
                    "status": q.status.value})
    session.commit()
    return out


def finalize_test(session: Session, test_id: int, allow_partial: bool = False) -> TestOut:
    """Tüm slotlarda kabul edilmiş soru varsa testi hazır yapar.

    allow_partial: deneme hakkı biten (kabul edilmiş sorusu olmayan) slotları testten çıkarır.
    """
    test = _get_test(session, test_id)
    if test.status is TestStatus.ready:
        raise AnalysisError(f"Test {test_id} zaten tamamlanmış")
    missing = [s for s in test.slots
               if s.current_question is None or s.current_question.status is not QuestionStatus.accepted]
    if missing and not allow_partial:
        raise AnalysisError("Kabul edilmiş sorusu olmayan slotlar var", [
            f"slot {s.id} (#{s.position}): " + (s.current_question.status.value if s.current_question else "soru yok")
            for s in missing])
    for s in missing:
        session.delete(s)
    session.flush()
    session.expire(test, ["slots"])
    if not test.slots:
        raise AnalysisError("Testte hiç kabul edilmiş soru yok")
    for pos, s in enumerate(test.slots, 1):
        s.position = pos
    test.status, test.finalized_at = TestStatus.ready, _utcnow()
    session.commit()
    return test_out(session, test_id)


def discard_test(session: Session, test_id: int, force: bool = False) -> None:
    """Testi siler. Tamamlanmış testler (ve çözümleri) yalnızca force ile silinir."""
    test = _get_test(session, test_id)
    if test.status is TestStatus.ready and not force:
        raise AnalysisError("Tamamlanmış test silinemez (gönderimleri de silinir; --force gerekir)")
    session.delete(test)
    session.commit()
