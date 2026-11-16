"""Üretilmiş testler: liste ve önizleme (soru, cevap, doğrulama / benzerlik / hakem rozetleri)."""

import streamlit as st

from examprep import testgen
from examprep.analysis import AnalysisError
from examprep.courses import list_courses
from examprep.db import session_scope
from examprep.models import SlotType, TestStatus
from examprep.schemas import SlotOut
from examprep.ui import ANGLE_TR

SLOT_TR = {SlotType.new: "🆕 Yeni konu", SlotType.review: "🔁 Tekrar", SlotType.past: "📜 Çıkmış soru"}
STATUS_TR = {TestStatus.draft: "Taslak", TestStatus.ready: "Hazır"}
VERIFY_TR = {"passed": "✅ Kodla doğrulandı", "unverified": "⚪ Kavramsal (yalnız hakem)",
             "undetermined": "⚪ Doğrulayıcı karar veremedi", "failed": "❌ Doğrulama başarısız",
             "error": "❌ Doğrulayıcı hatası"}

st.title("Testler")

with session_scope() as s:
    courses = {c.id: c.name for c in list_courses(s)}
if not courses:
    st.warning("Önce 'Dersler' sayfasından bir ders oluşturun.")
    st.stop()
course_id = st.selectbox("Ders", options=list(courses), format_func=courses.get)
st.caption(f"Yeni test için Claude Code'da `/hafta-testi {course_id}` çalıştırın "
           f"(soru sayısı da verilebilir: `/hafta-testi {course_id} 15`).")

with session_scope() as s:
    tests = testgen.list_tests(s, course_id)
if not tests:
    st.info("Bu ders için henüz test yok.")
    st.stop()


def label(t) -> str:
    when = (t.finalized_at or t.created_at).strftime("%d.%m.%Y %H:%M")
    n = sum(t.counts.get(k, 0) for k in ("new", "review", "past"))
    return f"Test {t.id} · {STATUS_TR[t.status]} · {when} UTC · {n} soru"


test_id = st.selectbox("Test", options=[t.id for t in reversed(tests)],
                       format_func=lambda i: label(next(t for t in tests if t.id == i)))
with session_scope() as s:
    test = testgen.test_out(s, test_id)

c = test.counts
m = st.columns(4)
m[0].metric("Yeni konu", c.get("new", 0))
m[1].metric("Tekrar", c.get("review", 0))
m[2].metric("Çıkmış soru", c.get("past", 0))
m[3].metric("Kabul edilen", c.get("q_accepted", 0))

if test.status is TestStatus.draft:
    st.warning("Bu test henüz tamamlanmadı. Eksik ya da reddedilmiş slotlar /hafta-testi tarafından doldurulur.")
    if st.button("Taslağı sil", type="secondary"):
        try:
            with session_scope() as s:
                testgen.discard_test(s, test_id)
            st.rerun()
        except AnalysisError as exc:
            st.error(str(exc))

show_answers = st.toggle("Cevapları göster", value=False)
st.divider()


def render_slot(slot: SlotOut) -> None:
    q = slot.question
    header = f"**{slot.position}.** {SLOT_TR[slot.slot_type]} · {slot.objective_text}"
    st.markdown(header)
    st.caption(f"Kalıp: {slot.skill} · açı: {ANGLE_TR[slot.angle]}"
               + (f" · kaynak: {slot.past_question.ref}" if slot.past_question else ""))
    if q is None:
        st.info(f"Henüz kabul edilmiş soru yok ({slot.attempts} deneme).")
        return
    st.markdown(q.prompt)
    if q.choices:
        st.markdown("\n".join(f"- {c}" for c in q.choices))
    badges = []
    if q.verification:
        badges.append(VERIFY_TR.get(q.verification["status"], q.verification["status"]))
    if q.similarity and q.similarity.get("score") is not None:
        badges.append(f"benzerlik {q.similarity['score']:.2f} ({q.similarity.get('ref')})")
    if q.judge:
        badges.append(f"hakem: {q.judge.get('verdict')}")
    if q.status.value != "accepted":
        badges.append(f"durum: {q.status.value}")
    st.caption(" · ".join(badges))
    if show_answers:
        with st.container(border=True):
            st.markdown(f"**Cevap:** {q.answer}")
            if q.explanation:
                st.markdown(q.explanation)


for slot in test.slots:
    with st.container(border=True):
        render_slot(slot)
