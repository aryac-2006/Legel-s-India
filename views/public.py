import streamlit as st
import auth
import ui

def home():
    st.markdown(ui.CSS, unsafe_allow_html=True)
    st.title("⚖️ Legal S India")
    st.subheader("Understand Indian law. Organise your legal matters.")
    st.write("Many people struggle to find reliable legal information, read agreements, or keep track of documents and dates. "
             "Legal S India brings research, document review, drafting and case organisation into one workspace, with answers tied to retrievable sources.")
    st.markdown("### What you can do")
    c = st.columns(3)
    feats = [("Source-grounded assistant", "Answers are built from retrieved passages. Every citation is checked against real retrieval results, and weak evidence is reported honestly."),
             ("Document intelligence", "Upload PDF or DOCX files, extract text, find key clauses and compare two versions."),
             ("Case workspace", "Matters, notes, tasks, evidence index, calendar and reports in one place."),
             ("Legal research", "Keyword, vector and combined search with filters, version history and a knowledge graph."),
             ("Drafting studio", "Eight templates with versioning and DOCX/PDF export. Missing facts stay as visible placeholders."),
             ("Privacy first", "Your records are visible only to you. Administrators cannot read your documents or conversations.")]
    for i, (t, d) in enumerate(feats):
        with c[i % 3].container(border=True):
            st.markdown(f"**{t}**"); st.caption(d)
    st.info("Use **Sign in** or **Register** in the sidebar to begin. " + ui.DISCLAIMER)

def about():
    st.markdown(ui.CSS, unsafe_allow_html=True)
    st.title("About the platform")
    st.write("Legal S India is an academic engineering project built with Python and Streamlit. It demonstrates information retrieval, "
             "document processing, relational database design, authentication and secure data handling.")
    st.markdown("**Architecture:** Streamlit UI → service layer (retrieval, documents, drafting, exports) → SQLite database. "
                "Retrieval uses BM25 keyword search, TF-IDF vector similarity and Reciprocal Rank Fusion. An external AI provider is optional.")
    st.warning("Not a law firm, not a government portal, and not an official judicial system. The bundled legal knowledge base is a small "
               "demonstration set of paraphrased summaries marked *unverified* until checked against India Code.")

def sign_in():
    st.markdown(ui.CSS, unsafe_allow_html=True)
    st.title("Sign in")
    with st.form("login"):
        e = st.text_input("Email"); p = st.text_input("Password", type="password")
        if st.form_submit_button("Sign in"):
            u, msg = auth.login(e, p)
            if u:
                st.session_state["user"] = u; st.rerun()
            st.error(msg)

def register():
    st.markdown(ui.CSS, unsafe_allow_html=True)
    st.title("Create an account")
    with st.form("reg"):
        n = st.text_input("Full name"); e = st.text_input("Email"); p = st.text_input("Password (min 8 characters)", type="password")
        if st.form_submit_button("Register"):
            ok, msg = auth.register(e, n, p); (st.success if ok else st.error)(msg)

def privacy_policy():
    st.title("Privacy policy")
    st.markdown("""
**What we store:** your account (email, name, salted scrypt password hash), conversations, uploaded documents and extracted text, drafts, matters, notes, tasks and evidence records.

**Who can see it:** only you. Administrators can manage accounts and legal sources and see aggregate counts and security events, but the application provides no screen for reading your private content.

**External AI:** by default nothing leaves the application. If the operator configures an AI provider, the text of your question and the retrieved legal passages are sent to that provider. Uploaded documents are not sent unless a feature explicitly says so.

**Retention and deletion:** you can delete conversations and documents (and their analyses) from the Privacy centre, and export your data as JSON.

**Limits:** this is a demonstration project; it has not been audited against any compliance standard.""")

def disclaimer():
    st.title("Legal disclaimer")
    st.write(ui.DISCLAIMER)
    st.write("Answers may be incomplete or outdated. Laws are amended and repealed. Automated analysis can miss or misread text. "
             "Generated drafts are not guaranteed to be valid or suitable for filing in any court. Always consult a qualified advocate.")
