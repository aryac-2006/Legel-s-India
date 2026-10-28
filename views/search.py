import streamlit as st
from database import q
import ui

def page():
    ui.header("Global search", "Searches only your own records (plus the shared legal source library).")
    i = ui.uid(); s = st.text_input("Search everything"); kinds = st.multiselect("Categories", ["Matters", "Documents", "Drafts", "Saved research", "Conversations", "Notes", "Timeline", "Legal sources"], default=["Matters", "Documents", "Drafts", "Saved research", "Conversations", "Notes", "Timeline", "Legal sources"])
    if len(s.strip()) < 2: st.caption("Type at least two characters."); return
    like = f"%{s.strip()}%"; n = 0
    def row(cat, title, meta, key, page=None, **state):
        nonlocal n; n += 1; c = st.columns([1, 5, 1]); c[0].caption(cat); c[1].write(f"**{title}**  \n{meta}")
        if page and c[2].button("Open", key=f"{key}"): ui.go(page, **state)
    if "Matters" in kinds:
        for m in q("SELECT * FROM matters WHERE user_id=? AND (title LIKE ? OR description LIKE ?)", (i, like, like)): row("Matter", m["title"], f"{m['category']} · {m['status']}", f"gm{m['id']}", "cases", sel_matter=m["id"])
    if "Documents" in kinds:
        for d in q("SELECT id,filename,created_at FROM documents WHERE user_id=? AND (filename LIKE ? OR text LIKE ?)", (i, like, like)): row("Document", d["filename"], d["created_at"][:10], f"gd{d['id']}", "docs", doc_id=d["id"])
    if "Drafts" in kinds:
        for d in q("SELECT DISTINCT d.id,d.title FROM drafts d JOIN draft_versions v ON v.draft_id=d.id WHERE d.user_id=? AND (d.title LIKE ? OR v.content LIKE ?)", (i, like, like)): row("Draft", d["title"], "", f"gr{d['id']}", "drafting")
    if "Saved research" in kinds:
        for r in q("SELECT s.id,s.act,s.section FROM saved_research r JOIN legal_sources s ON s.id=r.source_id WHERE r.user_id=? AND (s.act LIKE ? OR s.text LIKE ? OR r.note LIKE ?)", (i, like, like, like)): row("Saved research", f"{r['act']}, {r['section']}", "", f"gs{r['id']}", "research")
    if "Conversations" in kinds:
        for c in q("SELECT DISTINCT c.id,c.title FROM conversations c JOIN messages m ON m.conversation_id=c.id WHERE c.user_id=? AND (c.title LIKE ? OR m.content LIKE ?)", (i, like, like)): row("Conversation", c["title"], "", f"gc{c['id']}", "assistant", conv_id=c["id"])
    if "Notes" in kinds:
        for nn in q("SELECT n.id,n.body,n.matter_id FROM matter_notes n WHERE n.user_id=? AND n.body LIKE ?", (i, like)): row("Note", nn["body"][:80], "", f"gn{nn['id']}", "cases", sel_matter=nn["matter_id"])
    if "Timeline" in kinds:
        for t in q("SELECT id,title,due_date,matter_id FROM tasks WHERE user_id=? AND (title LIKE ? OR description LIKE ?)", (i, like, like)): row("Timeline", t["title"], t["due_date"], f"gt{t['id']}", "calendar")
        for e in q("SELECT id,title,event_date,matter_id FROM evidence WHERE user_id=? AND (title LIKE ? OR description LIKE ? OR timeline_note LIKE ?)", (i, like, like, like)): row("Evidence", e["title"], e["event_date"] or "", f"ge{e['id']}", "cases", sel_matter=e["matter_id"])
    if "Legal sources" in kinds:
        for l in q("SELECT id,act,section,title FROM legal_sources WHERE act LIKE ? OR title LIKE ? OR text LIKE ? LIMIT 15", (like, like, like)): row("Source", f"{l['act']}, {l['section']}", l["title"], f"gl{l['id']}", "research", saved_q=f"{l['act']} {l['section']}")
    if not n: st.info("No results.")
