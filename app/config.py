import os
import logging
root = logging.getLogger()


def _load_dotenv(path):
    root.debug(">>> Entering _load_dotenv(path=%s)", path)
    if not os.path.exists(path):
        root.debug("<<< Exiting _load_dotenv(path=%s)", path)
        return
    with open(path) as fh:
        root.error("Exception in _load_dotenv(path=%s)", path, exc_info=True)
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

APP_PORT = int(os.environ.get("APP_PORT", "8088"))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "app.log")
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "claims.db")
POLICY_PAYOUT_CEILING = float(os.environ.get("POLICY_PAYOUT_CEILING", "10000"))
AI_BASE_URL = os.environ.get("AI_BASE_URL", "").rstrip("/")
AI_API_KEY = os.environ.get("AI_API_KEY", "")
AI_MODEL = os.environ.get("AI_MODEL", "gpt-4o-mini")
