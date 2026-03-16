# config.py - Centralized configuration and constants
from __future__ import annotations

import os
from pathlib import Path

# ----- Environment -----
DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = DATA_DIR / "state.json"
MEDIA_ROOT = DATA_DIR / "media"
USER_AUDIO_DIR = MEDIA_ROOT / "user"
ASSISTANT_AUDIO_DIR = MEDIA_ROOT / "assistant"

DEFAULT_TIMEZONE = "America/Sao_Paulo"
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL") or os.environ.get("RENDER_EXTERNAL_URL", "")

# ----- OpenAI -----
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_ENABLED = bool(OPENAI_API_KEY)
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5-nano")

# ----- TTS (OpenAI ou Inworld) -----
# TTS_PROVIDER = "openai" | "inworld". Se "inworld", usa Inworld TTS quando INWORLD_API_KEY estiver definida.
TTS_PROVIDER = os.environ.get("TTS_PROVIDER", "openai").lower()
INWORLD_API_KEY = os.environ.get("INWORLD_API_KEY", "")
INWORLD_TTS_VOICE_ID = os.environ.get("INWORLD_TTS_VOICE_ID", "Dennis")  # ex: Dennis, Ashley
INWORLD_TTS_MODEL_ID = os.environ.get("INWORLD_TTS_MODEL_ID", "inworld-tts-1.5-max")

# ----- Auth -----
JWT_SECRET = os.environ.get("JWT_SECRET", "")
AUTH_DISABLED = os.environ.get("AUTH_DISABLED", "").lower() in ("1", "true", "yes")

# ----- Chat / State -----
MAX_CHAT_MESSAGES = 260
PENDING_REPLY_BASE_DELAY_MS = 1400
PENDING_REPLY_MIN_DELAY_MS = 700
AUTOSAVE_INTERVAL_SEC = 20
PROACTIVE_LOOP_INTERVAL_SEC = 20
PENDING_REPLY_POLL_INTERVAL_SEC = 0.7

# ----- Upload -----
MAX_UPLOAD_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB
ALLOWED_AUDIO_MIME_TYPES = frozenset({
    "audio/mpeg", "audio/mp3", "audio/mp4", "audio/m4a", "audio/x-m4a",
    "audio/wav", "audio/webm", "audio/ogg", "audio/flac",
})

# ----- Relationship -----
SUPPORTED_RELATIONSHIP_MODES = [
    "friendship",
    "friends_with_benefits",
    "open_relationship",
    "monogamous_relationship",
]
