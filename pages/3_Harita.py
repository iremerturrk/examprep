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
from examprep.ui import (
    ANGLE_TR,
    AXIS_SEP,
    BLOOM_TR,
    DOC_TR,
    ORIGIN_TR,
    axes_to_text,
    text_to_axes,
)


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


@st.dialog("Konuyu yeniden adlandır")
def edit_topic(t: TopicOut) -> None:
    name = st.text_input("Ad", t.name)
    if st.button("Kaydet", type="primary"):
        run(lambda s: analysis.rename_topic(s, t.id, name), "Konu güncellendi")


@st.dialog("Kazanımı düzenle", width="large")
def edit_objective(o: ObjectiveOut) -> None:
    text = st.text_area("Kazanım", o.text)
    bloom = st.selectbox(
        "Bloom seviyesi", list(BloomLevel), index=list(BloomLevel).index(o.bloom_level), format_func=BLOOM_TR.get
    )
    manual = st.checkbox(
        f"Ağırlığı elle ayarla (hesaplanan: {o.weight:g})", value=o.weight_override is not None
    )
    weight = st.number_input(
        "Ağırlık", min_value=0.1, value=float(o.effective_weight), step=0.5, disabled=not manual
    )
    if st.button("Kaydet", type="primary"):
        run(
            lambda s: analysis.update_objective(
                s,
                o.id,
                ObjectiveEdit(text=text, bloom_level=bloom, weight_override=weight if manual else None),
            ),
            "Kazanım güncellendi",
        )


@st.dialog("Kalıbı düzenle", width="large")
def edit_archetype(a: ArchetypeOut) -> None:
    skill = st.text_area("Beceri", a.skill)
    angle = st.selectbox("Açı", list(Angle), index=list(Angle).index(a.angle), format_func=ANGLE_TR.get)
    axes = st.text_area(
        "Varyasyon eksenleri",
        axes_to_text(a.variation_axes),
        height=150,
        help=f"Her satır bir eksen: `eksen: değer1 {AXIS_SEP} değer2 {AXIS_SEP} ...` (en az 2 değer)",
    )
    if st.button("Kaydet", type="primary"):
        run(
            lambda s: analysis.update_archetype(
                s, a.id, ArchetypeEdit(skill=skill, angle=angle, variation_axes=text_to_axes(axes))
            ),
            "Kalıp güncellendi",
        )


@st.dialog("Silinsin mi?")
def confirm_delete(model, obj_id: int, label: str, note: str = "") -> None:
    st.write(f"**{label}** silinecek.")
    if note:
        st.warning(note)
    if st.button("Sil", type="primary"):
        run(lambda s: analysis.delete_item(s, model, obj_id), "Silindi")


# --- Görüntüleme ---


def approve_button(model, obj_id: int, approved: bool, key: str) -> None:
    label = "Onayı kaldır" if approved else "Onayla"
    if st.button(label, key=key, type="secondary" if approved else "primary"):
        run(lambda s: analysis.set_approved(s, model, obj_id, not approved))


def render_question(q: SourceQuestionOut, archetype_id: int | None = None) -> None:
    points = f" · {q.points:g} puan" if q.points is not None else ""
    st.markdown(f"**{DOC_TR[q.doc_type]} · {q.document_filename} · Soru {q.label}** (s. {q.page_no}{points})")
    st.code(q.text or "", language=None, wrap_lines=True)
    if q.difficulty:
        d = q.difficulty
        edges = ", ".join(d.get("edge_cases", [])) or "yok"
        st.caption(
            f"Adım {d['steps']} · girdi {d['input_size']} · kavram {d['concept_count']} · "
            f"{BLOOM_TR[BloomLevel(d['bloom_level'])]} · ~{d['est_minutes']:g} dk · kenar durum: {edges}"
        )
    key = f"q{q.id}_a{archetype_id}"
    c1, c2 = st.columns(2)
    with c1:
        show_solution = bool(q.solution) and st.toggle("Çözümü göster", key=f"sol_{key}")
    with c2:
        if archetype_id is not None:
            if st.button("Bu kalıptan ayır", key=f"unlink_{key}"):
                run(lambda s: analysis.unlink_question(s, archetype_id, q.id), "Soru kalıptan ayrıldı")
        elif st.button("Soruyu sil", key=f"del_{key}"):
            confirm_delete(SourceQuestion, q.id, f"Soru {q.label} ({q.document_filename})")
    if show_solution:
        st.code(q.solution, language=None, wrap_lines=True)


