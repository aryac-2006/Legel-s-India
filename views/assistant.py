import json, streamlit as st
from database import q, one, ex, audit, owned, log_error
from services import llm, retrieval
import config, ui

FEEDBACK = ["Helpful", "Incorrect or unsupported", "Outdated source", "Broken citation"]

def answer_text(p, srcs):
    if p["status"] == "insufficient": return "\n".join(p["notes"])
    lines = ["SHORT ANSWER", p["short_answer"], "", "EXPLANATION"] + p["explanation"] + ["", "CONDITIONS"] + p["conditions"] + ["", "NEXT STEPS"] + p["next_steps"]
    lines += ["", "SOURCES"] + [f"[{c['ref']}] {srcs[c['source_id']]['act']}, {srcs[c['source_id']]['section']} - {srcs[c['source_id']]['url']} ({srcs[c['source_id']]['verification_status']})" for c in p["citations"] if c["source_id"] in srcs]
    return "\n".join(lines + ["", ui.DISCLAIMER])

def ask(conv_id, question, language):
    ex("INSERT INTO messages(conversation_id,role,content) VALUES(?,?,?)", (conv_id, "user", question))
    flt = st.session_state.get("asst_filters") or {}
    hits = ui.index().search(question, k=5, mode="combined", filters=flt)
    ok = retrieval.is_sufficient(question, hits)
    payload = llm.build_answer(question, hits, llm.get_provider(), language, ok)
    mid = ex("INSERT INTO messages(conversation_id,role,content,payload) VALUES(?,?,?,?)", (conv_id, "assistant", payload.get("short_answer") or "Insufficient evidence", json.dumps(payload)))
    cited = {c["chunk_id"] for c in payload["citations"]}
    for h in payload["hits"]:
        ex("INSERT INTO retrieved_sources(message_id,source_id,chunk_id,rank,score,cited) VALUES(?,?,?,?,?,?)", (mid, h["source_id"], h["chunk_id"], h["rank"], h["score"], int(h["chunk_id"] in cited)))
    audit(ui.uid(), "assistant_query", f"conv={conv_id} status={payload['status']} rejected={payload['rejected']}")

def render(m):
    p = json.loads(m["payload"])
    if p["status"] == "insufficient":
        st.warning("**Insufficient evidence.** " + " ".join(p["notes"]))
        st.write("Suggested steps:"); [st.write("• " + s) for s in p["next_steps"]]
        return
    ids = [c["source_id"] for c in p["citations"]]
    srcs = {s["id"]: s for s in q(f"SELECT * FROM legal_sources WHERE id IN ({','.join('?'*len(ids))})", ids)} if ids else {}
    st.markdown("#### Short answer"); st.write(p["short_answer"])
    st.markdown("#### Relevant provisions")
    for c in p["citations"]:
        if c["source_id"] in srcs: st.caption(f"[{c['ref']}]"); ui.source_card(srcs[c["source_id"]], show_text=False)
    st.markdown("#### Explanation (generated from retrieved passages)")
    for e in p["explanation"]: st.write("• " + e)
    st.markdown("#### Important conditions or exceptions"); [st.write("• " + c) for c in p["conditions"]]
    st.markdown("#### Practical next steps"); [st.write("• " + c) for c in p["next_steps"]]
    for n in p["notes"]: st.caption("ℹ️ " + n)
    with st.expander("Retrieved evidence (original source text)"):
        for c in p["citations"]:
            if c["source_id"] in srcs: st.markdown(f"**[{c['ref']}]**"); ui.source_card(srcs[c["source_id"]])
        st.caption(f"{p['provider']}. Scores are ranking signals only, not legal confidence. {p['rejected']} invalid citation(s) rejected.")
    t = answer_text(p, srcs)
    with st.expander("Copy / export / save"):
        st.code(t, language=None)
        st.download_button("Download .txt", t, file_name="answer.txt", key=f"dl{m['id']}")
        mid = ui.matter_picker("Save answer to matter", key=f"sm{m['id']}")
        if mid and st.button("Save to matter", key=f"sb{m['id']}") and owned("matters", mid, ui.uid()):
            ex("INSERT OR IGNORE INTO matter_links(matter_id,user_id,kind,ref_id,label) VALUES(?,?,?,?,?)", (mid, ui.uid(), "message", m["id"], p["short_answer"][:80]))
            st.success("Saved.")
    with st.expander("Report this answer"):
        k = st.selectbox("Feedback", FEEDBACK, key=f"fk{m['id']}"); note = st.text_input("Note (optional)", key=f"fn{m['id']}")
        if st.button("Submit feedback", key=f"fs{m['id']}"):
            ex("INSERT INTO answer_feedback(message_id,user_id,kind,note) VALUES(?,?,?,?)", (m["id"], ui.uid(), k, note[:500])); st.success("Thanks, feedback recorded.")

