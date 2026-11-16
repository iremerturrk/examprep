"""Veri modeli.

Course > Topic > LearningObjective > QuestionArchetype > GeneratedQuestion > Attempt
Ayrıca: SourceDocument (+ DocumentPage, SourceQuestion), DifficultyProfile (ders başına),
WeeklyPlan (sınav tarihine göre haftalara dağıtılmış kazanımlar).
"""

import enum
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class DocType(str, enum.Enum):
    slides = "slides"
    homework = "homework"
    exam = "exam"


class DocStatus(str, enum.Enum):
    processed = "processed"
    needs_ocr = "needs_ocr"
    failed = "failed"


class ArchetypeOrigin(str, enum.Enum):
    exam = "exam"
    homework = "homework"
    web = "web"
    model = "model"


class BloomLevel(str, enum.Enum):
    remember = "remember"
    understand = "understand"
    apply = "apply"
    analyze = "analyze"
    evaluate = "evaluate"
    create = "create"

    @property
    def rank(self) -> int:
        return list(BloomLevel).index(self) + 1


class Angle(str, enum.Enum):
    """Bir kalıbın kazanımı hangi açıdan test ettiği."""

    compute = "compute"  # hesaplama
    trace = "trace"  # izleme
    compare = "compare"  # karşılaştırma
    find_error = "find_error"  # hata bulma
    edge_case = "edge_case"  # kenar durum
    explain = "explain"  # açıklama
    design = "design"  # tasarım


class PerceivedDifficulty(str, enum.Enum):
    easy = "easy"
    exam_like = "exam_like"
    hard = "hard"