def render_archetype(a: ArchetypeOut) -> None:
    with st.container(border=True):
        status = "✅ onaylı" if a.approved else "⬜ onay bekliyor"
        st.markdown(f"**{ANGLE_TR[a.angle]}** · kaynak: {ORIGIN_TR[a.origin]} · {status}")
        st.write(a.skill)
        st.markdown("\n".join(f"- *{name}*: {', '.join(values)}" for name, values in a.variation_axes.items()))
        if a.source_url:
            st.caption(f"Kaynak: {a.source_url}")
        c1, c2, c3, _ = st.columns([1, 1, 1, 3])
        with c1:
            approve_button(QuestionArchetype, a.id, a.approved, f"appr_a{a.id}")
        with c2:
            if st.button("Düzenle", key=f"edit_a{a.id}"):
                edit_archetype(a)
        with c3:
            if st.button("Sil", key=f"del_a{a.id}"):
                confirm_delete(QuestionArchetype, a.id, f"Kalıp: {a.skill[:60]}")
        if a.source_questions and st.toggle(
            f"Kaynak sorular ({len(a.source_questions)})", key=f"srcq_{a.id}"
        ):
            for q in a.source_questions:
                render_question(q, archetype_id=a.id)


def objective_warning(o: ObjectiveOut) -> str:
    if not o.archetypes:
        return " · ⚠️ kalıp yok"
    if len({a.angle for a in o.archetypes}) < analysis.MIN_ANGLES:
        return " · ⚠️ tek açı"
    return ""


def render_objective(o: ObjectiveOut) -> None:
    weight = f"ağırlık {o.effective_weight:g}" + (" (elle)" if o.weight_override is not None else "")
    icon = "✅" if o.approved else "⬜"
    label = f"{icon} {o.text} · {BLOOM_TR[o.bloom_level]} · {weight}{objective_warning(o)}"
    with st.expander(label):
        pages = f" · slayt sayfaları: {', '.join(map(str, o.source_pages))}" if o.source_pages else ""
        st.caption(f"`{o.key}`{pages}")
        c1, c2, c3, _ = st.columns([1, 1, 1, 3])
        with c1:
            approve_button(LearningObjective, o.id, o.approved, f"appr_o{o.id}")
        with c2:
            if st.button("Düzenle", key=f"edit_o{o.id}"):
                edit_objective(o)
        with c3:
            if st.button("Sil", key=f"del_o{o.id}"):
                confirm_delete(
                    LearningObjective, o.id, o.text,
                    "Kazanımın kalıpları da silinir; kaynak sorular kalır ve eşlenmemiş olur.",
                )
        if not o.archetypes:
            st.info("Bu kazanımın kalıbı yok. `/ders-analiz` tekrar çalıştırılınca model kalıpları eklenir.")
        for a in o.archetypes:
            render_archetype(a)


def is_pending(o: ObjectiveOut) -> bool:
    return not o.approved or any(not a.approved for a in o.archetypes)


def has_visible(t: TopicOut, pending_only: bool) -> bool:
    if not pending_only:
        return True
    return (
        not t.approved
        or any(is_pending(o) for o in t.objectives)
        or any(has_visible(c, pending_only) for c in t.children)
    )


