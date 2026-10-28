import csv, io, json
from datetime import date
import config
from database import db, q, one
from services.retrieval import chunk_text

REQUIRED = ["title", "act", "domain", "text"]
OPTIONAL = ["section", "doc_type", "source_name", "url", "verification_status", "version", "retrieved_on", "effective_info"]


def _rebuild_chunks(conn, source_id, text):
    conn.execute("DELETE FROM legal_chunks WHERE source_id=?", (source_id,))
    for i, c in enumerate(chunk_text(text)):
        conn.execute("INSERT INTO legal_chunks(source_id,idx,text) VALUES(?,?,?)", (source_id, i, c))


def upsert_source(conn, row, note="import"):
    """Insert or update (act, section, version). Snapshots the previous text into source_versions."""
    r = {k: (row.get(k) or "").strip() for k in REQUIRED + OPTIONAL}
    r["version"] = r["version"] or "1"
    r["verification_status"] = r["verification_status"] if r["verification_status"] in ("unverified", "verified", "outdated") else "unverified"
    r["doc_type"] = r["doc_type"] or "Statute"
    r["retrieved_on"] = r["retrieved_on"] or date.today().isoformat()
    cur = conn.execute("SELECT * FROM legal_sources WHERE act=? AND section=? AND version=?", (r["act"], r["section"], r["version"])).fetchone()
    if cur:
        conn.execute("INSERT INTO source_versions(source_id,version,text,verification_status,note) VALUES(?,?,?,?,?)",
                     (cur["id"], cur["version"], cur["text"], cur["verification_status"], note))
        conn.execute("""UPDATE legal_sources SET title=?,domain=?,doc_type=?,source_name=?,url=?,text=?,
                        verification_status=?,retrieved_on=?,effective_info=? WHERE id=?""",
                     (r["title"], r["domain"], r["doc_type"], r["source_name"], r["url"], r["text"],
                      r["verification_status"], r["retrieved_on"], r["effective_info"], cur["id"]))
        sid = cur["id"]
    else:
        sid = conn.execute("""INSERT INTO legal_sources(title,act,section,domain,doc_type,source_name,url,text,
                              verification_status,version,retrieved_on,effective_info) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                           (r["title"], r["act"], r["section"], r["domain"], r["doc_type"], r["source_name"], r["url"],
                            r["text"], r["verification_status"], r["version"], r["retrieved_on"], r["effective_info"])).lastrowid
    _rebuild_chunks(conn, sid, r["text"])
    return sid


def import_csv(data: bytes, user_id=None, filename="upload.csv"):
    """Validate every row; good rows are imported in one transaction, bad rows reported. Job is recorded."""
    ok, bad, errors = 0, 0, []
    try:
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError("Missing required columns: " + ", ".join(missing))
        with db() as conn:
            for n, row in enumerate(reader, start=2):
                if not all((row.get(c) or "").strip() for c in REQUIRED):
                    bad += 1; errors.append(f"Row {n}: required field empty"); continue
                upsert_source(conn, row); ok += 1
        status = "completed" if bad == 0 else "completed_with_errors"
    except Exception as e:
        status, errors = "failed", errors + [str(e)[:200]]
    with db() as conn:
        conn.execute("INSERT INTO ingestion_jobs(user_id,filename,status,rows_ok,rows_failed,error) VALUES(?,?,?,?,?,?)",
                     (user_id, filename, status, ok, bad, "; ".join(errors)[:1000]))
    return {"status": status, "ok": ok, "failed": bad, "errors": errors}


def bootstrap_sources():
    if one("SELECT COUNT(*) n FROM legal_sources")["n"] == 0:
        p = config.BASE_DIR / "data" / "legal_sources.csv"
        if p.exists():
            import_csv(p.read_bytes(), None, p.name)


def load_chunks():
    return q("""SELECT c.id, c.source_id, c.text, s.title, s.act, s.section, s.domain, s.doc_type, s.source_name,
                s.verification_status FROM legal_chunks c JOIN legal_sources s ON s.id=c.source_id""")


def chunks_version():
    r = one("SELECT COUNT(*) n, COALESCE(MAX(id),0) m FROM legal_chunks")
    return f"{r['n']}-{r['m']}"


def eval_questions():
    return json.loads((config.BASE_DIR / "data" / "eval_questions.json").read_text(encoding="utf-8"))