weekly_plan_objective = Table(
    "weekly_plan_objective",
    Base.metadata,
    Column("weekly_plan_id", ForeignKey("weekly_plan.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "learning_objective_id",
        ForeignKey("learning_objective.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


archetype_source_question = Table(
    "archetype_source_question",
    Base.metadata,
    Column("archetype_id", ForeignKey("question_archetype.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "source_question_id",
        ForeignKey("source_question.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Course(Base):
    __tablename__ = "course"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    code: Mapped[str | None] = mapped_column(String(50))
    exam_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    documents: Mapped[list["SourceDocument"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", passive_deletes=True
    )
    topics: Mapped[list["Topic"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", passive_deletes=True
    )
    difficulty_profile: Mapped["DifficultyProfile | None"] = relationship(
        back_populates="course", cascade="all, delete-orphan", passive_deletes=True
    )
    weekly_plans: Mapped[list["WeeklyPlan"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="WeeklyPlan.week_no",
    )


class SourceDocument(Base):
    __tablename__ = "source_document"
    __table_args__ = (UniqueConstraint("course_id", "sha256", name="uq_document_course_sha"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(500))
    doc_type: Mapped[DocType] = mapped_column(Enum(DocType))
    sha256: Mapped[str] = mapped_column(String(64))
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[DocStatus] = mapped_column(Enum(DocStatus), default=DocStatus.processed)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    course: Mapped[Course] = relationship(back_populates="documents")
    pages: Mapped[list["DocumentPage"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentPage.page_no",
    )
    questions: Mapped[list["SourceQuestion"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )


class DocumentPage(Base):
    __tablename__ = "document_page"
    __table_args__ = (UniqueConstraint("document_id", "page_no", name="uq_page_document_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("source_document.id", ondelete="CASCADE"), index=True
    )
    page_no: Mapped[int] = mapped_column(Integer)  # 1'den başlar
    text: Mapped[str] = mapped_column(Text, default="")
    image_path: Mapped[str] = mapped_column(String(500))  # DATA_DIR'e göreli
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    is_scanned: Mapped[bool] = mapped_column(Boolean, default=False)

    document: Mapped[SourceDocument] = relationship(back_populates="pages")


class SourceQuestion(Base):
    """Çıkmış sınav ya da ödevden alınan soru (metni olduğu gibi saklanır)."""

    __tablename__ = "source_question"
    __table_args__ = (UniqueConstraint("document_id", "label", name="uq_question_document_label"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("source_document.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(50))  # belgedeki numarası: "3", "2b"
    page_no: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    points: Mapped[float | None] = mapped_column(Float)
    solution: Mapped[str | None] = mapped_column(Text)
    # steps, input_size, concept_count, bloom_level, est_minutes, edge_cases
    difficulty: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    document: Mapped[SourceDocument] = relationship(back_populates="questions")
    archetypes: Mapped[list["QuestionArchetype"]] = relationship(
        secondary=archetype_source_question, back_populates="source_questions"
    )


class Topic(Base):
    __tablename__ = "topic"
    __table_args__ = (UniqueConstraint("course_id", "key", name="uq_topic_course_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("topic.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(300))
    order: Mapped[int] = mapped_column(Integer, default=0)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)

    course: Mapped[Course] = relationship(back_populates="topics")
    parent: Mapped["Topic | None"] = relationship(back_populates="children", remote_side=[id])
    children: Mapped[list["Topic"]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Topic.order",
    )
    objectives: Mapped[list["LearningObjective"]] = relationship(
        back_populates="topic",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="LearningObjective.order",
    )


class LearningObjective(Base):
    __tablename__ = "learning_objective"
    __table_args__ = (UniqueConstraint("course_id", "key", name="uq_objective_course_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # course_id konudan türetilir; ders içinde tekil anahtar için tutulur.
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topic.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    bloom_level: Mapped[BloomLevel] = mapped_column(Enum(BloomLevel))
    order: Mapped[int] = mapped_column(Integer, default=0)
    source_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("source_document.id", ondelete="SET NULL")
    )
    source_pages: Mapped[list[int]] = mapped_column(JSON, default=list)
    weight: Mapped[float] = mapped_column(Float, default=1.0)  # kaynak sorulardan hesaplanır
    weight_override: Mapped[float | None] = mapped_column(Float)  # kullanıcı değeri
    approved: Mapped[bool] = mapped_column(Boolean, default=False)

    topic: Mapped[Topic] = relationship(back_populates="objectives")
    archetypes: Mapped[list["QuestionArchetype"]] = relationship(
        back_populates="objective",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="QuestionArchetype.id",
    )

    @property
    def effective_weight(self) -> float:
        return self.weight_override if self.weight_override is not None else self.weight


class QuestionArchetype(Base):
    __tablename__ = "question_archetype"
    __table_args__ = (UniqueConstraint("course_id", "key", name="uq_archetype_course_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id", ondelete="CASCADE"), index=True)
    learning_objective_id: Mapped[int] = mapped_column(
        ForeignKey("learning_objective.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(200))
    skill: Mapped[str] = mapped_column(Text)
    angle: Mapped[Angle] = mapped_column(Enum(Angle))
    variation_axes: Mapped[dict] = mapped_column(JSON, default=dict)
    origin: Mapped[ArchetypeOrigin] = mapped_column(Enum(ArchetypeOrigin))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    approved: Mapped[bool] = mapped_column(Boolean, default=False)

    objective: Mapped[LearningObjective] = relationship(back_populates="archetypes")
    source_questions: Mapped[list[SourceQuestion]] = relationship(
        secondary=archetype_source_question,
        back_populates="archetypes",
        order_by="SourceQuestion.id",
    )
    questions: Mapped[list["GeneratedQuestion"]] = relationship(
        back_populates="archetype", cascade="all, delete-orphan", passive_deletes=True
    )


class GeneratedQuestion(Base):
    __tablename__ = "generated_question"

    id: Mapped[int] = mapped_column(primary_key=True)
    archetype_id: Mapped[int] = mapped_column(
        ForeignKey("question_archetype.id", ondelete="CASCADE"), index=True
    )
    prompt: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    difficulty_scores: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    archetype: Mapped[QuestionArchetype] = relationship(back_populates="questions")
    attempts: Mapped[list["Attempt"]] = relationship(
        back_populates="question", cascade="all, delete-orphan", passive_deletes=True
    )


class Attempt(Base):
    __tablename__ = "attempt"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("generated_question.id", ondelete="CASCADE"), index=True
    )
    answered_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    correct: Mapped[bool] = mapped_column(Boolean)
    perceived_difficulty: Mapped[PerceivedDifficulty | None] = mapped_column(
        Enum(PerceivedDifficulty)
    )
    time_spent_s: Mapped[int | None] = mapped_column(Integer)

    question: Mapped[GeneratedQuestion] = relationship(back_populates="attempts")


class DifficultyProfile(Base):
    __tablename__ = "difficulty_profile"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("course.id", ondelete="CASCADE"), unique=True
    )
    steps: Mapped[float | None] = mapped_column(Float)
    input_size: Mapped[float | None] = mapped_column(Float)
    concept_count: Mapped[float | None] = mapped_column(Float)
    bloom_level: Mapped[float | None] = mapped_column(Float)
    est_minutes: Mapped[float | None] = mapped_column(Float)
    edge_cases: Mapped[dict] = mapped_column(JSON, default=dict)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)  # kaç sınav sorusundan
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    course: Mapped[Course] = relationship(back_populates="difficulty_profile")


class WeeklyPlan(Base):
    """Bir haftada çalışılacak kazanımlar. Haftalık test bu kayda göre üretilir."""

    __tablename__ = "weekly_plan"
    __table_args__ = (UniqueConstraint("course_id", "week_no", name="uq_plan_course_week"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id", ondelete="CASCADE"), index=True)
    week_no: Mapped[int] = mapped_column(Integer)  # 1'den başlar
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)

    course: Mapped[Course] = relationship(back_populates="weekly_plans")
    objectives: Mapped[list[LearningObjective]] = relationship(secondary=weekly_plan_objective)
