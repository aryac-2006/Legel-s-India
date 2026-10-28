"""Explainable retrieval: chunking, BM25 keyword search, TF-IDF cosine "vector" search,
and Reciprocal Rank Fusion (RRF) for combined retrieval.

NOTE: the vector mode is a lexical TF-IDF vector space, NOT a neural embedding model.
Scores are ranking signals only; they are never a probability of legal correctness."""
import math, re
from collections import Counter

STOP = set("a an the and or of to in on for with is are was were be been it its this that these those i me my we our you your "
           "can could should would will shall may might do does did have has had how what when where which who whom why "
           "about under as at by from if not no any there than then so such into over".split())


def stem(w):
    for suf in ("ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[:-len(suf)]
    return w


def tokenize(text):
    return [stem(w) for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in STOP and len(w) > 1]


_RAW_SYN = {
    "refund": ["price", "replace", "defective"], "faulty": ["defective", "deficiency"], "defect": ["defective"],
    "fired": ["retrenchment", "terminate"], "terminated": ["retrenchment", "notice"], "job": ["workman", "employee"],
    "employer": ["workman", "retrenchment"], "tenant": ["lease"], "rent": ["lease"], "tenancy": ["lease", "notice"],
    "landlord": ["lease"], "impersonate": ["personation", "identity"], "password": ["identity", "electronic"],
    "hacked": ["unauthorised", "computer"], "scam": ["cheating", "personation"], "fraud": ["cheating"],
    "divorce": ["marriage", "cruelty", "desertion"], "husband": ["domestic", "marriage"], "wife": ["domestic", "marriage"],
    "equality": ["equal"], "complaint": ["commission"], "consumer": ["commission"], "breach": ["compensation"],
    "damages": ["compensation"], "limit": ["limitation"], "deadline": ["limitation"], "time": ["limitation", "period"],
}
SYN = {stem(k): [stem(x) for x in v] for k, v in _RAW_SYN.items()}


def chunk_text(text, size=120, overlap=20):
    """Word-window chunking with configurable overlap."""
    words = (text or "").split()
    if not words:
        return []
    if size <= overlap:
        raise ValueError("size must exceed overlap")
    out, i = [], 0
    while i < len(words):
        out.append(" ".join(words[i:i + size]))
        if i + size >= len(words):
            break
        i += size - overlap
    return out


class Index:
    def __init__(self, chunks):
        """chunks: dicts with id, source_id, text, title, act, section, domain, doc_type, source_name, verification_status."""
        self.chunks = chunks
        self.toks = [tokenize(f"{c.get('title','')} {c.get('act','')} {c.get('section','')} {c['text']}") for c in chunks]
        self.tf = [Counter(t) for t in self.toks]
        n = len(chunks)
        df = Counter(w for t in self.tf for w in t)
        self.idf = {w: math.log(1 + (n - d + 0.5) / (d + 0.5)) for w, d in df.items()}
        self.avgdl = (sum(len(t) for t in self.toks) / n) if n else 1
        self.norm = [math.sqrt(sum((c * self.idf[w]) ** 2 for w, c in tf.items())) or 1.0 for tf in self.tf]

    def _bm25(self, qt, i, k1=1.5, b=0.75):
        tf, dl, s = self.tf[i], len(self.toks[i]), 0.0
        for w in qt:
            f = tf.get(w, 0)
            if f:
                s += self.idf.get(w, 0) * f * (k1 + 1) / (f + k1 * (1 - b + b * dl / self.avgdl))
        return s

    def _cos(self, qt, i):
        qtf = Counter(qt)
        qn = math.sqrt(sum((c * self.idf.get(w, 0)) ** 2 for w, c in qtf.items())) or 1.0
        dot = sum(c * self.idf.get(w, 0) * self.tf[i].get(w, 0) * self.idf.get(w, 0) for w, c in qtf.items())
        return dot / (qn * self.norm[i])

    def search(self, query, k=5, mode="combined", filters=None):
        filters = filters or {}
        orig = tokenize(query)
        exp = [x for t in orig for x in SYN.get(t, [])]
        qt = orig + exp
        sec = None
        m = re.search(r"(?:section|sec\.?|s\.?|article|art\.?)\s*([0-9]+[a-z]?(?:\([0-9a-z]+\))*)", query.lower())
        if m:
            sec = m.group(1)
        cand = []
        for i, c in enumerate(self.chunks):
            if any(filters.get(f) and c.get(f) not in filters[f] for f in ("domain", "doc_type", "source_name", "verification_status")):
                continue
            if filters.get("act") and filters["act"].lower() not in c["act"].lower():
                continue
            cand.append(i)
        rows = []
        for i in cand:
            matched_o = set(orig) & set(self.tf[i])
            matched_e = set(exp) & set(self.tf[i])
            sec_hit = bool(sec and c_section(self.chunks[i]) == sec)
            if not (matched_o or matched_e or sec_hit):
                continue
            rows.append({**self.chunks[i], "bm25": self._bm25(qt, i), "cosine": self._cos(qt, i),
                         "matched": sorted(matched_o), "matched_expanded": sorted(matched_e), "section_match": sec_hit})
        rb = {r["id"]: n for n, r in enumerate(sorted(rows, key=lambda r: -r["bm25"]))}
        rc = {r["id"]: n for n, r in enumerate(sorted(rows, key=lambda r: -r["cosine"]))}
        for r in rows:
            r["rrf"] = 1 / (60 + rb[r["id"]]) + 1 / (60 + rc[r["id"]]) + (1 if r["section_match"] else 0)
            r["strength"] = len(r["matched"]) + 0.5 * len(r["matched_expanded"]) + (3 if r["section_match"] else 0)
        key = {"keyword": "bm25", "vector": "cosine", "combined": "rrf"}[mode]
        rows.sort(key=lambda r: (-int(r["section_match"]), -r[key]))
        rows = rows[:k]
        for n, r in enumerate(rows, 1):
            r["rank"] = n
            r["score"] = round(r[key], 4)
        return rows


def c_section(chunk):
    m = re.search(r"([0-9]+[a-z]?(?:\([0-9a-z]+\))*)", (chunk.get("section") or "").lower())
    return m.group(1) if m else None


def is_sufficient(query, hits):
    """Heuristic evidence check: best hit must share enough query terms. Not a legal-confidence measure."""
    if not hits:
        return False
    n_orig = len(tokenize(query))
    need = 1.0 if n_orig <= 1 else 1.5
    return max(h["strength"] for h in hits) >= need


def precision_at_k(ids, relevant, k):
    top = ids[:k]
    return sum(1 for x in top if x in relevant) / k if k else 0.0


def recall_at_k(ids, relevant, k):
    return sum(1 for x in ids[:k] if x in relevant) / len(relevant) if relevant else 0.0


def reciprocal_rank(ids, relevant):
    for n, x in enumerate(ids, 1):
        if x in relevant:
            return 1 / n
    return 0.0


def evaluate(index, questions, k=3, mode="combined"):
    """questions: [{'q':..., 'relevant':['Act|Section', ...]}]. Returns per-question rows + means."""
    rows = []
    for item in questions:
        hits = index.search(item["q"], k=10, mode=mode)
        keys, seen = [], set()
        for h in hits:                       # de-duplicate chunks of the same source
            key = f"{h['act']}|{h['section']}"
            if key not in seen:
                seen.add(key); keys.append(key)
        rel = set(item["relevant"])
        rows.append({"question": item["q"], f"P@{k}": precision_at_k(keys, rel, k),
                     f"R@{k}": recall_at_k(keys, rel, k), "RR": reciprocal_rank(keys, rel)})
    n = len(rows) or 1
    return rows, {f"P@{k}": sum(r[f"P@{k}"] for r in rows) / n, f"R@{k}": sum(r[f"R@{k}"] for r in rows) / n,
                  "MRR": sum(r["RR"] for r in rows) / n}