def render_topic(t: TopicOut, depth: int, pending_only: bool) -> None:
    if not has_visible(t, pending_only):
        return
    heading = "#" * min(depth + 3, 6)
    icon = "✅" if t.approved else "⬜"
    c0, c1, c2, c3 = st.columns([5, 1.4, 1, 1], vertical_alignment="center")
    with c0:
        st.markdown(f"{heading} {icon} {t.name}")
    with c1:
        if st.button("Tümünü onayla", key=f"apprall_t{t.id}", help="Konu, alt konular, kazanımlar ve kalıplar"):
            run(lambda s: analysis.approve_topic_tree(s, t.id), "Konu onaylandı")
    with c2:
        if st.button("Düzenle", key=f"edit_t{t.id}"):
            edit_topic(t)
    with c3:
        if st.button("Sil", key=f"del_t{t.id}"):
            confirm_delete(Topic, t.id, t.name, "Alt konular, kazanımlar ve kalıplar da silinir.")
    for o in t.objectives:
        if not pending_only or is_pending(o):
            render_objective(o)
    for child in t.children:
        render_topic(child, depth + 1, pending_only)


def walk_objectives(topics: list[TopicOut]):
    for t in topics:
        yield from t.objectives
        yield from walk_objectives(t.children)


# --- Sayfa ---

st.title("Kazanım Haritası")

with session_scope() as s:
    courses = {c.id: c.name for c in list_courses(s)}
if not courses:
    st.warning("Önce 'Dersler' sayfasından bir ders oluşturun.")
    st.stop()

course_id = st.selectbox("Ders", options=list(courses), format_func=courses.get)
with session_scope() as s:
    cmap = analysis.get_course_map(s, course_id)

if not cmap.topics:
    st.info(f"Bu ders için henüz analiz yok. Claude Code'da `/ders-analiz {course_id}` çalıştırın.")
    st.stop()

cov = cmap.coverage
m1, m2, m3, m4 = st.columns(4)
m1.metric("Kazanım", cov.objective_count)
m2.metric("Kalıp", cov.archetype_count)
m3.metric("Kaynak soru", cov.source_question_count)
m4.metric("Onay bekleyen", cov.unapproved_count)

texts = {o.key: o.text for o in walk_objectives(cmap.topics)}
if cov.objectives_without_archetypes:
    st.warning(
        "Kalıbı olmayan kazanımlar: " + "; ".join(texts[k] for k in cov.objectives_without_archetypes)
    )
if cov.objectives_with_few_angles:
    st.warning(
        f"{analysis.MIN_ANGLES}'den az açıyla kapsanan kazanımlar: "
        + "; ".join(texts[k] for k in cov.objectives_with_few_angles)
    )

if cmap.profile:
    p = cmap.profile
    with st.expander(f"Zorluk profili ({p.sample_size} sınav sorusundan)"):
        c = st.columns(5)
        c[0].metric("Adım", f"{p.steps:g}")
        c[1].metric("Girdi boyutu", f"{p.input_size:g}")
        c[2].metric("Kavram", f"{p.concept_count:g}")
        c[3].metric("Bloom (1-6)", f"{p.bloom_level:g}")
        c[4].metric("Süre (dk)", f"{p.est_minutes:g}")
        freq = p.edge_cases.get("frequency", {})
        if freq:
            st.caption("Kenar durumlar: " + ", ".join(f"{k} ({v})" for k, v in freq.items()))

st.caption(
    "Düzenlediğin bir kaydı onaylamazsan, /ders-analiz tekrar çalıştığında üzerine yazılabilir. "
    "Onaylı kayıtlar korunur."
)
pending_only = st.toggle("Yalnızca onay bekleyenleri göster")
st.divider()

for topic in cmap.topics:
    render_topic(topic, 0, pending_only)

if cmap.unmapped_questions:
    st.divider()
    st.subheader(f"Eşlenmemiş kaynak sorular ({len(cmap.unmapped_questions)})")
    st.caption("Slayt kazanımlarına bağlanamayan sorular (kapsam dışı). Testlerde kullanılmazlar.")
    for q in cmap.unmapped_questions:
        with st.container(border=True):
            render_question(q)
