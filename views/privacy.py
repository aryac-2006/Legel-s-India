import json, streamlit as st
from database import q, ex, owned, audit
from services import llm, exports
import security, ui

def export_all(i):
    tabs = ["matters", "matter_notes", "tasks", "evidence", "drafts", "saved_research", "collections", "saved_searches", "conversations", "documents", "help_prep", "comparisons"]
    out = {t: q(f"SELECT * FROM {t} WHERE user_id=?", (i,)) for t in tabs}
    for d in out["documents"]: d["text"] = d["text"][:200000]; d.pop("stored_path", None)
    out["messages"] = q("SELECT m.* FROM messages m JOIN conversations c ON c.id=m.conversation_id WHERE c.user_id=?", (i,))
    out["draft_versions"] = q("SELECT v.* FROM draft_versions v JOIN drafts d ON d.id=v.draft_id WHERE d.user_id=?", (i,))
    out["profile"] = q("SELECT id,email,name,role,language,created_at FROM users WHERE id=?", (i,))
    return json.dumps(out, indent=1, default=str)

def page():
    ui.header("Privacy and security centre")
    i = ui.uid(); u = ui.user(); prov = llm.get_provider()
    t = st.tabs(["Sessions & access", "External AI", "Delete data", "Export & redaction", "Audit history"])
    with t[0]:
        st.write(f"Signed in as **{u['email']}** (role: {u['role']}). Sign-in lasts for this browser session only; use *Sign out* to end it. Your password is stored only as a salted scrypt hash.")
        n = q("SELECT COUNT(*) n FROM documents WHERE user_id=?", (i,))[0]["n"]
        st.write(f"You have {n} stored document(s). Files are saved on the server under your own folder and are served only to you. Administrators have no screen for reading your documents, conversations or matters.")
    with t[1]:
        if prov.external: st.warning(f"An external AI provider is configured ({prov.label}). When you ask the assistant a question, your question and the retrieved legal passages are sent to it. Uploaded documents and matter data are not sent.")
        else: st.success("No external AI provider is configured. Nothing you enter is sent outside this application.")
        st.write("Retention: data stays until you delete it or an operator deletes the database. This is a demonstration project and has not been assessed against any compliance standard.")
    with t[2]:
        for c in q("SELECT id,title FROM conversations WHERE user_id=? ORDER BY id DESC", (i,)):
            cc = st.columns([6, 1]); cc[0].write("💬 " + c["title"])
            if cc[1].button("Delete", key=f"pc{c['id']}"): ex("DELETE FROM conversations WHERE id=? AND user_id=?", (c["id"], i)); audit(i, "conversation_delete", c["id"]); st.rerun()
        for d in q("SELECT id,filename,stored_path FROM documents WHERE user_id=? ORDER BY id DESC", (i,)):
            cc = st.columns([6, 1]); cc[0].write("📄 " + d["filename"])
            if cc[1].button("Delete", key=f"pd{d['id']}"): security.delete_file(d["stored_path"]); ex("DELETE FROM documents WHERE id=? AND user_id=?", (d["id"], i)); audit(i, "document_delete", d["id"]); st.rerun()
    with t[3]:
        st.download_button("Download all my data (JSON)", export_all(i), file_name="my_legal_s_india_data.json")
        st.subheader("Redact an exported document copy")
        ds = q("SELECT id,filename FROM documents WHERE user_id=? AND status='analysed'", (i,))
        if ds:
            sel = st.selectbox("Document", [d["id"] for d in ds], format_func=lambda x: next(d["filename"] for d in ds if d["id"] == x)); terms = st.text_area("Text to redact (one per line)")
            d = owned("documents", sel, i)
            if d and terms.strip():
                red = exports.redact(d["text"], terms.splitlines()); st.text_area("Preview", red[:3000], height=200)
                st.download_button("Download redacted .docx", exports.make_docx("Redacted copy", red), file_name="redacted.docx")
                st.caption("Redaction is plain text matching on the extracted text. Check the result; the original file is unchanged.")
        else: st.caption("No analysed documents.")
    with t[4]:
        for e in q("SELECT * FROM audit_events WHERE user_id=? ORDER BY id DESC LIMIT 100", (i,)): st.caption(f"{e['created_at']} - {e['action']} {e['detail']}")
    ui.footer()
