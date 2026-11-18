"""Testler: kartlarla tekrar → şıklı test → gönder → sonuç ve eksik kazanımlar."""

import time

import streamlit as st

from examprep import cards, config, submissions, testgen
from examprep.analysis import AnalysisError
from examprep.courses import list_courses
from examprep.db import session_scope
from examprep.i18n import label, t
from examprep.models import PerceivedDifficulty, TestFormat, TestStatus, Tier
from examprep.schemas import AnswerIn, SubmissionIn, TestOut

LETTERS = "ABCD"

st.markdown("""
<style>
.block-container {max-width: 880px; padding-top: 2rem;}
[data-testid="stVerticalBlockBorderWrapper"] p {font-size: 1.04rem; line-height: 1.6;}
div[role="radiogroup"] label p {font-size: 1.0rem;}
div[role="radiogroup"] {gap: 0.35rem;}
.qnum {font-weight: 700; color: #6e7781; margin-right: .35rem;}
</style>
""", unsafe_allow_html=True)

st.title(t("tests.title"))

with session_scope() as s:
    courses = {c.id: c.name for c in list_courses(s)}
if not courses:
    st.warning(t("common.need_course"))
    st.stop()
course_id = st.selectbox(t("common.course"), options=list(courses), format_func=courses.get)

with session_scope() as s:
    tests = [t for t in testgen.list_tests(s, course_id) if t.status is TestStatus.ready]
if not tests:
    st.info(t("tests.none", id=course_id))
    st.stop()


def test_label(test: TestOut) -> str:
    when = (test.finalized_at or test.created_at).strftime("%d.%m.%Y")
    kind = t("tests.kind_kazanim") if test.format is TestFormat.kazanim else t("tests.kind_open")
    return f"Test {test.id} · {kind} · {t('tests.n_questions', n=test.size)} · {when}"


test_id = st.selectbox("Test", [t.id for t in reversed(tests)],
                       format_func=lambda i: test_label(next(x for x in tests if x.id == i)))
st.caption(t("tests.new_hint", id=course_id))
with session_scope() as s:
    test = testgen.test_out(s, test_id)


# --- Eski format (açık uçlu) testler: salt okunur ---

if test.format is TestFormat.open:
    show = st.toggle(t("tests.show_answers"))
    for slot in test.slots:
        q = slot.question
        with st.container(border=True):
            st.markdown(f"<span class='qnum'>{slot.position}.</span>", unsafe_allow_html=True)
            st.markdown(q.prompt)
            if show:
                st.markdown(f"**{t('tests.answer')}:** {q.answer}")
                if q.explanation:
                    st.markdown(q.explanation)
    st.stop()


tab_cards, tab_test, tab_result = st.tabs([t("tests.tab_cards"), t("tests.tab_test"), t("tests.tab_result")])

# --- 1. Kartlar ---

with tab_cards:
    with session_scope() as s:
        deck = cards.cards_for_test(s, test_id)
    n_obj = len({c.objective_key for c in deck})
    st.markdown(t("tests.cards_intro", o=n_obj, c=len(deck)))
    if not deck:
        st.info(t("tests.no_cards"))
    else:
        c1, c2 = st.columns([2, 1])
        mode = c1.segmented_control(t("tests.view"), ["single", "list"], default="single", key=f"mode_{test_id}",
                                    format_func=lambda m: t(f"tests.view_{m}"))
        try:
            with session_scope() as s:
                path = cards.export_apkg(s, test_id, config.DATA_DIR / "exports" / f"test_{test_id}.apkg")["path"]
            with open(path, "rb") as fh:
                c2.download_button(t("tests.anki"), fh.read(), file_name=f"test_{test_id}.apkg",
                                   mime="application/octet-stream", width="stretch")
        except AnalysisError as exc:
            c2.caption(str(exc))

        if mode == "list":
            for c in deck:
                with st.expander(c.front):
                    st.markdown(c.back)
                    st.caption(f"{label(c.kind)} · {c.objective_text}")
        else:
            idx_key, flip_key = f"card_idx_{test_id}", f"card_flip_{test_id}"
            idx = st.session_state.get(idx_key, 0) % len(deck)
            card = deck[idx]
            st.progress((idx + 1) / len(deck), text=t("tests.card_progress", i=idx + 1, n=len(deck)))
            with st.container(border=True):
                st.caption(label(card.kind))
                st.markdown(f"#### {card.front}")
                if st.session_state.get(flip_key):
                    st.divider()
                    st.markdown(card.back)
                    st.caption(card.objective_text)
            b1, b2, b3 = st.columns(3)
            if not st.session_state.get(flip_key):
                if b2.button(t("tests.flip"), type="primary", width="stretch"):
                    st.session_state[flip_key] = True
                    st.rerun()
            else:
                def answer(known: bool) -> None:
                    with session_scope() as s2:
                        cards.record_review(s2, card.id, known)
                    st.session_state[idx_key] = idx + 1
                    st.session_state[flip_key] = False

                b1.button(t("tests.again"), on_click=answer, args=(False,), width="stretch")
                b3.button(t("tests.known"), on_click=answer, args=(True,), type="primary", width="stretch")


# --- 2. Test ---

