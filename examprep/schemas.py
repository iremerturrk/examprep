"""CLI giriş/çıkış şemaları. Skill'ler CLI'ye bu şemalara uyan JSON gönderir ve alır."""

from datetime import date, datetime
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from examprep.models import (
    AnswerType,
    Angle,
    ArchetypeOrigin,
    BloomLevel,
    DocStatus,
    DocType,
    QuestionKind,
    QuestionStatus,
    SlotType,
    TestStatus,
)

# Skill'in verdiği kalıcı anahtar: küçük harf, rakam, nokta, tire, alt çizgi.
Key = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^[a-z0-9][a-z0-9._-]*$", max_length=200),
]
NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CourseIn(_In):
    name: str = Field(min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=50)
    exam_date: date | None = None

    @field_validator("code")
    @classmethod
    def _empty_code_is_none(cls, v: str | None) -> str | None:
        return v or None


class CourseOut(_Out):
    id: int
    name: str
    code: str | None
    exam_date: date | None
    document_count: int = 0


class DocumentOut(_Out):
    id: int
    course_id: int
    filename: str
    doc_type: DocType
    sha256: str
    page_count: int
    status: DocStatus
    uploaded_at: datetime


class IngestResult(BaseModel):
    document: DocumentOut
    created: bool


class PageOut(BaseModel):
    page_no: int
    text: str
    image_path: str = Field(description="Sayfa görüntüsünün mutlak yolu")
    char_count: int
    is_scanned: bool


# --- Analiz girdileri (skill -> CLI) ---


class TopicNode(_In):
    key: Key
    name: NonEmpty
    children: list["TopicNode"] = []


class ObjectiveIn(_In):
    key: Key
    topic_key: Key
    text: NonEmpty
    bloom_level: BloomLevel
    source_document_id: int | None = None
    source_pages: list[Annotated[int, Field(ge=1)]] = []


class DifficultyIn(_In):
    steps: int = Field(ge=0, description="Çözümdeki ayrı işlem/adım sayısı")
    input_size: int = Field(ge=0, description="Verilen verinin boyutu (dizi uzunluğu, düğüm sayısı...)")
    concept_count: int = Field(ge=1, description="Sorunun birlikte kullandığı kavram sayısı")
    bloom_level: BloomLevel
    est_minutes: float = Field(gt=0, description="Tahmini çözüm süresi (dakika)")
    edge_cases: list[NonEmpty] = []


class SourceQuestionIn(_In):
    document_id: int
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    page_no: int = Field(ge=1)
    text: NonEmpty
    points: float | None = Field(default=None, ge=0)
    solution: str | None = None
    difficulty: DifficultyIn | None = None


class QuestionRef(_In):
    document_id: int
    label: NonEmpty

    @property
    def ref(self) -> str:
        return f"{self.document_id}:{self.label}"


def validate_variation_axes(axes: dict[str, list[str]]) -> dict[str, list[str]]:
    if not axes:
        raise ValueError("En az bir varyasyon ekseni gerekli")
    cleaned: dict[str, list[str]] = {}
    for name, values in axes.items():
        name = name.strip()
        values = list(dict.fromkeys(v.strip() for v in values if v.strip()))
        if not name:
            raise ValueError("Eksen adı boş olamaz")
        if len(values) < 2:
            raise ValueError(f"'{name}' ekseninde en az 2 farklı değer olmalı")
        cleaned[name] = values
    return cleaned


class ArchetypeEdit(_In):
    """Kalıbın düzenlenebilir alanları (arayüz ve import ortak kullanır)."""

    skill: NonEmpty
    angle: Angle
    variation_axes: dict[str, list[str]]

    @field_validator("variation_axes")
    @classmethod
    def _axes(cls, v: dict[str, list[str]]) -> dict[str, list[str]]:
        return validate_variation_axes(v)


class ArchetypeIn(ArchetypeEdit):
    key: Key
    objective_key: Key
    origin: ArchetypeOrigin
    source_url: str | None = None
    source_questions: list[QuestionRef] = []

    @model_validator(mode="after")
    def _origin_rules(self) -> Self:
        if self.origin is ArchetypeOrigin.web and not self.source_url:
            raise ValueError("origin=web için source_url gerekli")
        if self.origin in (ArchetypeOrigin.exam, ArchetypeOrigin.homework) and not self.source_questions:
            raise ValueError(f"origin={self.origin.value} için en az bir kaynak soru gerekli")
        if self.origin is ArchetypeOrigin.model and self.source_questions:
            raise ValueError("origin=model kalıbı kaynak soruya bağlanamaz (bağlıysa origin exam/homework olmalı)")
        return self


class ObjectiveEdit(_In):
    text: NonEmpty
    bloom_level: BloomLevel
    weight_override: float | None = Field(default=None, gt=0)


