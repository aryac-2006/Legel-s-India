"""Optional demo data:  python seed.py   (creates demo@example.com / demo-password-1 with clearly labelled [DEMO] items)."""
from datetime import date, timedelta
import auth, database
from database import one, ex
from services import ingest

database.init_db(); ingest.bootstrap_sources(); auth.bootstrap_admin()
if not one("SELECT id FROM users WHERE email='demo@example.com'"):
    auth.register("demo@example.com", "Demo User", "demo-password-1")
u = one("SELECT id FROM users WHERE email='demo@example.com'")["id"]
if not one("SELECT id FROM matters WHERE user_id=? AND is_demo=1", (u,)):
    m1 = ex("INSERT INTO matters(user_id,title,category,status,description,is_demo) VALUES(?,?,?,?,?,1)", (u, "[DEMO] Defective phone refund", "Consumer", "Open", "Sample demonstration matter."))
    m2 = ex("INSERT INTO matters(user_id,title,category,status,description,is_demo) VALUES(?,?,?,?,?,1)", (u, "[DEMO] Rental deposit dispute", "Property", "In Progress", "Sample demonstration matter."))
    ex("INSERT INTO tasks(user_id,matter_id,title,kind,due_date,is_demo) VALUES(?,?,?,?,?,1)", (u, m1, "[DEMO] Send reminder to seller", "task", (date.today() + timedelta(days=5)).isoformat()))
    ex("INSERT INTO tasks(user_id,matter_id,title,kind,due_date,is_demo) VALUES(?,?,?,?,?,1)", (u, m2, "[DEMO] Collect rent receipts", "deadline", (date.today() + timedelta(days=12)).isoformat()))
    ex("INSERT INTO matter_notes(matter_id,user_id,body) VALUES(?,?,?)", (m1, u, "[DEMO] Seller promised replacement on the phone; asked for written confirmation."))
print("Seeded.")
