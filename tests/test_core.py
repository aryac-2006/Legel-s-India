"""Run with:  python -m unittest discover -s tests -v   (or pytest)"""
import os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

_tmp = tempfile.mkdtemp()
config.DATA_DIR = Path(_tmp); config.UPLOAD_DIR = Path(_tmp) / "uploads"; config.DB_PATH = str(Path(_tmp) / "t.db")

import auth, database, security
from database import q, one, ex, owned, init_db
from services import ingest, retrieval, llm, documents, diffing, exports, drafting


def setUpModule():
    init_db(); ingest.bootstrap_sources()


class AuthTests(unittest.TestCase):
    def test_register_login_and_hashing(self):
        self.assertTrue(auth.register("a@x.com", "A", "password1")[0])
        u, _ = auth.login("a@x.com", "password1"); self.assertEqual(u["role"], "user")
        self.assertNotIn("password1", one("SELECT password_hash h FROM users WHERE email='a@x.com'")["h"])
        self.assertIsNone(auth.login("a@x.com", "bad")[0])

    def test_validation_and_no_admin_via_registration(self):
        self.assertFalse(auth.register("bad", "A", "password1")[0])
        self.assertFalse(auth.register("b@x.com", "B", "short")[0])
        auth.register("c@x.com", "C", "password1"); self.assertEqual(one("SELECT role FROM users WHERE email='c@x.com'")["role"], "user")
        self.assertFalse(auth.register("c@x.com", "C", "password1")[0])

    def test_lockout(self):
        auth.register("d@x.com", "D", "password1")
        for _ in range(config.MAX_LOGIN_ATTEMPTS): auth.login("d@x.com", "wrong")
        u, msg = auth.login("d@x.com", "password1"); self.assertIsNone(u); self.assertIn("Too many", msg)


class OwnershipTests(unittest.TestCase):
    def test_cross_user_access_blocked(self):
        auth.register("o1@x.com", "O1", "password1"); auth.register("o2@x.com", "O2", "password1")
        a = one("SELECT id FROM users WHERE email='o1@x.com'")["id"]; b = one("SELECT id FROM users WHERE email='o2@x.com'")["id"]
        mid = ex("INSERT INTO matters(user_id,title,category) VALUES(?,?,?)", (a, "private", "Other"))
        did = ex("INSERT INTO documents(user_id,filename,stored_path,sha256,size) VALUES(?,?,?,?,?)", (a, "f.pdf", "/x", "h", 1))
        self.assertIsNotNone(owned("matters", mid, a)); self.assertIsNone(owned("matters", mid, b))
        self.assertIsNone(owned("documents", did, b))
        with self.assertRaises(ValueError): owned("users", a, a)

    def test_cascade_delete_and_persistence(self):
        auth.register("p@x.com", "P", "password1"); p = one("SELECT id FROM users WHERE email='p@x.com'")["id"]
        mid = ex("INSERT INTO matters(user_id,title,category) VALUES(?,?,?)", (p, "m", "Other"))
        ex("INSERT INTO matter_notes(matter_id,user_id,body) VALUES(?,?,?)", (mid, p, "note"))
        self.assertEqual(len(q("SELECT * FROM matter_notes WHERE matter_id=?", (mid,))), 1)   # persisted, new connection
        ex("DELETE FROM matters WHERE id=?", (mid,)); self.assertEqual(q("SELECT * FROM matter_notes WHERE matter_id=?", (mid,)), [])


class UploadTests(unittest.TestCase):
    def test_invalid_uploads(self):
        self.assertFalse(security.validate_upload("a.exe", b"MZ")[0])
        self.assertFalse(security.validate_upload("a.pdf", b"")[0])
        self.assertFalse(security.validate_upload("a.pdf", b"not a pdf")[0])
        self.assertFalse(security.validate_upload("a.pdf", b"%PDF" + b"0" * (config.MAX_UPLOAD_MB * 1024 * 1024))[0])
        self.assertTrue(security.validate_upload("a.pdf", b"%PDF-1.4 x")[0])

    def test_path_traversal(self):
        self.assertEqual(security.safe_filename("../../etc/passwd"), "passwd")
        p = security.store_file(1, "../../evil.pdf", b"%PDF-1.4"); self.assertTrue(p.startswith(str(config.UPLOAD_DIR.resolve())))


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.index = retrieval.Index(ingest.load_chunks())

    def test_expected_source_found(self):
        hits = self.index.search("how do I file a consumer complaint", k=3)
        self.assertIn("Section 35", [h["section"] for h in hits])

    def test_section_search(self):
        self.assertEqual(self.index.search("section 66C", k=1)[0]["section"], "Section 66C")

    def test_filters(self):
        hits = self.index.search("compensation", k=10, filters={"domain": ["Cyber law"]})
        self.assertTrue(hits and all(h["domain"] == "Cyber law" for h in hits))

    def test_insufficient_evidence(self):
        h = self.index.search("zebra quantum helicopter", k=3); self.assertFalse(retrieval.is_sufficient("zebra quantum helicopter", h))
        a = llm.build_answer("zebra quantum helicopter", h, llm.ExtractiveProvider(), sufficient=False)
        self.assertEqual(a["status"], "insufficient"); self.assertEqual(a["citations"], [])

    def test_metrics(self):
        self.assertEqual(retrieval.reciprocal_rank(["a", "b"], {"b"}), 0.5)
        self.assertEqual(retrieval.precision_at_k(["a", "b"], {"b"}, 2), 0.5)
        self.assertEqual(retrieval.recall_at_k(["a"], {"a", "z"}, 3), 0.5)

    def test_chunk_overlap(self):
        c = retrieval.chunk_text(" ".join(str(i) for i in range(100)), size=40, overlap=10)
        self.assertEqual(c[0].split()[-10:], c[1].split()[:10])


