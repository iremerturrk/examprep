"""Kazanım haritası: konu ağacı, kazanımlar, kalıplar ve kaynak sorular; düzenle / sil / onayla."""

from collections.abc import Callable

import streamlit as st
from pydantic import ValidationError
from sqlalchemy.orm import Session

from examprep import analysis
from examprep.analysis import AnalysisError
from examprep.courses import list_courses
from examprep.db import session_scope
from examprep.models import (
    Angle,
    BloomLevel,
    LearningObjective,
    QuestionArchetype,
    SourceQuestion,
    Topic,
)
from examprep.schemas import (
    ArchetypeEdit,
    ArchetypeOut,
    ObjectiveEdit,
    ObjectiveOut,
    SourceQuestionOut,
    TopicOut,
)
from examprep.i18n import label, t
from examprep.ui import AXIS_SEP, axes_to_text, text_to_axes


def run(action: Callable[[Session], object], message: str | None = None) -> None:
    """Değişikliği uygular; başarılıysa sayfayı yeniler, hatayı gösterir."""
    try:
        with session_scope() as s:
            action(s)
    except ValidationError as exc:
        st.error("; ".join(e["msg"] for e in exc.errors()))
        return
    except AnalysisError as exc:
        st.error(str(exc))
        return
    if message:
        st.toast(message)
    st.rerun()


# --- Diyaloglar ---


@st.dialog(t("map.dlg_rename"))
def edit_topic(topic: TopicOut) -> None:
    name = st.text_input(t("map.name"), topic.name)
    if st.button(t("common.save"), type="primary"):
        run(lambda s: analysis.rename_topic(s, topic.id, name), t("map.topic_updated"))


@st.dialog(t("map.dlg_objective"), width="large")
def edit_objective(o: ObjectiveOut) -> None:
    text = st.text_area(t("map.objective"), o.text)
    bloom = st.selectbox(
        t("map.bloom"), list(BloomLevel), index=list(BloomLevel).index(o.bloom_level), format_func=label
    )
    manual = st.checkbox(t("map.manual_weight", w=f"{o.weight:g}"), value=o.weight_override is not None)
    weight = st.number_input(
        t("map.weight_label"), min_value=0.1, value=float(o.effective_weight), step=0.5, disabled=not manual
    )
    if st.button(t("common.save"), type="primary"):
        run(
            lambda s: analysis.update_objective(
                s,
                o.id,
                ObjectiveEdit(text=text, bloom_level=bloom, weight_override=weight if manual else None),
            ),
            t("map.objective_updated"),
        )


@st.dialog(t("map.dlg_archetype"), width="large")
def edit_archetype(a: ArchetypeOut) -> None:
    skill = st.text_area(t("map.skill"), a.skill)
    angle = st.selectbox(t("map.angle"), list(Angle), index=list(Angle).index(a.angle), format_func=label)
    axes = st.text_area(t("map.axes"), axes_to_text(a.variation_axes), height=150,
                        help=t("map.axes_help", sep=AXIS_SEP))
    if st.button(t("common.save"), type="primary"):
        run(
            lambda s: analysis.update_archetype(
                s, a.id, ArchetypeEdit(skill=skill, angle=angle, variation_axes=text_to_axes(axes))
            ),
            t("map.archetype_updated"),
        )


@st.dialog(t("map.dlg_delete"))
def confirm_delete(model, obj_id: int, name: str, note: str = "") -> None:
    st.write(t("map.will_delete", label=name))
    if note:
        st.warning(note)
    if st.button(t("common.delete"), type="primary"):
        run(lambda s: analysis.delete_item(s, model, obj_id), t("map.deleted"))


# --- Görüntüleme ---


def approve_button(model, obj_id: int, approved: bool, key: str) -> None:
    text = t("common.unapprove") if approved else t("common.approve")
    if st.button(text, key=key, type="secondary" if approved else "primary"):
        run(lambda s: analysis.set_approved(s, model, obj_id, not approved))


