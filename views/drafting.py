import json, streamlit as st
from database import q, one, ex, owned, audit
from services import drafting as DR, diffing, exports
import ui

def page():
    ui.header("Drafting studio", "Structured drafts with placeholders for anything you have not supplied.")
    i = ui.uid(); st.warning(DR.REVIEW_NOTICE)
    t1, t2 = st.tabs(["New draft", "My drafts & versions"])
    with t1:
        key = st.selectbox("Template", list(DR.T), format_func=lambda k: DR.T[k]["title"])
        spec = DR.T[key]; vals = {}
        with st.form(f"f_{key}"):
            for k, label, kind, req in spec["fields"]:
                vals[k] = (st.text_area if kind == "area" else st.text_input)(label + (" *" if req else ""), key=f"{key}_{k}")
            go = st.form_submit_button("Review facts")
        if go:
            miss = DR.validate(key, vals)
            if miss: st.error("Required: " + ", ".join(miss))
            else: st.session_state["draft_ctx"] = (key, vals, DR.render(key, vals))
        if st.session_state.get("draft_ctx") and st.session_state["draft_ctx"][0] == key:
            _, v, text = st.session_state["draft_ctx"]
            st.subheader("Review"); st.table([{"Field": l, "Value": v.get(k) or "(placeholder)"} for k, l, _, _ in spec["fields"]])
            body = st.text_area("Edit the draft", text, height=420)
            st.caption(f"{len(DR.placeholders(body))} placeholder(s) remain.")
            title = st.text_input("Title", spec["title"]); mid = ui.matter_picker("Associate with matter", key="dmatter")
            if st.button("Save draft") and title.strip():
                if mid and not owned("matters", mid, i): st.error("Invalid matter."); return
                did = ex("INSERT INTO drafts(user_id,matter_id,template,title) VALUES(?,?,?,?)", (i, mid, key, title.strip()))
                ex("INSERT INTO draft_versions(draft_id,version,content,fields,note) VALUES(?,?,?,?,?)", (did, 1, body, json.dumps(v), "initial")); audit(i, "draft_save", did); st.success("Saved as version 1.")
    with t2:
        ds = q("SELECT * FROM drafts WHERE user_id=? ORDER BY id DESC", (i,))
        if not ds: st.info("No drafts yet."); return
        d = owned("drafts", st.selectbox("Draft", [x["id"] for x in ds], format_func=lambda x: next(y["title"] for y in ds if y["id"] == x)), i)
        vs = q("SELECT * FROM draft_versions WHERE draft_id=? ORDER BY version DESC", (d["id"],)); latest = vs[0]
        st.caption(f"Template: {DR.T[d['template']]['title']} | {len(vs)} version(s)")
        body = st.text_area("Content (latest version)", latest["content"], height=360, key=f"ed{d['id']}_{latest['version']}")
        note = st.text_input("Version note", key="vnote")
        c = st.columns(5)
        if c[0].button("Save new version"):
            ex("INSERT INTO draft_versions(draft_id,version,content,fields,note) VALUES(?,?,?,?,?)", (d["id"], latest["version"] + 1, body, latest["fields"], note)); st.rerun()
        c[1].download_button("TXT", body, file_name="draft.txt"); c[2].download_button("DOCX", exports.make_docx(d["title"], body), file_name="draft.docx")
        pdf = exports.make_pdf(d["title"], body)
        if pdf: c[3].download_button("PDF", pdf, file_name="draft.pdf")
        else: c[3].caption("PDF export unavailable (install reportlab)")
        if c[4].button("Delete draft"): ex("DELETE FROM drafts WHERE id=? AND user_id=?", (d["id"], i)); st.rerun()
        mid = ui.matter_picker("Matter", key="dm2")
        if mid and st.button("Link to matter") and owned("matters", mid, i): ex("UPDATE drafts SET matter_id=? WHERE id=? AND user_id=?", (mid, d["id"], i)); ex("INSERT OR IGNORE INTO matter_links(matter_id,user_id,kind,ref_id,label) VALUES(?,?,?,?,?)", (mid, i, "draft", d["id"], d["title"])); st.success("Linked")
        st.subheader("Versions")
        for v in vs:
            with st.expander(f"v{v['version']} - {v['created_at'][:16]} {v['note']}"):
                if v["version"] != latest["version"]:
                    l, r = diffing.word_diff_html(v["content"], latest["content"]); st.markdown("Changes from this version to latest:"); st.markdown(r.replace("\n", "<br>"), unsafe_allow_html=True)
                    if st.button("Restore as new version", key=f"rest{v['id']}"): ex("INSERT INTO draft_versions(draft_id,version,content,fields,note) VALUES(?,?,?,?,?)", (d["id"], latest["version"] + 1, v["content"], v["fields"], f"restored v{v['version']}")); st.rerun()
                else: st.write("Current version")
    ui.footer()
