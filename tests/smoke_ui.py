"""Renders every page with a fake Streamlit (no browser) against a temp DB to catch runtime errors.
Run: python tests/smoke_ui.py   (uses a stub, so it only proves pages run without exceptions on read paths)"""
import sys, tempfile, datetime
from pathlib import Path
from unittest.mock import MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
tmp = Path(tempfile.mkdtemp()); config.DATA_DIR = tmp; config.UPLOAD_DIR = tmp / "uploads"; config.DB_PATH = str(tmp / "s.db")

class SS(dict):
    __getattr__ = dict.get
    def __setattr__(self, k, v): self[k] = v

st = MagicMock(); st.session_state = SS()
cnt = lambda n: n if isinstance(n, int) else len(n)
st.columns.side_effect = lambda n, *a, **k: [st for _ in range(cnt(n))]
st.tabs.side_effect = lambda labels, *a, **k: [st for _ in labels]
first = lambda label, options=(), *a, **k: (list(options)[k["index"]] if k.get("index") is not None and list(options) else (list(options)[0] if list(options) else None))
st.selectbox.side_effect = first; st.radio.side_effect = first
st.multiselect.side_effect = lambda *a, **k: k.get("default", [])
for n in ("button", "checkbox", "toggle", "form_submit_button"): getattr(st, n).return_value = False
for n in ("text_input", "text_area"): getattr(st, n).side_effect = lambda label, value="", *a, **k: value if isinstance(value, str) else ""
st.number_input.side_effect = lambda label, mn=0, *a, **k: mn
st.slider.side_effect = lambda label, mn=0, *a, **k: mn + 2
st.date_input.side_effect = lambda *a, **k: datetime.date.today()
st.file_uploader.return_value = None; st.chat_input.return_value = None
st.cache_resource = lambda f: f
sys.modules["streamlit"] = st

import database, auth, ui
database.init_db(); from services import ingest; ingest.bootstrap_sources()
auth.register("t@x.com", "Tester", "password1"); u, _ = auth.login("t@x.com", "password1")
st.session_state["user"] = u
mid = database.ex("INSERT INTO matters(user_id,title,category) VALUES(?,?,?)", (u["id"], "m", "Other"))
database.ex("INSERT INTO tasks(user_id,matter_id,title,due_date) VALUES(?,?,?,?)", (u["id"], mid, "t", datetime.date.today().isoformat()))
st.session_state["sel_matter"] = mid
auth.register("adm@x.com", "Adm", "password1"); database.ex("UPDATE users SET role='admin' WHERE email='adm@x.com'")
from views import (public, dashboard, assistant, research, graph, documents, compare, drafting, cases, evidence, calendar_view, helpprep, privacy, search, analytics, admin)
pages = {"home": public.home, "about": public.about, "signin": public.sign_in, "register": public.register, "pp": public.privacy_policy, "disc": public.disclaimer,
         "dashboard": dashboard.page, "assistant": assistant.page, "research": research.page, "graph": graph.page, "docs": documents.page, "compare": compare.page,
         "drafting": drafting.page, "cases": cases.page, "evidence": evidence.page, "calendar": calendar_view.page, "helpprep": helpprep.page,
         "privacy": privacy.page, "search": search.page, "analytics": analytics.page}
fail = 0
for name, fn in pages.items():
    try: fn(); print("ok  ", name)
    except Exception as e: fail += 1; import traceback; print("FAIL", name, type(e).__name__, e); traceback.print_exc(limit=3)
st.session_state["user"] = {**u, "role": "admin", "id": database.one("SELECT id FROM users WHERE email='adm@x.com'")["id"]}
try: admin.page(); print("ok   admin")
except Exception as e: fail += 1; import traceback; print("FAIL admin", e); traceback.print_exc(limit=3)
# non-admin must be refused
st.session_state["user"] = u; st.error.reset_mock(); admin.page(); assert st.error.called, "admin page must refuse normal users"

# ---- action flows (real DB, stubbed UI) ----
from services import exports
try:
    cid = database.ex("INSERT INTO conversations(user_id,title) VALUES(?,?)", (u["id"], "t"))
    assistant.ask(cid, "How do I file a consumer complaint?", "English"); assistant.ask(cid, "zebra quantum helicopter", "English")
    msgs = database.q("SELECT * FROM messages WHERE conversation_id=? AND role='assistant'", (cid,))
    for m in msgs: assistant.render(m)
    import json; ps = [json.loads(m["payload"])["status"] for m in msgs]; assert ps == ["ok", "insufficient"], ps
    assert database.q("SELECT * FROM retrieved_sources WHERE cited=1"), "citations not stored"
    body = "This Agreement is made between Asha Rao and Beta Pvt Ltd on 5 March 2025.\n\nEither party may terminate at its sole discretion.\n\nPayment of Rs. 50,000 monthly."
    documents.process("a.docx", exports.make_docx("T", body)); documents.process("b.docx", exports.make_docx("T", body.replace("50,000", "60,000")))
    docs = database.q("SELECT id FROM documents WHERE user_id=?", (u["id"],)); assert len(docs) == 2
    st.session_state["doc_id"] = docs[0]["id"]; documents.page()
    st.button.return_value = True; compare.page(); st.button.return_value = False; assert st.session_state.get("cmp"); compare.page()
    documents.process("bad.docx", b"PK\x03\x04junk"); assert database.one("SELECT status FROM documents WHERE filename='bad.docx'")["status"] == "failed"
    ev = database.q("SELECT * FROM findings"); assert ev
    print("ok   flows")
except Exception as e:
    fail += 1; import traceback; print("FAIL flows", e); traceback.print_exc(limit=4)
print("failures:", fail); sys.exit(1 if fail else 0)