with tab_test:
    start_key, sub_key = f"start_{test_id}", f"submission_{test_id}"
    st.session_state.setdefault(start_key, time.time())
    if st.session_state.get(sub_key):
        with session_scope() as s:
            done = submissions.submission_out(s, st.session_state[sub_key])
        st.success(t("tests.submitted", s=done.score, n=done.total))
        if st.button(t("tests.retake")):
            for k in [k for k in st.session_state if k.startswith(f"ans_{test_id}_")]:
                del st.session_state[k]
            st.session_state[start_key] = time.time()
            del st.session_state[sub_key]
            st.rerun()
    else:
        with st.form(f"test_form_{test_id}", border=False):
            current = None
            for slot in test.slots:
                if slot.tier != current:
                    current = slot.tier
                    st.subheader(label(current))
                    st.caption(t(f"tiernote.{current.value}"))
                q = slot.question
                with st.container(border=True):
                    st.markdown(f"<span class='qnum'>{slot.position}.</span>", unsafe_allow_html=True)
                    st.markdown(q.prompt)
                    st.radio(t("tests.question_n", n=slot.position), options=list(range(len(q.choices))), index=None,
                             format_func=lambda i, ch=q.choices: f"**{LETTERS[i]})**  {ch[i]}",
                             key=f"ans_{test_id}_{slot.slot_id}", label_visibility="collapsed")
            submitted = st.form_submit_button(t("tests.submit"), type="primary", width="stretch")
        if submitted:
            answers = []
            for slot in test.slots:
                i = st.session_state.get(f"ans_{test_id}_{slot.slot_id}")
                answers.append(AnswerIn(slot_id=slot.slot_id, selected=None if i is None else slot.question.choices[i]))
            blank = sum(a.selected is None for a in answers)
            with session_scope() as s:
                out = submissions.submit(s, SubmissionIn(test_id=test_id, answers=answers,
                                                         duration_s=int(time.time() - st.session_state[start_key])))
            st.session_state[sub_key] = out.id
            if blank:
                st.toast(t("tests.blank", n=blank))
            st.rerun()


# --- 3. Sonuç ---

with tab_result:
    with session_scope() as s:
        subs = submissions.list_submissions(s, test_id)
    if not subs:
        st.info(t("tests.no_result"))
        st.stop()
    sub_id = st.selectbox(t("tests.submission"), [x.id for x in reversed(subs)], format_func=lambda i: next(
        f"{x.submitted_at.strftime('%d.%m.%Y %H:%M')} UTC · {x.score}/{x.total}" for x in subs if x.id == i))
    with session_scope() as s:
        res = submissions.submission_out(s, sub_id)

    cols = st.columns(4)
    cols[0].metric(t("tests.total"), f"{res.score}/{res.total}", f"%{round(100 * res.score / res.total)}", delta_color="off")
    for col, tier in zip(cols[1:], Tier):
        sc = res.section_scores.get(tier.value)
        if sc:
            col.metric(t(f"tiershort.{tier.value}"), f"{sc['correct']}/{sc['total']}")
    if res.duration_s:
        st.caption(t("tests.duration", m=res.duration_s // 60, s=res.duration_s % 60))

    if res.weak_objectives:
        st.subheader(t("tests.weak"))
        with session_scope() as s:
            deck: dict = {}
            for c in cards.cards_for_test(s, test_id):
                deck.setdefault(c.objective_key, []).append(c)
        for w in res.weak_objectives:
            with st.expander(t("tests.weak_item", text=w["text"], w=w["wrong"], n=w["total"])):
                for c in deck.get(w["key"], []):
                    st.markdown(f"**{c.front}**")
                    st.markdown(c.back)
                if not deck.get(w["key"]):
                    st.caption(t("tests.no_card_obj"))
    else:
        st.success(t("tests.all_correct"))

    st.subheader(t("tests.questions"))
    only_wrong = st.toggle(t("tests.only_wrong"), value=bool(res.weak_objectives))
    for r in res.results:
        if only_wrong and r.correct:
            continue
        with st.container(border=True):
            mark = "✅" if r.correct else (t("tests.blank_mark") if r.selected is None else "❌")
            st.markdown(f"<span class='qnum'>{r.position}.</span> {mark}", unsafe_allow_html=True)
            st.markdown(r.prompt)
            lines = []
            for i, ch in enumerate(r.choices or []):
                tag = " ✅" if ch == r.answer else (f" ❌ *({t('tests.your_answer')})*" if ch == r.selected else "")
                lines.append(f"- **{LETTERS[i]})** {ch}{tag}")
            st.markdown("\n".join(lines))
            if r.explanation:
                with st.expander(t("tests.explanation")):
                    st.markdown(r.explanation)
                    st.caption(t("tests.objective", text=r.objective_text))

            def mark_perceived(attempt_id=r.attempt_id, key=f"perc_{r.attempt_id}"):
                value = st.session_state.get(key)
                with session_scope() as s2:
                    submissions.set_perceived(s2, attempt_id, PerceivedDifficulty(value) if value else None)

            st.segmented_control(t("tests.difficulty"), [p.value for p in PerceivedDifficulty],
                                 format_func=lambda v: label(v, "perceived"), default=r.perceived_difficulty,
                                 key=f"perc_{r.attempt_id}", on_change=mark_perceived, label_visibility="collapsed")