# --- Analiz çıktıları ---


class ImportResult(BaseModel):
    created: list[str] = []
    updated: list[str] = []
    skipped_approved: list[str] = []
    dry_run: bool = False


class SourceQuestionOut(BaseModel):
    id: int
    ref: str  # "belge_id:etiket"
    document_id: int
    document_filename: str
    doc_type: DocType
    label: str
    page_no: int
    text: str | None
    points: float | None
    solution: str | None
    difficulty: dict | None
    archetype_keys: list[str]


class ArchetypeOut(BaseModel):
    id: int
    key: str
    skill: str
    angle: Angle
    variation_axes: dict[str, list[str]]
    origin: ArchetypeOrigin
    source_url: str | None
    approved: bool
    source_questions: list[SourceQuestionOut]


class ObjectiveOut(BaseModel):
    id: int
    key: str
    text: str
    bloom_level: BloomLevel
    source_document_id: int | None
    source_pages: list[int]
    weight: float
    weight_override: float | None
    effective_weight: float
    approved: bool
    archetypes: list[ArchetypeOut]


class TopicOut(BaseModel):
    id: int
    key: str
    name: str
    approved: bool
    objectives: list[ObjectiveOut]
    children: list["TopicOut"]


class CoverageOut(BaseModel):
    objective_count: int
    archetype_count: int
    source_question_count: int
    objectives_without_archetypes: list[str]
    objectives_with_few_angles: list[str]  # MIN_ANGLES'tan az farklı açı
    unmapped_questions: list[str]
    questions_without_difficulty: list[str]
    unapproved_count: int
    ok: bool


class ProfileOut(_Out):
    steps: float | None
    input_size: float | None
    concept_count: float | None
    bloom_level: float | None
    est_minutes: float | None
    edge_cases: dict
    sample_size: int
    updated_at: datetime | None = None


class CourseMap(BaseModel):
    course_id: int
    course_name: str
    topics: list[TopicOut]
    unmapped_questions: list[SourceQuestionOut]
    coverage: CoverageOut
    profile: ProfileOut | None


# --- Test üretimi ---


class CheckIn(_In):
    checker: NonEmpty
    input: dict
    expected: dict = {}


class GeneratedQuestionIn(_In):
    slot_id: int
    prompt: str | None = None  # past slotlarında boş bırakılır (kaynak soru aynen kullanılır)
    answer: NonEmpty
    answer_type: AnswerType = AnswerType.open
    choices: list[NonEmpty] | None = None
    explanation: str | None = None
    params: dict[str, str] = {}  # varyasyon ekseni -> seçilen değer
    check: CheckIn | None = None

    @model_validator(mode="after")
    def _choices(self) -> Self:
        if self.answer_type is AnswerType.choice:
            if not self.choices or len(self.choices) < 2:
                raise ValueError("answer_type=choice için en az 2 seçenek gerekli")
            if self.answer not in self.choices:
                raise ValueError("Cevap seçeneklerden biri olmalı")
        elif self.choices:
            raise ValueError("choices yalnızca answer_type=choice ile kullanılır")
        if self.answer_type is AnswerType.numeric:
            try:
                float(self.answer.replace(",", "."))
            except ValueError:
                if "/" not in self.answer:
                    raise ValueError("answer_type=numeric için cevap sayı (ya da a/b kesri) olmalı") from None
        return self


class JudgeIn(_In):
    question_id: int
    scores: DifficultyIn
    comment: str | None = None


class AnchorOut(BaseModel):
    ref: str
    text: str
    points: float | None
    difficulty: dict | None


class GeneratedQuestionOut(BaseModel):
    id: int
    kind: QuestionKind
    status: QuestionStatus
    reject_reason: str | None
    prompt: str
    answer: str
    answer_type: AnswerType
    choices: list | None
    explanation: str | None
    params: dict
    verification: dict | None
    similarity: dict | None
    judge: dict | None


class SlotOut(BaseModel):
    slot_id: int
    position: int
    slot_type: SlotType
    priority: float
    objective_key: str
    objective_text: str
    bloom_level: BloomLevel
    archetype_key: str
    skill: str
    angle: Angle
    origin: ArchetypeOrigin
    variation_axes: dict[str, list[str]]
    used_params: list[dict]  # bu kalıpla daha önce kullanılan kombinasyonlar (tekrar etme)
    anchors: list[AnchorOut]
    target_difficulty: dict | None
    past_question: AnchorOut | None
    past_solution: str | None
    question: GeneratedQuestionOut | None
    attempts: int  # bu slot için üretilen soru sayısı (reddedilenler dahil)


class TestOut(BaseModel):
    id: int
    course_id: int
    status: TestStatus
    seed: int
    size: int
    created_at: datetime
    finalized_at: datetime | None
    counts: dict[str, int]
    slots: list[SlotOut] = []