def render_question(q: SourceQuestionOut, archetype_id: int | None = None) -> None:
    points = " · " + t("map.points", p=f"{q.points:g}") if q.points is not None else ""
    st.markdown(f"**{label(q.doc_type)} · {q.document_filename} · {t('map.question_head', label=q.label)}** "
                f"({t('common.page')} {q.page_no}{points})")
    st.code(q.text or "", language=None, wrap_lines=True)
    if q.difficulty:
        d = q.difficulty
        edges = ", ".join(d.get("edge_cases", [])) or t("common.none")
        st.caption(t("map.difficulty", steps=d["steps"], input=d["input_size"], concepts=d["concept_count"],
                     bloom=label(BloomLevel(d["bloom_level"])), minutes=f"{d['est_minutes']:g}", edges=edges))
    key = f"q{q.id}_a{archetype_id}"
    c1, c2 = st.columns(2)
    with c1:
        show_solution = bool(q.solution) and st.toggle(t("map.show_solution"), key=f"sol_{key}")
    with c2:
        if archetype_id is not None:
            if st.button(t("map.unlink"), key=f"unlink_{key}"):
                run(lambda s: analysis.unlink_question(s, archetype_id, q.id), t("map.unlinked"))
        elif st.button(t("map.delete_question"), key=f"del_{key}"):
            confirm_delete(SourceQuestion, q.id, f"{t('map.question_head', label=q.label)} ({q.document_filename})")
    if show_solution:
        st.code(q.solution, language=None, wrap_lines=True)


def render_archetype(a: ArchetypeOut) -> None:
    with st.container(border=True):
        status = t("map.approved") if a.approved else t("map.unapproved")
        st.markdown(f"**{label(a.angle)}** · {t('map.origin', origin=label(a.origin))} · {status}")
        st.write(a.skill)
        st.markdown("\n".join(f"- *{name}*: {', '.join(values)}" for name, values in a.variation_axes.items()))
        if a.source_url:
            st.caption(t("map.source_url", url=a.source_url))
        c1, c2, c3, _ = st.columns([1, 1, 1, 3])
        with c1:
            approve_button(QuestionArchetype, a.id, a.approved, f"appr_a{a.id}")
        with c2:
            if st.button(t("common.edit"), key=f"edit_a{a.id}"):
                edit_archetype(a)
        with c3:
            if st.button(t("common.delete"), key=f"del_a{a.id}"):
                confirm_delete(QuestionArchetype, a.id, t("map.pattern", skill=a.skill[:60]))
        if a.source_questions and st.toggle(t("map.source_toggle", n=len(a.source_questions)), key=f"srcq_{a.id}"):
            for q in a.source_questions:
                render_question(q, archetype_id=a.id)


def objective_warning(o: ObjectiveOut) -> str:
    if not o.archetypes:
        return " · " + t("map.warn_none")
    if len({a.angle for a in o.archetypes}) < analysis.MIN_ANGLES:
        return " · " + t("map.warn_angle")
    return ""


def render_objective(o: ObjectiveOut) -> None:
    weight = t("map.weight", w=f"{o.effective_weight:g}") + (t("map.manual") if o.weight_override is not None else "")
    icon = "✅" if o.approved else "⬜"
    basis = " · " + t("map.past_basis") if o.basis.value == "past_questions" else ""
    title = f"{icon} {o.text} · {label(o.bloom_level)} · {weight}{basis}{objective_warning(o)}"
    with st.expander(title):
        pages = " · " + t("map.slide_pages", pages=", ".join(map(str, o.source_pages))) if o.source_pages else ""
        st.caption(f"`{o.key}`{pages}")
        c1, c2, c3, _ = st.columns([1, 1, 1, 3])
        with c1:
            approve_button(LearningObjective, o.id, o.approved, f"appr_o{o.id}")
        with c2:
            if st.button(t("common.edit"), key=f"edit_o{o.id}"):
                edit_objective(o)
        with c3:
            if st.button(t("common.delete"), key=f"del_o{o.id}"):
                confirm_delete(LearningObjective, o.id, o.text, t("map.delete_objective_note"))
        if not o.archetypes:
            st.info(t("map.no_archetypes"))
        for a in o.archetypes:
            render_archetype(a)


