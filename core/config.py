"""Settings, read from the environment and an optional .env file.

The Gemini key is read here and nowhere else. It is never printed, logged or
sent anywhere but the `x-goog-api-key` header of a request to Google.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    # Minimal KEY=VALUE reader; real environment variables win.
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")

# The CRM database and the telemetry log. On Render's free plan the disk is
# not persistent: telemetry resets whenever the service restarts or sleeps.
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / ".data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

CRM_DB = Path(os.environ.get("CRM_DB", DATA_DIR / "crm.sqlite"))
TELEMETRY_DB = Path(os.environ.get("TELEMETRY_DB", DATA_DIR / "telemetry.sqlite"))
CACHE_DIR = ROOT / ".cache" / "llm"
RESULTS_DIR = ROOT / "evals" / "results"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# 3.5 Flash-Lite: answers in about 2 s and was available when gemini-3.8-flash
# returned "high demand" errors (2026-11-13). Set GEMINI_MODEL to compare.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
# USD per million tokens, paid tier, from the official pricing page (read
# 2026-11-13). gemini-3.5-flash-lite: 0.30 in / 2.50 out. If you switch to
# gemini-3.8-flash set 0.75 / 3.75 (through 2026-12-31; 1.50 / 7.50 from 2027).
# Thinking tokens are billed as output.
PRICE_IN_PER_M = float(os.environ.get("GEMINI_PRICE_IN_PER_M", "0.30"))
PRICE_OUT_PER_M = float(os.environ.get("GEMINI_PRICE_OUT_PER_M", "2.50"))
# Gemini 3 sets thinking by level (low / medium / high). Empty = the model's
# default; set "low" for gemini-3.8-flash to keep latency and cost down.
THINKING_LEVEL = os.environ.get("GEMINI_THINKING_LEVEL", "")

# The public demo spends the owner's key, so it is capped.
DAILY_REQUEST_CAP = int(os.environ.get("DAILY_REQUEST_CAP", "300"))
PER_IP_PER_HOUR = int(os.environ.get("PER_IP_PER_HOUR", "30"))
MAX_QUESTION_CHARS = 300
