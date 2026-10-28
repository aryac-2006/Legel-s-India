import json, streamlit as st
from datetime import date
from database import q, ex, owned, audit
from services import exports
import ui

def build_report(a):
    events = sorted([e for e in a["events"] if e["date"].strip() or e["what"].strip()], key=lambda e: e["date"] or "9999")
    missing = []
    if not a["parties"].strip(): missing.append("Who are all the people or organisations involved, with full names and addresses?")
    if not events: missing.append("What happened, and on which dates?")
    if any(not e["date"].strip() for e in events): missing.append("Some events have no date. Can you find the dates from messages, receipts or calendars?")
    if not a["documents"].strip(): missing.append("Which documents (contracts, receipts, messages, notices) do you have?")
    if not a["goal"].strip(): missing.append("What outcome are you hoping for?")
    docs = [d.strip() for d in a["documents"].splitlines() if d.strip()]
    std = ["Government photo ID", "Any written agreement or terms", "Proof of payment (receipts, bank statements)", "Messages or emails with the other side", "Any notices sent or received"]
    L = ["CONSULTATION PREPARATION REPORT", "", "PART A - FACTS AS YOU PROVIDED THEM (verbatim)", f"Matter: {a['title']}", f"Parties: {a['parties'] or '[not provided]'}", f"Your goal: {a['goal'] or '[not provided]'}", "", "Chronology:"]
    L += [f"  {e['date'] or '[date unknown]'} - {e['what']}" for e in events] or ["  [none provided]"]
    L += ["", "PART B - ORGANISED SUMMARY (assembled automatically from Part A; not verified, not legal analysis)",
          f"The matter concerns '{a['title']}' and involves {a['parties'] or 'parties not yet identified'}. {len(events)} event(s) were recorded." + (f" Earliest: {events[0]['date']}; latest: {events[-1]['date']}." if events and events[0]['date'] and events[-1]['date'] else ""),
          "", "DOCUMENTS YOU HAVE"] + [f"  [x] {d}" for d in docs] + ["", "DOCUMENTS TO CONSIDER GATHERING"] + [f"  [ ] {d}" for d in std if not any(w in " ".join(docs).lower() for w in d.lower().split()[:2])]
    L += ["", "INFORMATION STILL MISSING"] + [f"  ? {m}" for m in missing] or ["  (none identified)"]
    L += ["", "QUESTIONS TO DISCUSS WITH AN ADVOCATE"] + [f"  - {x.strip()}" for x in a["questions"].splitlines() if x.strip()]
    L += ["  - Which forum or authority is appropriate for my situation?", "  - Are there time limits that apply to me, and when do they start?", "  - What are the possible options, costs and risks?", "  - Which documents should I bring or preserve?"]
    L += ["", "This report does not predict outcomes or assess the strength of any claim. " + ui.DISCLAIMER]
    return "\n".join(L)

def page():
    ui.header("Legal help preparation", "Organise your facts before you meet an advocate.")
    i = ui.uid(); t1, t2 = st.tabs(["New questionnaire", "Saved reports"])
    with t1:
        title = st.text_input("Short title for your situation"); parties = st.text_area("Who is involved? (names, relationship)")
        n = st.number_input("Number of events to record", 1, 12, 3); events = []
        for k in range(int(n)):
            c = st.columns([1, 4]); events.append({"date": c[0].text_input("Date (YYYY-MM-DD)", key=f"hd{k}"), "what": c[1].text_input("What happened", key=f"hw{k}")})
        docs = st.text_area("Documents you have (one per line)"); goal = st.text_area("What outcome do you want?"); qs = st.text_area("Your own questions (one per line)")
        mid = ui.matter_picker("Attach to matter (optional)", key="hpm")
        if st.button("Generate report") and title.strip():
            a = {"title": title, "parties": parties, "events": events, "documents": docs, "goal": goal, "questions": qs}
            st.session_state["hp_report"] = build_report(a)
            ex("INSERT INTO help_prep(user_id,matter_id,title,answers) VALUES(?,?,?,?)", (i, mid if mid and owned("matters", mid, i) else None, title[:100], json.dumps(a))); audit(i, "help_prep")
        if st.session_state.get("hp_report"):
            r = st.session_state["hp_report"]; st.text_area("Report (printable)", r, height=420)
            c = st.columns(2); c[0].download_button("Download .txt", r, file_name="consultation_prep.txt"); c[1].download_button("Download .docx", exports.make_docx("Consultation preparation", r), file_name="consultation_prep.docx")
    with t2:
        for h in q("SELECT * FROM help_prep WHERE user_id=? ORDER BY id DESC", (i,)):
            with st.expander(f"{h['created_at'][:10]} - {h['title']}"):
                st.text(build_report(json.loads(h["answers"])))
                if st.button("Delete", key=f"hpd{h['id']}"): ex("DELETE FROM help_prep WHERE id=? AND user_id=?", (h["id"], i)); st.rerun()
    ui.footer()