def is_pending(o: ObjectiveOut) -> bool:
    return not o.approved or any(not a.approved for a in o.archetypes)


def has_visible(topic: TopicOut, pending_only: bool) -> bool:
    if not pending_only:
        return True
    return (
        not topic.approved
        or any(is_pending(o) for o in topic.objectives)
        or any(has_visible(c, pending_only) for c in topic.children)
    )


def render_topic(topic: TopicOut, depth: int, pending_only: bool) -> None:
    if not has_visible(topic, pending_only):
        return
    heading = "#" * min(depth + 3, 6)
    icon = "✅" if topic.approved else "⬜"
    c0, c1, c2, c3 = st.columns([5, 1.4, 1, 1], vertical_alignment="center")
    with c0:
        st.markdown(f"{heading} {icon} {topic.name}")
    with c1:
        if st.button(t("map.approve_all"), key=f"apprall_t{topic.id}", help=t("map.approve_all_help")):
            run(lambda s: analysis.approve_topic_tree(s, topic.id), t("map.topic_approved"))
    with c2:
        if st.button(t("common.edit"), key=f"edit_t{topic.id}"):
            edit_topic(topic)
    with c3:
        if st.button(t("common.delete"), key=f"del_t{topic.id}"):
            confirm_delete(Topic, topic.id, topic.name, t("map.delete_topic_note"))
    for o in topic.objectives:
        if not pending_only or is_pending(o):
            render_objective(o)
    for child in topic.children:
        render_topic(child, depth + 1, pending_only)


def walk_objectives(topics: list[TopicOut]):
    for topic in topics:
        yield from topic.objectives
        yield from walk_objectives(topic.children)


# --- Sayfa ---

st.title(t("map.title"))

with session_scope() as s:
    courses = {c.id: c.name for c in list_courses(s)}
if not courses:
    st.warning(t("common.need_course"))
    st.stop()

course_id = st.selectbox(t("common.course"), options=list(courses), format_func=courses.get)
with session_scope() as s:
    cmap = analysis.get_course_map(s, course_id)

if not cmap.topics:
    st.info(t("map.no_analysis", id=course_id))
    st.stop()

cov = cmap.coverage
m1, m2, m3, m4 = st.columns(4)
m1.metric(t("map.objectives"), cov.objective_count)
m2.metric(t("map.archetypes"), cov.archetype_count)
m3.metric(t("map.source_questions"), cov.source_question_count)
m4.metric(t("map.pending"), cov.unapproved_count)

texts = {o.key: o.text for o in walk_objectives(cmap.topics)}
if cov.objectives_without_archetypes:
    st.warning(t("map.no_archetype_list", items="; ".join(texts[k] for k in cov.objectives_without_archetypes)))
if cov.objectives_with_few_angles:
    st.warning(t("map.few_angles_list", n=analysis.MIN_ANGLES,
                 items="; ".join(texts[k] for k in cov.objectives_with_few_angles)))

if cmap.profile:
    p = cmap.profile
    with st.expander(t("map.profile", n=p.sample_size)):
        c = st.columns(5)
        c[0].metric(t("map.steps"), f"{p.steps:g}")
        c[1].metric(t("map.input_size"), f"{p.input_size:g}")
        c[2].metric(t("map.concepts"), f"{p.concept_count:g}")
        c[3].metric(t("map.bloom_scale"), f"{p.bloom_level:g}")
        c[4].metric(t("map.minutes"), f"{p.est_minutes:g}")
        freq = p.edge_cases.get("frequency", {})
        if freq:
            st.caption(t("map.edge_cases", items=", ".join(f"{k} ({v})" for k, v in freq.items())))

st.caption(t("map.overwrite_note"))
pending_only = st.toggle(t("map.pending_only"))
st.divider()

for topic in cmap.topics:
    render_topic(topic, 0, pending_only)

if cmap.unmapped_questions:
    st.divider()
    st.subheader(t("map.unmapped", n=len(cmap.unmapped_questions)))
    st.caption(t("map.unmapped_note"))
    for q in cmap.unmapped_questions:
        with st.container(border=True):
            render_question(q)
