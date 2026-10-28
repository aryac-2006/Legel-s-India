import streamlit as st
import config
from database import q, one, ex, audit
from services import ingest, retrieval, llm

DISCLAIMER = ("Legal S India provides legal information and document assistance only. It is not a law firm, a government portal, "
              "or an official judicial system, and it is not a substitute for advice from a qualified advocate.")
PAGES = {}
MATTER_STATUS = ["Open", "In Progress", "On Hold", "Closed"]
CATEGORIES = ["Consumer", "Property", "Family", "Labour", "Criminal", "Cyber", "Contract", "Other"]
CSS = """<style>
h1,h2,h3{color:#0B1F3A;font-family:Georgia,serif} [data-testid=stSidebar]{background:#0B1F3A}
[data-testid=stSidebar] *{color:#E9E4D6!important} .stButton>button{border:1px solid #B8975A;border-radius:6px}
.src{border-left:3px solid #B8975A;background:#fff;padding:.6rem .9rem;margin:.4rem 0;border-radius:4px}
.badge{font-size:.72rem;padding:2px 8px;border-radius:10px;background:#EFE9D8;color:#0B1F3A;margin-right:6px}
.warn{background:#fff4e5;border-left:3px solid #e0a030;padding:.5rem .8rem;border-radius:4px}
</style>"""


def user():
    return st.session_state.get("user")


def uid():
    return st.session_state["user"]["id"]


def go(key, **state):
    st.session_state.update(state)
    st.switch_page(PAGES[key])


def header(title, caption=None):
    st.title(title)
    if caption:
        st.caption(caption)


def footer():
    st.divider()
    st.caption(DISCLAIMER)


@st.cache_resource
def _build_index(version):
    return retrieval.Index(ingest.load_chunks())


def index():
    return _build_index(ingest.chunks_version())


def my_matters(include_archived=False):
    sql = "SELECT * FROM matters WHERE user_id=?" + ("" if include_archived else " AND archived=0") + " ORDER BY created_at DESC"
    return q(sql, (uid(),))


def matter_picker(label="Matter", key=None, optional=True):
    ms = my_matters()
    opts = ([None] if optional else []) + [m["id"] for m in ms]
    names = {m["id"]: m["title"] for m in ms}
    return st.selectbox(label, opts, format_func=lambda i: "None" if i is None else names[i], key=key)


def source_card(s, show_text=True):
    badge = {"verified": "✅ verified", "unverified": "⚠️ unverified", "outdated": "⛔ outdated"}[s["verification_status"]]
    st.markdown(f"<div class='src'><b>{s['act']}, {s['section']}</b> - {s['title']}<br>"
                f"<span class='badge'>{s['domain']}</span><span class='badge'>{s['doc_type']}</span><span class='badge'>{badge}</span>"
                f"<span class='badge'>v{s['version']}</span></div>", unsafe_allow_html=True)
    if show_text:
        st.write(s["text"])
    c1, c2 = st.columns(2)
    c1.caption(f"Source: {s['source_name'] or 'n/a'} | Retrieved: {s['retrieved_on'] or 'n/a'}")
    if s["url"]:
        c2.markdown(f"[Open official source]({s['url']})")
    if s.get("effective_info"):
        st.caption("Amendment/effective-date info: " + s["effective_info"])
