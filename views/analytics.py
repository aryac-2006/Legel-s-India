import pandas as pd, streamlit as st
from database import q, one
from services import retrieval, ingest
import ui

def page():
    ui.header("Analytics", "Part 1 shows YOUR activity from stored data. Part 2 shows AI retrieval evaluation. They are different things.")
    i = ui.uid(); st.subheader("Your activity")
    ms = q("SELECT status FROM matters WHERE user_id=?", (i,)); c = st.columns(4)
    n = lambda s: one(s, (i,))["n"]
    c[0].metric("Matters", len(ms)); c[1].metric("Documents analysed", n("SELECT COUNT(*) n FROM documents WHERE user_id=? AND status='analysed'")); c[2].metric("Drafts", n("SELECT COUNT(*) n FROM drafts WHERE user_id=?")); c[3].metric("Saved research", n("SELECT COUNT(*) n FROM saved_research WHERE user_id=?"))
    c = st.columns(3); c[0].metric("Open tasks", n("SELECT COUNT(*) n FROM tasks WHERE user_id=? AND done=0")); c[1].metric("Completed tasks", n("SELECT COUNT(*) n FROM tasks WHERE user_id=? AND done=1")); c[2].metric("Conversations", n("SELECT COUNT(*) n FROM conversations WHERE user_id=?"))
    a, b = st.columns(2)
    with a:
        st.markdown("**Matters by status**")
        if ms: st.bar_chart(pd.Series([m["status"] for m in ms]).value_counts())
        else: st.caption("No data yet.")
    with b:
        st.markdown("**Document findings by category**")
        f = q("SELECT f.category FROM findings f JOIN documents d ON d.id=f.document_id WHERE d.user_id=? AND f.kind='clause'", (i,))
        if f: st.bar_chart(pd.Series([x["category"] for x in f]).value_counts())
        else: st.caption("No analysed documents yet.")
    if ms and st.button("Open my cases"): ui.go("cases")
    st.divider(); st.subheader("Retrieval evaluation (AI search quality)")
    st.caption("Computed live on a small hand-written question set against the bundled sources. See the README for why these numbers must not be generalised.")
    k = st.slider("K", 1, 5, 3); mode = st.radio("Method", ["combined", "keyword", "vector"], horizontal=True)
    if st.button("Run evaluation"):
        rows, mean = retrieval.evaluate(ui.index(), ingest.eval_questions(), k, mode)
        m = st.columns(3); [m[j].metric(name, f"{val:.2f}") for j, (name, val) in enumerate(mean.items())]
        st.dataframe(pd.DataFrame(rows))
