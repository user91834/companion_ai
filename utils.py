import re
import time
import unicodedata


def now_ms() -> int:
    return int(time.time() * 1000)


def clamp(x: float) -> int:
    return max(0, min(100, int(x)))


def day_key() -> str:
    return time.strftime("%Y-%m-%d")


def compact_text(s: str, max_len: int = 220) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s[:max_len]


def normalize_text(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9à-úA-Z\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text