class CitationTests(unittest.TestCase):
    def test_fake_citations_removed(self):
        passages = [{"ref": "S1"}, {"ref": "S2"}]
        good, bad = llm.validate_citations(["S1", "S9", "Section 420"], passages)
        self.assertEqual(good, ["S1"]); self.assertEqual(bad, ["S9", "Section 420"])

    def test_provider_with_only_fake_citations_is_discarded(self):
        class Fake:
            label = "fake"; external = True
            def generate(self, *a, **k): return {"short_answer": "x", "cited": ["S99"], "explanation": []}
        hits = retrieval.Index(ingest.load_chunks()).search("consumer complaint", k=2)
        a = llm.build_answer("consumer complaint", hits, Fake())
        self.assertTrue(a["citations"]); self.assertTrue(all(c["ref"] in {"S1", "S2"} for c in a["citations"]))
        self.assertTrue(any("no valid citations" in n for n in a["notes"]))


class IngestTests(unittest.TestCase):
    def test_bad_csv_rows_and_columns(self):
        r = ingest.import_csv(b"title,act\nx,y\n", None, "bad.csv"); self.assertEqual(r["status"], "failed")
        r = ingest.import_csv(b"title,act,domain,text\nT,Act X,Consumer protection,Some text\n,Act Y,Cyber law,\n", None, "m.csv")
        self.assertEqual((r["ok"], r["failed"]), (1, 1))
        self.assertTrue(one("SELECT * FROM ingestion_jobs ORDER BY id DESC")["rows_failed"] == 1)

    def test_version_snapshot_on_update(self):
        ingest.import_csv(b"title,act,section,domain,text\nT,Act V,S1,Cyber law,old text\n", None, "v.csv")
        ingest.import_csv(b"title,act,section,domain,text\nT,Act V,S1,Cyber law,new text\n", None, "v.csv")
        sid = one("SELECT id FROM legal_sources WHERE act='Act V'")["id"]
        self.assertEqual(q("SELECT text FROM source_versions WHERE source_id=?", (sid,))[0]["text"], "old text")


class DocumentTests(unittest.TestCase):
    TEXT = ("This Agreement is made between Asha Rao and Beta Pvt Ltd on 5 March 2025.\n\nEither party may terminate this agreement at its sole discretion.\n\n"
            "Payment of Rs. 50,000 shall be made monthly. Disputes shall be subject to arbitration at Pune.")

    def test_docx_roundtrip_and_analysis(self):
        pages, err = documents.extract_text("a.docx", exports.make_docx("T", self.TEXT)); self.assertIsNone(err)
        r = documents.analyze(pages); cats = {f["category"] for f in r["findings"]}
        self.assertTrue({"Termination", "Payment", "Dispute resolution", "Potential concern"} <= cats)
        self.assertTrue(all(f["passage"] for f in r["findings"]))
        self.assertIn("Rs. 50,000", r["entities"]["amounts"])

    def test_empty_and_corrupt(self):
        self.assertIsNotNone(documents.extract_text("a.docx", b"PK\x03\x04junk")[1])
        self.assertIsNotNone(documents.extract_text("a.pdf", b"%PDF-1.4 broken")[1])

    def test_pdf_export_extract(self):
        pdf = exports.make_pdf("Title", "Hello legal world")
        if pdf:
            pages, err = documents.extract_text("a.pdf", pdf); self.assertIsNone(err); self.assertIn("legal", pages[0])


class DiffTests(unittest.TestCase):
    def test_detects_changes(self):
        c = diffing.compare("Same.\n\nPay Rs. 100 by 1 May 2025.\n\nWeekly cleaning schedule applies.", "Same.\n\nPay Rs. 200 by 1 May 2025.\n\nArbitration seat shall be Mumbai.")
        self.assertEqual(c["unchanged"], 1); self.assertEqual(len(c["modified"]), 1)
        self.assertEqual(c["facts"]["amounts"]["only_in_a"], ["Rs. 100"])
        self.assertTrue(diffing.compare("x", " x ")["identical"])

    def test_html_escaped(self):
        l, r = diffing.word_diff_html("<script>a</script>", "b"); self.assertNotIn("<script>", l)


class DraftTests(unittest.TestCase):
    def test_placeholders_not_invented(self):
        t = drafting.render("legal_notice", {"sender_name": "Asha"})
        self.assertIn("[PLACEHOLDER: Recipient name]", t); self.assertNotIn("None", t)
        self.assertIn("Recipient name", drafting.validate("legal_notice", {"sender_name": "Asha"}))

    def test_ics(self):
        self.assertIn("DTSTART;VALUE=DATE:20261101", exports.make_ics([{"id": 1, "title": "Hearing", "due_date": "2026-11-01"}]))


if __name__ == "__main__":
    unittest.main()
