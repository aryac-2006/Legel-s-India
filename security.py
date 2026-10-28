import base64, hashlib, hmac, os, re, time
import config

MAGIC = {".pdf": b"%PDF", ".docx": b"PK\x03\x04"}


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, s, h = stored.split("$")
        dk = hashlib.scrypt(pw.encode(), salt=base64.b64decode(s), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(dk, base64.b64decode(h))
    except Exception:
        return False


def safe_filename(name: str) -> str:
    """Strip any directory part (path traversal) and unsafe characters."""
    base = os.path.basename(name.replace("\\", "/"))
    base = re.sub(r"[^A-Za-z0-9._ -]", "_", base).strip(" .")
    return base[:100] or "file"


def validate_upload(name: str, data: bytes):
    """Returns (ok, message). Checks extension, size, emptiness and magic bytes."""
    ext = os.path.splitext(name.lower())[1]
    if ext not in config.ALLOWED_EXT:
        return False, "Only PDF and DOCX files are supported."
    if not data:
        return False, "The file is empty."
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        return False, f"File exceeds the {config.MAX_UPLOAD_MB} MB limit."
    if not data.startswith(MAGIC[ext]):
        return False, "File content does not match its extension."
    return True, "ok"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def store_file(user_id: int, name: str, data: bytes) -> str:
    """Store under uploads/<user_id>/<sha>_<safe name>; the path is built server-side only."""
    d = config.UPLOAD_DIR / str(int(user_id))
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{sha256(data)[:16]}_{safe_filename(name)}"
    resolved = path.resolve()
    if config.UPLOAD_DIR.resolve() not in resolved.parents:
        raise ValueError("invalid storage path")
    resolved.write_bytes(data)
    return str(resolved)


def delete_file(path: str):
    try:
        p = os.path.realpath(path)
        if str(config.UPLOAD_DIR.resolve()) in p and os.path.exists(p):
            os.remove(p)
    except OSError:
        pass
