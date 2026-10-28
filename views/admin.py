import pandas as pd, streamlit as st
from database import q, one, ex, db, audit
from services import ingest, diffing
import auth, config, ui

def page():
    if not auth.is_admin(ui.user()): st.error("Not authorised."); return     # server-side check
    ui.header("Administration", "Aggregate and operational views only. There is no screen for reading private user content.")
    i = ui.uid(); t = st.tabs(["Users", "Legal sources", "Import", "Jobs & errors", "Feedback", "Security & audit", "Health"])
    with t[0]:
        for u in q("SELECT id,email,role,is_active,created_at FROM users ORDER BY id"):
            c = st.columns([4, 2, 2])
            c[0].write(f"{u['email']}  ·  joined {u['created_at'][:10]}")
            if u["id"] == i: c[1].caption("you"); continue
            r = c[1].selectbox("Role", ["user", "professional", "admin"], index=["user", "professional", "admin"].index(u["role"]), key=f"r{u['id']}")
            a = c[2].toggle("Active", bool(u["is_active"]), key=f"a{u['id']}")
            if r != u["role"]: ex("UPDATE users SET role=? WHERE id=?", (r, u["id"])); audit(i, "role_change", f"{u['id']}->{r}"); st.rerun()
            if a != bool(u["is_active"]): ex("UPDATE users SET is_active=? WHERE id=?", (int(a), u["id"])); audit(i, "user_active_toggle", f"{u['id']}={a}"); st.rerun()
    with t[1]:
        srcs = q("SELECT id,act,section,domain,verification_status,version,retrieved_on FROM legal_sources ORDER BY act, section")
        st.dataframe(pd.DataFrame(srcs))
        sid = st.selectbox("Edit source", [s["id"] for s in srcs], format_func=lambda x: next(f"{s['act']}, {s['section']}" for s in srcs if s["id"] == x))
        s = one("SELECT * FROM legal_sources WHERE id=?", (sid,))
        with st.form("src"):
            txt = st.text_area("Text", s["text"], height=160); url = st.text_input("Official URL", s["url"]); eff = st.text_input("Effective / amendment info", s["effective_info"] or "")
            vs = st.selectbox("Verification status", ["unverified", "verified", "outdated"], index=["unverified", "verified", "outdated"].index(s["verification_status"])); ver = st.text_input("Version", s["version"])
            if st.form_submit_button("Save"):
                with db() as c:
                    c.execute("INSERT INTO source_versions(source_id,version,text,verification_status,note) VALUES(?,?,?,?,?)", (sid, s["version"], s["text"], s["verification_status"], "admin edit"))
                    c.execute("UPDATE legal_sources SET text=?,url=?,effective_info=?,verification_status=?,version=? WHERE id=?", (txt, url, eff, vs, ver, sid))
                    c.execute("DELETE FROM legal_chunks WHERE source_id=?", (sid,)); ingest._rebuild_chunks(c, sid, txt)
                audit(i, "source_edit", f"{sid} status={vs}"); st.success("Saved. A version snapshot was stored."); st.rerun()
        st.caption("Mark a source *verified* only after comparing it with the official text on India Code or another authoritative site.")
    with t[2]:
        st.write("CSV columns: title, act, domain, text (required); section, doc_type, source_name, url, verification_status, version, retrieved_on, effective_info (optional). Import only legally sourced material.")
        up = st.file_uploader("CSV file", type=["csv"])
        if up and st.button("Import"):
            r = ingest.import_csv(up.getvalue(), i, up.name); audit(i, "source_import", f"{r['status']} ok={r['ok']} failed={r['failed']}"); st.write(r)
    with t[3]:
        st.markdown("**Ingestion jobs**"); st.dataframe(pd.DataFrame(q("SELECT * FROM ingestion_jobs ORDER BY id DESC LIMIT 30")))
        st.markdown("**Application errors / processing failures**"); st.dataframe(pd.DataFrame(q("SELECT * FROM error_log ORDER BY id DESC LIMIT 30")))
        st.markdown("**Documents that failed processing (metadata only)**"); st.dataframe(pd.DataFrame(q("SELECT id, filename, status_note, created_at FROM documents WHERE status='failed' ORDER BY id DESC LIMIT 30")))
    with t[4]:
        st.dataframe(pd.DataFrame(q("""SELECT f.id, f.kind, f.note, f.created_at, s.act, s.section FROM answer_feedback f
            LEFT JOIN retrieved_sources r ON r.message_id=f.message_id AND r.cited=1 LEFT JOIN legal_sources s ON s.id=r.source_id ORDER BY f.id DESC LIMIT 100""")))
        st.caption("Shows the feedback and which sources were cited, not the user's question or conversation.")
    with t[5]:
        st.dataframe(pd.DataFrame(q("SELECT * FROM audit_events WHERE action IN ('login_failed','login_locked','role_change','user_active_toggle','source_edit','source_import','bootstrap_admin') ORDER BY id DESC LIMIT 100")))
    with t[6]:
        cnt = lambda t: one(f"SELECT COUNT(*) n FROM {t}")["n"]
        c = st.columns(4); c[0].metric("Users", cnt("users")); c[1].metric("Sources", cnt("legal_sources")); c[2].metric("Documents (all)", cnt("documents")); c[3].metric("Matters (all)", cnt("matters"))
        import os; st.write(f"Database size: {os.path.getsize(config.DB_PATH)/1024:.0f} KB"); st.write("AI provider:", ui.llm.get_provider().label)
        st.caption("Counts only. Content of user records is not shown.")
