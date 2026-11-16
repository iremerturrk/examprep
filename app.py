"""ExamPrep Streamlit giriş noktası: `streamlit run app.py`"""

import streamlit as st

from examprep.db import init_db

st.set_page_config(page_title="ExamPrep", page_icon="📚", layout="wide")


@st.cache_resource
def _init() -> bool:
    init_db()
    return True


_init()

nav = st.navigation(
    [
        st.Page("pages/1_Dersler.py", title="Dersler", icon="🎓", default=True),
        st.Page("pages/2_Yukle.py", title="PDF Yükle", icon="📄"),
    ]
)
nav.run()
