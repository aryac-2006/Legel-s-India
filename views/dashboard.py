import pandas as pd, streamlit as st
from datetime import date
from database import q, one
import ui

def page():
    u = ui.user(); ui.header(f"Welcome, {u['name']}", "Your workspace at a glance")
    qq = st.text_input("Ask a legal question", placeholder="e.g. How do I file a consumer complaint?")
    if st.button("Ask the assistant") and qq.strip():
        ui.go("assistant", queued_q=qq.strip())
    cols = st.columns(4)
    for c, (label, key, page) in zip(cols, [("New matter", "cases", "cases"), ("Analyse document", "docs", "docs"), ("Draft a document", "drafting", "drafting"), ("Research", "research", "research")]):
        if c.button(label, key=f"qa_{key}"): ui.go(page)
    i = ui.uid()
    ms = q("SELECT * FROM matters WHERE user_id=? AND archived=0", (i,))
    n = lambda sql: one(sql, (i,))["n"]
    tasks_open = q("SELECT * FROM tasks WHERE user_id=? AND done=0 ORDER BY due_date LIMIT 5", (i,))
    m = st.columns(5)
    m[0].metric("Matters", len(ms)); m[1].metric("Documents analysed", n("SELECT COUNT(*) n FROM documents WHERE user_id=? AND status='analysed'"))
    m[2].metric("Drafts", n("SELECT COUNT(*) n FROM drafts WHERE user_id=?")); m[3].metric("Saved research", n("SELECT COUNT(*) n FROM saved_research WHERE user_id=?"))
    m[4].metric("Open tasks", n("SELECT COUNT(*) n FROM tasks WHERE user_id=? AND done=0"))
    if any(x["is_demo"] for x in ms): st.caption("Items tagged [DEMO] are demonstration data.")
    a, b = st.columns(2)
    with a:
        st.subheader("Matters by status")
        if ms: st.bar_chart(pd.Series([x["status"] for x in ms]).value_counts())
        else: st.caption("No matters yet.")
        st.subheader("Recent research")
        for r in q("SELECT s.id, s.act, s.section FROM saved_research r JOIN legal_sources s ON s.id=r.source_id WHERE r.user_id=? ORDER BY r.id DESC LIMIT 4", (i,)):
            st.write(f"• {r['act']}, {r['section']}")
    with b:
        st.subheader("Upcoming deadlines and tasks")
        for t in tasks_open:
            od = " ⚠️ overdue" if t["due_date"] < date.today().isoformat() else ""
            st.write(f"• {t['due_date']} - {t['title']}{od}")
        if not tasks_open: st.caption("Nothing pending.")
        st.subheader("Recent documents")
        for d in q("SELECT filename, status FROM documents WHERE user_id=? ORDER BY id DESC LIMIT 4", (i,)):
            st.write(f"• {d['filename']} ({d['status']})")
        st.subheader("Activity")
        for e in q("SELECT action, detail, created_at FROM audit_events WHERE user_id=? ORDER BY id DESC LIMIT 6", (i,)):
            st.caption(f"{e['created_at']} - {e['action']} {e['detail']}")
    ui.footer()
