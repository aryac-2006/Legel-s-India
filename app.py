"""Legal S India - Streamlit entry point.   Run:  streamlit run app.py"""
import streamlit as st

st.set_page_config(page_title="Legal S India", page_icon="⚖️", layout="wide")

import auth, database, ui
from services import ingest
from views import (public, dashboard, assistant, research, graph, documents, compare, drafting, cases,
                    evidence, calendar_view, helpprep, privacy, search, analytics, admin)


@st.cache_resource
def _bootstrap():
    database.init_db(); auth.bootstrap_admin(); ingest.bootstrap_sources(); return True


_bootstrap()
st.markdown(ui.CSS, unsafe_allow_html=True)


def sign_out():
    database.audit(ui.uid(), "logout"); st.session_state.clear(); st.rerun()


def P(fn, title, key, icon=None):
    pg = st.Page(fn, title=title, icon=icon, url_path=key); ui.PAGES[key] = pg; return pg


if not ui.user():
    nav = st.navigation([P(public.home, "Home", "home", "🏠"), P(public.about, "About", "about", "ℹ️"), P(public.sign_in, "Sign in", "signin", "🔑"),
                         P(public.register, "Register", "register", "📝"), P(public.privacy_policy, "Privacy policy", "privacy-policy", "🔒"),
                         P(public.disclaimer, "Legal disclaimer", "disclaimer", "⚖️")])
else:
    sections = {
        "Workspace": [P(dashboard.page, "Overview", "overview", "🏠"), P(assistant.page, "Legal AI Assistant", "assistant", "💬"),
                      P(research.page, "Legal Research", "research", "📚"), P(graph.page, "Knowledge Graph", "graph", "🕸️"),
                      P(search.page, "Global Search", "search", "🔎")],
        "Documents": [P(documents.page, "Document Analyzer", "docs", "📄"), P(compare.page, "Document Comparison", "compare", "🆚"),
                      P(drafting.page, "Document Drafting", "drafting", "✍️")],
        "Matters": [P(cases.page, "My Cases", "cases", "📁"), P(evidence.page, "Evidence Organizer", "evidence", "🗂️"),
                    P(calendar_view.page, "Important Dates", "calendar", "📅"), P(helpprep.page, "Help Preparation", "helpprep", "🧭")],
        "Account": [P(analytics.page, "Analytics", "analytics", "📊"), P(privacy.page, "Privacy & Security", "privacy", "🛡️")],
    }
    if auth.is_admin(ui.user()):
        sections["Administration"] = [P(admin.page, "Administration", "admin", "⚙️")]
    sections["Account"].append(P(sign_out, "Sign out", "signout", "🚪"))
    nav = st.navigation(sections)
    with st.sidebar:
        st.caption(f"{ui.user()['name']} · {ui.user()['role']}")
        r = calendar_view.reminders(ui.uid())
        with st.expander(f"🔔 Reminders ({len(r)})"):
            for kind, t in r[:8]: st.caption(f"{kind}: {t['due_date']} - {t['title']}")
            if not r: st.caption("Nothing due.")
            st.caption("In-app only. No email or push notifications are sent.")
nav.run()
