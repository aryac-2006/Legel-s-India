import streamlit as st
from datetime import date
from database import q, one, ex, owned, audit
from services import exports
import security, ui

INTEGRITY = "A SHA-256 hash shows only that a file has not changed since it was hashed. It does not establish authenticity, authorship or legal admissibility."

def panel(matter_id):
    i = ui.uid()
    if not owned("matters", matter_id, i): st.error("Not found."); return
    st.caption(INTEGRITY)
    with st.form(f"ev{matter_id}", clear_on_submit=True):
        t = st.text_input("Evidence title"); d = st.text_area("Description"); ed = st.date_input("Date of the recorded event", date.today()); n = st.text_area("Notes"); tl = st.text_input("Related timeline entry (optional)")
        f = st.file_uploader("File to fingerprint (optional; the file itself is not stored)")
        if st.form_submit_button("Add evidence") and t.strip():
            h = security.sha256(f.getvalue()) if f else ""
            ex("INSERT INTO evidence(user_id,matter_id,title,description,event_date,file_type,filename,notes,timeline_note,sha256) VALUES(?,?,?,?,?,?,?,?,?,?)",
               (i, matter_id, t.strip(), d, ed.isoformat(), (f.name.rsplit(".", 1)[-1] if f else ""), security.safe_filename(f.name) if f else "", n, tl, h)); audit(i, "evidence_add", t[:60]); st.rerun()
    s = st.text_input("Search evidence", key=f"se{matter_id}")
    rows = [e for e in q("SELECT * FROM evidence WHERE matter_id=? AND user_id=? ORDER BY event_date, id", (matter_id, i)) if s.lower() in (e["title"] + e["description"] + e["notes"]).lower()]
    for e in rows:
        with st.expander(f"{e['event_date'] or 'n/a'} - {e['title']}"):
            st.write(e["description"]); st.caption(f"Added {e['added_on'][:10]} | file: {e['filename'] or 'none'} ({e['file_type']}) | SHA-256: {e['sha256'] or 'n/a'}")
            if e["timeline_note"]: st.caption("Timeline: " + e["timeline_note"])
            st.write(e["notes"])
            nt = st.text_input("Edit title", e["title"], key=f"et{e['id']}")
            c = st.columns(2)
            if c[0].button("Update title", key=f"eu{e['id']}"): ex("UPDATE evidence SET title=? WHERE id=? AND user_id=?", (nt, e["id"], i)); st.rerun()
            if c[1].button("Remove", key=f"er{e['id']}"): ex("DELETE FROM evidence WHERE id=? AND user_id=?", (e["id"], i)); st.rerun()
    if rows:
        rep = "EVIDENCE INDEX (chronological)\n" + "\n".join(f"{e['event_date'] or 'n/a'} | {e['title']} | added {e['added_on'][:10]} | {e['file_type'] or '-'} | sha256 {e['sha256'] or 'n/a'}" for e in rows) + "\n\n" + INTEGRITY
        st.download_button("Export evidence index (.txt)", rep, file_name="evidence_index.txt", key=f"ex{matter_id}"); st.download_button("Export (.docx)", exports.make_docx("Evidence index", rep), file_name="evidence_index.docx", key=f"exd{matter_id}")

def page():
    ui.header("Evidence organizer", "Index the evidence for a matter. Files are fingerprinted, not stored.")
    mid = ui.matter_picker("Matter", key="evm", optional=False) if ui.my_matters() else None
    if mid: panel(mid)
    else: st.info("Create a matter first.")
    ui.footer()
