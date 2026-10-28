import json, streamlit as st
from database import q, ex, owned, audit, log_error
from services import diffing
import ui, security
from views.documents import process

def page():
    ui.header("Document comparison lab", "Real text differences (difflib). Any AI explanation only describes the detected changes.")
    i = ui.uid(); docs = q("SELECT id, filename FROM documents WHERE user_id=? AND status='analysed' ORDER BY id DESC", (i,))
    names = {d["id"]: d["filename"] for d in docs}
    if len(docs) < 2: st.info("Upload at least two documents in the Document analyzer first.")
    else:
        c = st.columns(2); a = c[0].selectbox("Document A (original)", list(names), format_func=lambda x: names[x]); b = c[1].selectbox("Document B (revised)", list(names), index=1, format_func=lambda x: names[x])
        if st.button("Compare"):
            da, db_ = owned("documents", a, i), owned("documents", b, i)
            if da and db_:
                r = diffing.compare(da["text"], db_["text"]); st.session_state["cmp"] = (da["filename"], db_["filename"], da["text"], db_["text"], r)
                ex("INSERT INTO comparisons(user_id,doc_a,doc_b,result) VALUES(?,?,?,?)", (i, da["filename"], db_["filename"], json.dumps(r))); audit(i, "compare", f"{a} vs {b}")
    if "cmp" in st.session_state:
        na, nb, ta, tb, r = st.session_state["cmp"]
        if r["identical"]: st.success("The two documents have identical text.")
        m = st.columns(4); m[0].metric("Unchanged", r["unchanged"]); m[1].metric("Added", len(r["added"])); m[2].metric("Removed", len(r["removed"])); m[3].metric("Modified", len(r["modified"]))
        t = st.tabs(["Modified", "Added / removed", "Facts", "Side by side", "Export"])
        with t[0]:
            for x in r["modified"]:
                l, rr = diffing.word_diff_html(x["before"], x["after"]); c = st.columns(2); c[0].markdown(l, unsafe_allow_html=True); c[1].markdown(rr, unsafe_allow_html=True); st.caption(f"similarity {x['similarity']}"); st.divider()
        with t[1]:
            for x in r["added"]: st.markdown(f"🟢 **Added:** {x}")
            for x in r["removed"]: st.markdown(f"🔴 **Removed:** {x}")
        with t[2]:
            for k, v in r["facts"].items(): st.markdown(f"**{k}**"); st.write(f"Only in A: {v['only_in_a'] or '—'}  |  Only in B: {v['only_in_b'] or '—'}  |  Common: {v['common'] or '—'}")
        with t[3]:
            l, rr = diffing.word_diff_html(ta[:20000], tb[:20000]); c = st.columns(2); c[0].markdown(f"**{na}**"); c[0].markdown(l.replace("\n", "<br>"), unsafe_allow_html=True); c[1].markdown(f"**{nb}**"); c[1].markdown(rr.replace("\n", "<br>"), unsafe_allow_html=True)
        with t[4]:
            rep = diffing.report_text(na, nb, r); st.download_button("Report (.txt)", rep, file_name="comparison.txt")
            from services import exports; st.download_button("Report (.docx)", exports.make_docx("Comparison report", rep), file_name="comparison.docx")
            from services import llm
            if llm.get_provider().external: st.caption("An AI explanation would send only the detected differences (not whole documents) to the provider. Not enabled in this build.")
    st.subheader("History")
    for h in q("SELECT * FROM comparisons WHERE user_id=? ORDER BY id DESC LIMIT 10", (i,)):
        r = json.loads(h["result"]); st.write(f"{h['created_at'][:16]} - {h['doc_a']} vs {h['doc_b']}: +{len(r['added'])} / -{len(r['removed'])} / ~{len(r['modified'])}")
    ui.footer()
