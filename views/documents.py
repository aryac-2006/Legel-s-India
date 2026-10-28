import json, streamlit as st
from database import q, one, ex, db, owned, audit, log_error
from services import documents as D, exports
import security, ui

REVIEW = ["Unreviewed", "Reviewed", "Needs Attention", "Not Applicable"]

def process(name, data):
    i = ui.uid(); ok, msg = security.validate_upload(name, data)
    if not ok: st.error(msg); return
    path = security.store_file(i, name, data)
    did = ex("INSERT INTO documents(user_id,filename,stored_path,sha256,size,status) VALUES(?,?,?,?,?,'uploaded')", (i, security.safe_filename(name), path, security.sha256(data), len(data)))
    pages, err = D.extract_text(name, data)
    if err and not any(p.strip() for p in pages):
        ex("UPDATE documents SET status='failed', status_note=? WHERE id=?", (err, did)); st.error(err); return
    r = D.analyze(pages)
    with db() as c:
        c.execute("UPDATE documents SET text=?, pages=?, doc_type=?, summary=?, entities=?, status='analysed' WHERE id=?",
                  ("\n\n".join(pages), json.dumps(pages), r["doc_type"], r["summary"], json.dumps(r["entities"]), did))
        for f in r["findings"] + r["checklist"]:
            c.execute("INSERT INTO findings(document_id,kind,category,passage,explanation,page,reason,priority) VALUES(?,?,?,?,?,?,?,?)",
                      (did, f["kind"], f["category"], f["passage"], f["explanation"], f["page"], f["reason"], f["priority"]))
    audit(i, "document_upload", f"id={did}"); st.success("Uploaded and analysed."); st.session_state["doc_id"] = did

def report(d, finds):
    out = [f"DOCUMENT ANALYSIS REPORT: {d['filename']}", f"SHA-256: {d['sha256']}", "", d["summary"], "", "Entities (rule-based):", json.dumps(json.loads(d["entities"]), indent=1), ""]
    for f in finds: out += [f"[{f['priority']}] {f['category']} (page {f['page'] or 'n/a'}) - {f['review_status']}", f"  Passage: {f['passage']}", f"  Why: {f['reason']}", ""]
    out.append("Limitations: automatic, rule-based extraction. Not legal advice. A qualified advocate should review.")
    return "\n".join(out)

def page():
    ui.header("Document analyzer", "PDF and DOCX. Findings are extracted passages with rule-based explanations, not legal conclusions.")
    i = ui.uid()
    with st.expander("Upload a document", expanded=not q("SELECT id FROM documents WHERE user_id=?", (i,))):
        up = st.file_uploader("PDF or DOCX (max 10 MB)", type=["pdf", "docx"])
        st.caption("OCR for scanned files is not enabled. Uploaded text is treated as untrusted data and is never executed or used as instructions.")
        if up and st.button("Analyse"):
            try: process(up.name, up.getvalue())
            except Exception as e: log_error("upload", e); st.error("Processing failed safely. The error was logged.")
    docs = q("SELECT id, filename, status, created_at FROM documents WHERE user_id=? ORDER BY id DESC", (i,))
    if not docs: st.info("No documents yet."); return
    ids = [d["id"] for d in docs]; cur = st.session_state.get("doc_id")
    sel = st.selectbox("Document", ids, index=ids.index(cur) if cur in ids else 0, format_func=lambda x: next(f"{d['filename']} - {d['status']} ({d['created_at'][:10]})" for d in docs if d["id"] == x))
    d = owned("documents", sel, i)
    if not d: st.error("Not found."); return
    if d["status"] == "failed": st.error(d["status_note"]); 
    tabs = st.tabs(["Summary", "Findings", "Risk & compliance checklist", "Extracted text", "Report & delete"])
    ent = json.loads(d["entities"] or "{}")
    with tabs[0]:
        st.info(d["summary"])
        c = st.columns(3); c[0].markdown("**Possible parties**"); [c[0].write("• " + x) for x in ent.get("possible_parties", [])]
        c[1].markdown("**Dates**"); [c[1].write("• " + x) for x in ent.get("dates", [])]; c[2].markdown("**Amounts**"); [c[2].write("• " + x) for x in ent.get("amounts", [])]
        st.caption("Extracted by pattern matching: these are facts found in the text, not interpretations. Verify against the original.")
    def finding_list(kind, cat_filter=None):
        fs = q("SELECT * FROM findings WHERE document_id=? AND kind=? ORDER BY CASE priority WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END, id", (sel, kind))
        cats = sorted({f["category"] for f in fs}); pick = st.multiselect("Category", cats, key=f"cat{kind}") if cat_filter else []
        for f in fs:
            if pick and f["category"] not in pick: continue
            with st.expander(f"[{f['priority']}] {f['category']} - page {f['page'] or 'n/a'} - {f['review_status']}"):
                st.markdown("**Extracted passage (original text)**"); st.write(f["passage"] or "_Nothing found_")
                st.markdown("**Plain-language explanation (automatic)**"); st.write(D.SIMPLE_EXPLAIN.get(f["category"], f["explanation"]) if kind == "clause" else f["explanation"])
                st.markdown("**Reason for review**"); st.write(f["reason"]); st.caption(f"Verification: {f['verification']}. Limitation: pattern-based; may miss or misread wording. Preliminary, not an assessment by an advocate.")
                ns = st.selectbox("Review status", REVIEW, index=REVIEW.index(f["review_status"]), key=f"rv{f['id']}")
                if ns != f["review_status"]: ex("UPDATE findings SET review_status=? WHERE id=? AND document_id=?", (ns, f["id"], sel)); audit(i, "finding_review", f"{f['id']}={ns}"); st.rerun()
        return fs
    with tabs[1]: finding_list("clause", True)
    with tabs[2]:
        st.caption(f"Checklist for detected type: **{d['doc_type']}**. Missing items may simply be phrased differently. This is a preliminary review.")
        fs = finding_list("checklist")
        st.download_button("Export checklist", "\n".join(f"{f['category']} | {'found' if f['passage'] else 'NOT FOUND'} | {f['review_status']}" for f in fs), file_name="checklist.txt")
    with tabs[3]:
        st.text_area("Extracted text (review for errors)", d["text"], height=380, disabled=True)
    with tabs[4]:
        fs = q("SELECT * FROM findings WHERE document_id=?", (sel,)); rep = report(d, fs)
        c = st.columns(3); c[0].download_button("Report (.txt)", rep, file_name="analysis.txt"); c[1].download_button("Report (.docx)", exports.make_docx("Document analysis", rep), file_name="analysis.docx")
        pdf = exports.make_pdf("Document analysis", rep)
        if pdf: c[2].download_button("Report (.pdf)", pdf, file_name="analysis.pdf")
        mid = ui.matter_picker("Link analysis to matter", key="lnkdoc")
        if mid and st.button("Link to matter"): ex("INSERT OR IGNORE INTO matter_links(matter_id,user_id,kind,ref_id,label) VALUES(?,?,?,?,?)", (mid, i, "document", sel, d["filename"])); st.success("Linked")
        st.divider()
        if st.checkbox("I understand this permanently deletes the file and its analysis") and st.button("Delete document", type="primary"):
            security.delete_file(d["stored_path"]); ex("DELETE FROM documents WHERE id=? AND user_id=?", (sel, i)); audit(i, "document_delete", sel); st.session_state.pop("doc_id", None); st.rerun()
    ui.footer()
