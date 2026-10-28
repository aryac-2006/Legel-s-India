import json, streamlit as st
from database import q, one, ex, owned, audit
from services import diffing
import ui

def citation(s):
    return f"{s['act']}, {s['section']} ({s['title']}). Source: {s['source_name'] or 'n/a'}, {s['url'] or 'n/a'}. Version {s['version']}, retrieved {s['retrieved_on']}. Status: {s['verification_status']}."

def page():
    ui.header("Legal research", "Search by topic, Act, section or keyword.")
    i = ui.uid()
    t1, t2, t3, t4 = st.tabs(["Search", "Compare provisions", "Collections & saved searches", "Source versions"])
    opts = lambda col: [r[col] for r in q(f"SELECT DISTINCT {col} FROM legal_sources WHERE {col}!='' ORDER BY {col}")]
    with t1:
        qry = st.text_input("Search", value=st.session_state.pop("saved_q", ""), placeholder="topic, Act name, 'section 66C', keyword")
        mode = st.radio("Method", ["combined", "keyword", "vector"], horizontal=True, help="keyword = BM25; vector = TF-IDF cosine (lexical, not neural); combined = Reciprocal Rank Fusion")
        c = st.columns(4)
        f = {"domain": c[0].multiselect("Domain", opts("domain")), "doc_type": c[1].multiselect("Type", opts("doc_type")),
             "source_name": c[2].multiselect("Source", opts("source_name")), "verification_status": c[3].multiselect("Verification", ["verified", "unverified", "outdated"])}
        if qry:
            hits = ui.index().search(qry, k=15, mode=mode, filters={k: v for k, v in f.items() if v})
            seen, res = set(), []
            for h in hits:
                if h["source_id"] not in seen: seen.add(h["source_id"]); res.append(h)
            st.write(f"{len(res)} result(s). Scores rank results only; they are not legal confidence.")
            cols = [r["id"] for r in q("SELECT id FROM collections WHERE user_id=?", (i,))]
            for h in res:
                s = one("SELECT * FROM legal_sources WHERE id=?", (h["source_id"],))
                with st.expander(f"{s['act']}, {s['section']} - {s['title']}  (score {h['score']})"):
                    ui.source_card(s); st.caption("Matched terms: " + ", ".join(h["matched"] + h["matched_expanded"]))
                    cc = st.columns(3)
                    if cc[0].button("Save", key=f"sv{s['id']}"):
                        ex("INSERT OR IGNORE INTO saved_research(user_id,source_id) VALUES(?,?)", (i, s["id"])); st.success("Saved")
                    if cc[1].button("Save search", key=f"ss{s['id']}"):
                        ex("INSERT INTO saved_searches(user_id,query,filters) VALUES(?,?,?)", (i, qry, json.dumps(f))); st.success("Search saved")
                    cc[2].download_button("Citation", citation(s), file_name="citation.txt", key=f"ci{s['id']}")
                    st.caption("Related: " + ", ".join(f"{r['act']} {r['section']}" for r in q("SELECT act,section FROM legal_sources WHERE domain=? AND id!=? LIMIT 3", (s["domain"], s["id"]))))
            if not res: st.info("No matching sources. Try different words, or ask an admin to import more material.")
    with t2:
        srcs = q("SELECT id, act, section, text FROM legal_sources ORDER BY act, section")
        names = {s["id"]: f"{s['act']}, {s['section']}" for s in srcs}
        pair = st.multiselect("Choose exactly two provisions", list(names), format_func=lambda x: names[x], max_selections=2)
        if len(pair) == 2:
            a, b = [next(s for s in srcs if s["id"] == p) for p in pair]
            l, r = diffing.word_diff_html(a["text"], b["text"])
            c1, c2 = st.columns(2); c1.markdown(f"**{names[a['id']]}**"); c1.markdown(l, unsafe_allow_html=True); c2.markdown(f"**{names[b['id']]}**"); c2.markdown(r, unsafe_allow_html=True)
            st.caption("Word-level text difference of the stored source text. Highlighting shows wording differences, not legal differences.")
    with t3:
        n = st.text_input("New collection name")
        if st.button("Create collection") and n.strip():
            ex("INSERT OR IGNORE INTO collections(user_id,name) VALUES(?,?)", (i, n.strip()))
        cols = q("SELECT * FROM collections WHERE user_id=?", (i,))
        for col in cols + [{"id": None, "name": "Uncategorised"}]:
            items = q("SELECT r.id rid, s.* FROM saved_research r JOIN legal_sources s ON s.id=r.source_id WHERE r.user_id=? AND r.collection_id IS ?" if col["id"] is None else
                      "SELECT r.id rid, s.* FROM saved_research r JOIN legal_sources s ON s.id=r.source_id WHERE r.user_id=? AND r.collection_id=?", (i, col["id"]))
            if items:
                st.markdown(f"**{col['name']}**")
                for s in items:
                    c = st.columns([5, 3, 1])
                    c[0].write(f"{s['act']}, {s['section']}")
                    tgt = c[1].selectbox("Move to", [None] + [x["id"] for x in cols], format_func=lambda x: "—" if x is None else next(y["name"] for y in cols if y["id"] == x), key=f"mv{s['rid']}")
                    if tgt and tgt != col["id"]: ex("UPDATE saved_research SET collection_id=? WHERE id=? AND user_id=?", (tgt, s["rid"], i)); st.rerun()
                    if c[2].button("✕", key=f"rm{s['rid']}"): ex("DELETE FROM saved_research WHERE id=? AND user_id=?", (s["rid"], i)); st.rerun()
        st.markdown("**Saved searches**")
        for sv in q("SELECT * FROM saved_searches WHERE user_id=? ORDER BY id DESC", (i,)):
            c = st.columns([5, 1, 1]); c[0].write(sv["query"])
            if c[1].button("Run", key=f"rs{sv['id']}"): st.session_state["saved_q"] = sv["query"]; st.rerun()
            if c[2].button("✕", key=f"ds{sv['id']}"): ex("DELETE FROM saved_searches WHERE id=? AND user_id=?", (sv["id"], i)); st.rerun()
        allc = q("SELECT s.* FROM saved_research r JOIN legal_sources s ON s.id=r.source_id WHERE r.user_id=?", (i,))
        if allc: st.download_button("Export citations of saved research", "\n\n".join(citation(s) for s in allc), file_name="saved_citations.txt")
    with t4:
        srcs = q("SELECT id, act, section, version FROM legal_sources ORDER BY act, section")
        sid = st.selectbox("Source", [s["id"] for s in srcs], format_func=lambda x: next(f"{s['act']}, {s['section']} (v{s['version']})" for s in srcs if s["id"] == x))
        cur = one("SELECT * FROM legal_sources WHERE id=?", (sid,))
        st.write(f"Current: version {cur['version']}, status {cur['verification_status']}, retrieved {cur['retrieved_on']}")
        for v in q("SELECT * FROM source_versions WHERE source_id=? ORDER BY id DESC", (sid,)):
            with st.expander(f"Earlier snapshot - {v['changed_at']} ({v['note']})"):
                l, r = diffing.word_diff_html(v["text"], cur["text"]); st.markdown(l, unsafe_allow_html=True); st.markdown("**Now:**"); st.markdown(r, unsafe_allow_html=True)
        if not q("SELECT id FROM source_versions WHERE source_id=?", (sid,)): st.caption("No earlier versions recorded.")
    ui.footer()
