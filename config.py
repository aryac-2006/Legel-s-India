"""Central configuration. Secrets come from Streamlit secrets or environment variables only."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "storage"))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = os.getenv("DB_PATH", str(DATA_DIR / "legal_s_india.db"))
MAX_UPLOAD_MB = 10
ALLOWED_EXT = (".pdf", ".docx")
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_SECONDS = 900
LANGUAGES = ["English", "Hindi", "Marathi"]


def secret(name: str, default: str = "") -> str:
    try:
        import streamlit as st
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.getenv(name, default)