def page():
    ui.header("Legal AI assistant", "Answers are built only from retrieved sources. Weak evidence is reported, never guessed.")
    prov = llm.get_provider(); st.caption(prov.label + (" - question and retrieved passages are sent to this provider." if prov.external else " - nothing leaves this app."))
    i = ui.uid()
    with st.expander("Conversations, language and filters", expanded=not st.session_state.get("conv_id")):
        s = st.text_input("Search conversations")
        convs = q("""SELECT DISTINCT c.id, c.title FROM conversations c LEFT JOIN messages m ON m.conversation_id=c.id
                     WHERE c.user_id=? AND (c.title LIKE ? OR m.content LIKE ?) ORDER BY c.id DESC LIMIT 30""", (i, f"%{s}%", f"%{s}%"))
        names = {c["id"]: c["title"] for c in convs}
        opts = [None] + list(names); cur = st.session_state.get("conv_id")
        pick = st.selectbox("Open conversation", opts, index=opts.index(cur) if cur in opts else 0, format_func=lambda x: "New conversation" if x is None else names[x])
        if pick != st.session_state.get("conv_id"): st.session_state["conv_id"] = pick
        lang = st.selectbox("Answer language", config.LANGUAGES, help="Hindi and Marathi need a configured AI provider.")
        doms = [r["domain"] for r in q("SELECT DISTINCT domain FROM legal_sources ORDER BY domain")]
        d = st.multiselect("Limit to legal domains", doms)
        st.session_state["asst_filters"] = {"domain": d} if d else {}
        if pick and st.button("Delete this conversation"):
            ex("DELETE FROM conversations WHERE id=? AND user_id=?", (pick, i)); audit(i, "conversation_delete", pick); st.session_state["conv_id"] = None; st.rerun()
    cid = st.session_state.get("conv_id")
    if cid and not owned("conversations", cid, i): cid = None; st.session_state["conv_id"] = None
    msgs = q("SELECT * FROM messages WHERE conversation_id=? ORDER BY id", (cid,)) if cid else []
    for m in msgs:
        with st.chat_message(m["role"]):
            st.write(m["content"]) if m["role"] == "user" else render(m)
    if msgs and msgs[-1]["role"] == "assistant":
        p = json.loads(msgs[-1]["payload"])
        if p["status"] == "ok":
            st.caption("Suggested follow-ups")
            hits = [c for c in p["citations"]][:2]
            ss = {s["id"]: s for s in q(f"SELECT * FROM legal_sources WHERE id IN ({','.join('?'*len(hits))})", [h["source_id"] for h in hits])} if hits else {}
            fu = [f"What are the conditions or exceptions under {s['act']}, {s['section']}?" for s in ss.values()] + ["What practical steps should I take next?"]
            for n, f in enumerate(fu): 
                if st.button(f, key=f"fu{n}"): st.session_state["queued_q"] = f; st.rerun()
    question = st.session_state.pop("queued_q", None) or st.chat_input("Ask a legal question in plain language")
    if question:
        try:
            if not cid:
                cid = ex("INSERT INTO conversations(user_id,title,language) VALUES(?,?,?)", (i, question[:60], lang)); st.session_state["conv_id"] = cid
            with st.status("Retrieving sources and validating citations...", expanded=False): ask(cid, question[:2000], lang)
            st.rerun()
        except Exception as e:
            log_error("assistant", e); st.error("Something went wrong while answering. Please try again.")
    ui.footer()
