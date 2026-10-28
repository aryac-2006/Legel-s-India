import streamlit as st
from datetime import date
from database import q, one, ex, owned, audit
from services import exports
import ui
from views import evidence as EV

def report_text(m):
    i = ui.uid(); out = [f"MATTER REPORT: {m['title']}", f"Category: {m['category']} | Status: {m['status']} | Archived: {bool(m['archived'])}", "", m["description"], "", "NOTES"]
    out += [f"- {n['created_at'][:10]}: {n['body']}" for n in q("SELECT * FROM matter_notes WHERE matter_id=? AND user_id=? ORDER BY id", (m["id"], i))]
    out += ["", "TASKS / DATES"] + [f"- {t['due_date']} [{'done' if t['done'] else 'open'}] {t['title']}" for t in q("SELECT * FROM tasks WHERE matter_id=? AND user_id=? ORDER BY due_date", (m["id"], i))]
    out += ["", "EVIDENCE INDEX"] + [f"- {e['event_date'] or 'n/a'}: {e['title']} (sha256 {e['sha256'][:12] or 'n/a'})" for e in q("SELECT * FROM evidence WHERE matter_id=? AND user_id=? ORDER BY event_date", (m["id"], i))]
    out += ["", "LINKED ITEMS"] + [f"- {l['kind']}: {l['label']}" for l in q("SELECT * FROM matter_links WHERE matter_id=? AND user_id=?", (m["id"], i))]
    return "\n".join(out + ["", ui.DISCLAIMER])

def timeline(m):
    i = ui.uid(); ev = [(m["created_at"][:10], "Matter created", m["title"])]
    ev += [(n["created_at"][:10], "Note", n["body"][:100]) for n in q("SELECT * FROM matter_notes WHERE matter_id=? AND user_id=?", (m["id"], i))]
    ev += [(t["due_date"], "Task" if t["kind"] == "task" else t["kind"].title(), t["title"] + (" (done)" if t["done"] else "")) for t in q("SELECT * FROM tasks WHERE matter_id=? AND user_id=?", (m["id"], i))]
    ev += [(e["event_date"] or e["added_on"][:10], "Evidence", e["title"]) for e in q("SELECT * FROM evidence WHERE matter_id=? AND user_id=?", (m["id"], i))]
    ev += [(l["created_at"][:10], "Linked " + l["kind"], l["label"]) for l in q("SELECT * FROM matter_links WHERE matter_id=? AND user_id=?", (m["id"], i))]
    return sorted(ev)

