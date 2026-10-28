import re, time
import config
from database import q, one, ex, audit
from security import hash_password, verify_password

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def register(email, name, password):
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        return False, "Enter a valid email address."
    if not (name or "").strip():
        return False, "Name is required."
    if len(password or "") < 8:
        return False, "Password must be at least 8 characters."
    if one("SELECT id FROM users WHERE email=?", (email,)):
        return False, "An account with this email already exists."
    # Role is never read from user input. Everyone registers as an ordinary user.
    uid = ex("INSERT INTO users(email,name,password_hash,role) VALUES(?,?,?,'user')",
             (email, name.strip(), hash_password(password)))
    audit(uid, "register")
    return True, "Account created. You can sign in now."


def login(email, password):
    """Returns (user_dict|None, message). Rate limited per email; generic failure message."""
    email = (email or "").strip().lower()
    cutoff = time.time() - config.LOCKOUT_SECONDS
    fails = one("SELECT COUNT(*) n FROM login_attempts WHERE email=? AND ok=0 AND ts>?", (email, cutoff))["n"]
    if fails >= config.MAX_LOGIN_ATTEMPTS:
        audit(None, "login_locked", email)
        return None, "Too many failed attempts. Try again in 15 minutes."
    u = one("SELECT * FROM users WHERE email=?", (email,))
    ok = bool(u and u["is_active"] and verify_password(password or "", u["password_hash"]))
    ex("INSERT INTO login_attempts(email,ok,ts) VALUES(?,?,?)", (email, int(ok), time.time()))
    audit(u["id"] if u else None, "login_success" if ok else "login_failed", "" if ok else email)
    if not ok:
        return None, "Invalid credentials or inactive account."
    return {"id": u["id"], "name": u["name"], "email": u["email"], "role": u["role"],
            "language": u["language"]}, "ok"


def bootstrap_admin():
    """Create the first admin from ADMIN_EMAIL / ADMIN_PASSWORD (secrets or env) if none exists."""
    if one("SELECT id FROM users WHERE role='admin'"):
        return
    email, pw = config.secret("ADMIN_EMAIL"), config.secret("ADMIN_PASSWORD")
    if email and len(pw) >= 8:
        uid = ex("INSERT INTO users(email,name,password_hash,role) VALUES(?,?,?,'admin')",
                 (email.lower(), "Administrator", hash_password(pw)))
        audit(uid, "bootstrap_admin")


def is_admin(user):
    return bool(user) and user.get("role") == "admin"
