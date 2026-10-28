import re, streamlit as st
from database import q
from services.retrieval import tokenize
import ui

def esc(s): return re.sub(r'["\\]', "", s)

def page():
    ui.header("Knowledge graph", "Domain → Act → Provision. Solid edges come from stored metadata. Dashed edges are INFERRED from shared vocabulary.")
    srcs = q("SELECT * FROM legal_sources")
    doms = sorted({s["domain"] for s in srcs})
    pick = st.multiselect("Domains", doms, default=doms[:3])
    infer = st.checkbox("Show inferred related-provision links", value=True)
    srcs = [s for s in srcs if s["domain"] in pick]
    if not srcs: st.info("Select at least one domain."); return
    dot = ["digraph G { rankdir=LR; node [fontname=Helvetica,fontsize=10]; edge [fontsize=8];"]
    for d in pick: dot.append(f'"D:{esc(d)}" [label="{esc(d)}",shape=box,style=filled,fillcolor="#0B1F3A",fontcolor=white];')
    for a in sorted({(s["act"], s["domain"]) for s in srcs}):
        dot.append(f'"A:{esc(a[0])}" [label="{esc(a[0])}",shape=box,style=filled,fillcolor="#EFE9D8"]; "D:{esc(a[1])}" -> "A:{esc(a[0])}";')
    for s in srcs:
        col = {"verified": "#2e8b57", "unverified": "#d9a441", "outdated": "#c0392b"}[s["verification_status"]]
        dot.append(f'"S:{s["id"]}" [label="{esc(s["section"])}",shape=ellipse,style=filled,fillcolor="{col}"]; "A:{esc(s["act"])}" -> "S:{s["id"]}";')
    rel = []
    if infer:
        toks = {s["id"]: set(tokenize(s["text"])) for s in srcs}
        for x in srcs:
            for y in srcs:
                if x["id"] < y["id"] and x["act"] != y["act"]:
                    sh = toks[x["id"]] & toks[y["id"]]; j = len(sh) / max(1, len(toks[x["id"]] | toks[y["id"]]))
                    if j >= 0.12:
                        dot.append(f'"S:{x["id"]}" -> "S:{y["id"]}" [style=dashed,dir=none,color=gray,label="inferred"];'); rel.append((x, y, round(j, 2), sorted(sh)[:6]))
    dot.append("}")
    st.graphviz_chart("\n".join(dot))
    st.caption("Node colour: green = verified, amber = unverified, red = outdated. Inferred links use Jaccard overlap of stemmed words and are NOT legal cross-references.")
    if rel:
        with st.expander("Inferred links (evidence)"):
            for x, y, j, sh in rel: st.write(f"{x['act']} {x['section']} ↔ {y['act']} {y['section']} - overlap {j}, shared terms: {', '.join(sh)}")
    ui.footer()
