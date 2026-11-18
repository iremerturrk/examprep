"""ExamPrep Streamlit giriş noktası: `streamlit run app.py`"""

import streamlit as st

from examprep.db import init_db
from examprep.i18n import language_selector, t

st.set_page_config(page_title="ExamPrep", page_icon="📚", layout="wide")


@st.cache_resource
def _init() -> bool:
    init_db()
    return True


_init()
language_selector()

nav = st.navigation(
    [
        st.Page("pages/1_Dersler.py", title=t("nav.courses"), icon="🎓", default=True),
        st.Page("pages/2_Yukle.py", title=t("nav.upload"), icon="📄"),
        st.Page("pages/3_Harita.py", title=t("nav.map"), icon="🗺️"),
        st.Page("pages/4_Testler.py", title=t("nav.tests"), icon="📝"),
    ]
)
nav.run()