def detail(m):
    i = ui.uid()
    c = st.columns([4, 1, 1])
    c[0].subheader(m["title"] + ("  [DEMO]" if m["is_demo"] else "") + ("  (archived)" if m["archived"] else ""))
    if c[1].button("Reopen" if m["archived"] else "Archive"): ex("UPDATE matters SET archived=? WHERE id=? AND user_id=?", (0 if m["archived"] else 1, m["id"], i)); st.rerun()
    if c[2].button("Back to list"): st.session_state.pop("sel_matter"); st.rerun()
    t = st.tabs(["Details", "Notes", "Tasks & dates", "Linked items", "Timeline", "Evidence", "Report"])
    with t[0]:
        with st.form("edit"):
            title = st.text_input("Title", m["title"]); cat = st.selectbox("Category", ui.CATEGORIES, index=ui.CATEGORIES.index(m["category"]) if m["category"] in ui.CATEGORIES else 7)
            stt = st.selectbox("Status", ui.MATTER_STATUS, index=ui.MATTER_STATUS.index(m["status"])); desc = st.text_area("Description", m["description"])
            if st.form_submit_button("Save") and title.strip(): ex("UPDATE matters SET title=?,category=?,status=?,description=? WHERE id=? AND user_id=?", (title.strip(), cat, stt, desc, m["id"], i)); audit(i, "matter_update", m["id"]); st.rerun()
    with t[1]:
        n = st.text_area("Add a private note", key="newnote")
        if st.button("Add note") and n.strip(): ex("INSERT INTO matter_notes(matter_id,user_id,body) VALUES(?,?,?)", (m["id"], i, n.strip())); st.rerun()
        for x in q("SELECT * FROM matter_notes WHERE matter_id=? AND user_id=? ORDER BY id DESC", (m["id"], i)):
            c = st.columns([8, 1]); c[0].write(f"**{x['created_at'][:16]}** - {x['body']}")
            if c[1].button("✕", key=f"dn{x['id']}"): ex("DELETE FROM matter_notes WHERE id=? AND user_id=?", (x["id"], i)); st.rerun()
    with t[2]:
        with st.form("nt"):
            tt = st.text_input("Title"); k = st.selectbox("Type", ["task", "deadline", "event"]); dd = st.date_input("Date", date.today()); rd = st.number_input("Remind days before", 0, 60, 1)
            if st.form_submit_button("Add") and tt.strip(): ex("INSERT INTO tasks(user_id,matter_id,title,kind,due_date,reminder_days) VALUES(?,?,?,?,?,?)", (i, m["id"], tt.strip(), k, dd.isoformat(), int(rd))); st.rerun()
        st.caption("Dates are entered by you. The app does not calculate statutory deadlines.")
        for x in q("SELECT * FROM tasks WHERE matter_id=? AND user_id=? ORDER BY due_date", (m["id"], i)):
            if st.checkbox(f"{x['due_date']} - {x['title']} ({x['kind']})", value=bool(x["done"]), key=f"tk{x['id']}") != bool(x["done"]):
                ex("UPDATE tasks SET done=? WHERE id=? AND user_id=?", (0 if x["done"] else 1, x["id"], i)); st.rerun()
    with t[3]:
        kind = st.selectbox("Link type", ["document", "draft", "research"])
        opts = {"document": q("SELECT id, filename label FROM documents WHERE user_id=?", (i,)), "draft": q("SELECT id, title label FROM drafts WHERE user_id=?", (i,)),
                "research": q("SELECT s.id, s.act||', '||s.section label FROM saved_research r JOIN legal_sources s ON s.id=r.source_id WHERE r.user_id=?", (i,))}[kind]
        if opts:
            ch = st.selectbox("Item", [o["id"] for o in opts], format_func=lambda x: next(o["label"] for o in opts if o["id"] == x))
            if st.button("Link"): ex("INSERT OR IGNORE INTO matter_links(matter_id,user_id,kind,ref_id,label) VALUES(?,?,?,?,?)", (m["id"], i, kind, ch, next(o["label"] for o in opts if o["id"] == ch))); st.rerun()
        else: st.caption("Nothing of this type to link yet.")
        for l in q("SELECT * FROM matter_links WHERE matter_id=? AND user_id=?", (m["id"], i)):
            c = st.columns([8, 1]); c[0].write(f"{l['kind']}: {l['label']}")
            if c[1].button("✕", key=f"ul{l['id']}"): ex("DELETE FROM matter_links WHERE id=? AND user_id=?", (l["id"], i)); st.rerun()
    with t[4]:
        for d, k, txt in timeline(m): st.write(f"**{d}** · {k} · {txt}")
    with t[5]: EV.panel(m["id"])
    with t[6]:
        r = report_text(m); st.text_area("Consolidated report", r, height=300, disabled=True)
        st.download_button("Download .txt", r, file_name="matter_report.txt"); st.download_button("Download .docx", exports.make_docx(m["title"], r), file_name="matter_report.docx")

def page():
    ui.header("My cases", "Every matter belongs to your account only.")
    i = ui.uid()
    if st.session_state.get("sel_matter"):
        m = owned("matters", st.session_state["sel_matter"], i)
        if m: detail(m); ui.footer(); return
        st.session_state.pop("sel_matter")
    with st.expander("New matter"):
        with st.form("nm", clear_on_submit=True):
            t = st.text_input("Title"); c = st.selectbox("Category", ui.CATEGORIES); d = st.text_area("Description")
            if st.form_submit_button("Create") and t.strip(): ex("INSERT INTO matters(user_id,title,category,description) VALUES(?,?,?,?)", (i, t.strip(), c, d)); audit(i, "matter_create", t[:60]); st.rerun()
    a, b, c = st.columns(3); s = a.text_input("Search"); fs = b.multiselect("Status", ui.MATTER_STATUS, default=ui.MATTER_STATUS); arch = c.checkbox("Show archived")
    rows = [m for m in q("SELECT * FROM matters WHERE user_id=? ORDER BY id DESC", (i,)) if m["status"] in fs and (arch or not m["archived"]) and s.lower() in (m["title"] + m["description"]).lower()]
    if not rows: st.info("No matters match. Create one above.")
    for m in rows:
        with st.container(border=True):
            c = st.columns([5, 2, 1]); c[0].markdown(f"**{m['title']}** {'[DEMO]' if m['is_demo'] else ''}"); c[0].caption(f"{m['category']} · {m['description'][:90]}"); c[1].write(m["status"])
            if c[2].button("Open", key=f"o{m['id']}"): st.session_state["sel_matter"] = m["id"]; st.rerun()
    ui.footer()
