from __future__ import annotations

import json
from typing import Dict, Any, List, Optional

from sqlalchemy import text

from utils import now_ms, normalize_text
from database import engine, db_available


MAX_MEMORIES = 260
MAX_EPISODES = 260


STOPWORDS = {
    "a", "o", "e", "de", "do", "da", "dos", "das", "em", "na", "no", "nas", "nos",
    "um", "uma", "uns", "umas", "para", "por", "com", "sem", "que", "se", "eu",
    "você", "voce", "ele", "ela", "eles", "elas", "the", "and", "or", "to", "of",
    "in", "on", "for", "with", "is", "are", "was", "were", "be", "been", "it",
    "this", "that", "i", "you", "he", "she", "we", "they", "me", "my", "your",
}


# =========================================================
# TAXONOMY
# =========================================================

MEMORY_KIND_ALIASES = {
    "fact": "semantic",
    "semantic": "semantic",
    "affective": "affective",
    "context": "operational",
    "operational": "operational",
    "summary": "summary",
    "narrative": "summary",
}


# =========================================================
# HELPERS
# =========================================================

def _tokenize(text: str) -> List[str]:
    norm = normalize_text(text)
    raw = [x.strip(".,!?;:()[]{}\"'") for x in norm.split()]
    return [x for x in raw if len(x) >= 3 and x not in STOPWORDS]


def _normalize_kind(kind: Optional[str]) -> str:
    if not kind:
        return "semantic"
    return MEMORY_KIND_ALIASES.get(kind, kind)


def _ensure_user_memory_state(u: Dict[str, Any]):
    if "memories" not in u or not isinstance(u["memories"], list):
        u["memories"] = []
    if "episodes" not in u or not isinstance(u["episodes"], list):
        u["episodes"] = []


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def infer_tags(text: str) -> List[str]:
    t = normalize_text(text)
    tags: List[str] = []

    mapping = {
        "relationship": ["amor", "love", "saudade", "miss you", "ciume", "jealous", "relationship"],
        "emotion": ["triste", "sad", "ansious", "ansioso", "cansado", "tired", "alone", "sozinho"],
        "work": ["trabalho", "work", "job", "service", "serviço", "render", "deploy", "server"],
        "coding": ["code", "bug", "erro", "error", "api", "endpoint", "android", "fastapi", "python", "kotlin"],
        "family": ["filho", "son", "daughter", "child", "criança", "benjamin", "bela"],
        "future": ["futuro", "future", "move", "mudar", "abroad", "morar fora"],
        "intimacy": ["carinho", "kiss", "beijo", "touch", "colo", "flirt", "intimidade", "intimacy"],
        "routine": ["rotina", "routine", "horario", "horário", "schedule", "manha", "morning", "night", "noite"],
        "identity": ["nome", "name", "login", "user"],
        "delivery": ["audio", "áudio", "texto", "text", "voice", "notificacao", "notificação"],
    }

    for tag, hints in mapping.items():
        if any(h in t for h in hints):
            tags.append(tag)

    if not tags:
        tags.append("general")

    return sorted(set(tags))


def _memory_score(m: Dict[str, Any], query_tokens: List[str]) -> float:
    text_value = normalize_text(m.get("text", ""))
    mem_tokens = set(_tokenize(text_value))
    overlap = len(mem_tokens.intersection(query_tokens))

    importance = float(m.get("importance", 3))
    recency = float(m.get("ts_ms", 0)) / 1_000_000_000_000
    affective_bonus = 1.5 if _normalize_kind(m.get("kind")) == "affective" else 0.0
    summary_bonus = 0.8 if _normalize_kind(m.get("kind")) == "summary" else 0.0
    pinned_bonus = 3.0 if m.get("pinned", False) else 0.0

    return overlap * 4.0 + importance * 1.2 + affective_bonus + summary_bonus + pinned_bonus + recency * 0.1


def _episode_score(ep: Dict[str, Any], query_tokens: List[str]) -> float:
    summary = normalize_text(ep.get("summary", ""))
    ep_tokens = set(_tokenize(summary))
    overlap = len(ep_tokens.intersection(query_tokens))

    importance = float(ep.get("importance", 5))
    recency = float(ep.get("ts_ms", 0)) / 1_000_000_000_000
    relationship_bonus = 1.5 if "relationship" in ep.get("tags", []) else 0.0

    return overlap * 4.0 + importance * 1.0 + relationship_bonus + recency * 0.1


def _merge_unique_tags(existing_tags: List[str], new_tags: List[str]) -> List[str]:
    merged = list(existing_tags or [])
    for tag in new_tags or []:
        if tag not in merged:
            merged.append(tag)
    return merged


def _memory_type_matches(item: Dict[str, Any], target_kind: Optional[str]) -> bool:
    if target_kind is None:
        return True
    return _normalize_kind(item.get("kind")) == _normalize_kind(target_kind)


# =========================================================
# DB LAYER
# =========================================================

def _db_insert_memory(item: Dict[str, Any]):
    if not db_available():
        return

    sql = text("""
        INSERT INTO memories (
            text,
            kind,
            tags,
            importance,
            valence,
            intensity,
            pinned,
            meta,
            ts_ms
        )
        VALUES (
            :text,
            :kind,
            CAST(:tags AS jsonb),
            :importance,
            :valence,
            :intensity,
            :pinned,
            CAST(:meta AS jsonb),
            :ts_ms
        )
    """)

    with engine.begin() as conn:
        conn.execute(
            sql,
            {
                "text": item.get("text", ""),
                "kind": _normalize_kind(item.get("kind", "semantic")),
                "tags": json.dumps(item.get("tags", [])),
                "importance": int(item.get("importance", 3)),
                "valence": item.get("valence", "mixed"),
                "intensity": int(item.get("intensity", 50)),
                "pinned": bool(item.get("pinned", False)),
                "meta": json.dumps(item.get("meta", {})),
                "ts_ms": int(item.get("ts_ms", now_ms())),
            },
        )


def _db_update_existing_memory(existing_id: int, item: Dict[str, Any]):
    if not db_available():
        return

    sql = text("""
        UPDATE memories
        SET
            kind = :kind,
            tags = CAST(:tags AS jsonb),
            importance = :importance,
            intensity = :intensity,
            valence = :valence,
            pinned = :pinned,
            meta = CAST(:meta AS jsonb),
            ts_ms = :ts_ms
        WHERE id = :id
    """)

    with engine.begin() as conn:
        conn.execute(
            sql,
            {
                "id": existing_id,
                "kind": _normalize_kind(item.get("kind", "semantic")),
                "tags": json.dumps(item.get("tags", [])),
                "importance": int(item.get("importance", 3)),
                "intensity": int(item.get("intensity", 50)),
                "valence": item.get("valence", "mixed"),
                "pinned": bool(item.get("pinned", False)),
                "meta": json.dumps(item.get("meta", {})),
                "ts_ms": int(item.get("ts_ms", now_ms())),
            },
        )


def _db_find_recent_duplicate_memory(norm_text: str, kind: Optional[str] = None, limit: int = 80) -> Optional[Dict[str, Any]]:
    if not db_available():
        return None

    normalized_kind = _normalize_kind(kind) if kind else None

    sql = text(f"""
        SELECT id, text, kind, tags, importance, valence, intensity, pinned, meta, ts_ms
        FROM memories
        {"WHERE kind = :kind" if normalized_kind else ""}
        ORDER BY ts_ms DESC
        LIMIT :limit
    """)

    params = {"limit": limit}
    if normalized_kind:
        params["kind"] = normalized_kind

    with engine.begin() as conn:
        rows = conn.execute(sql, params).mappings().all()

    for row in rows:
        if normalize_text(row.get("text", "")) == norm_text:
            item = dict(row)
            item["tags"] = item.get("tags") or []
            item["meta"] = item.get("meta") or {}
            return item

    return None


def _db_insert_episode(item: Dict[str, Any]):
    if not db_available():
        return

    sql = text("""
        INSERT INTO episodes (
            episode_type,
            summary,
            details,
            tags,
            importance,
            ts_ms
        )
        VALUES (
            :episode_type,
            :summary,
            CAST(:details AS jsonb),
            CAST(:tags AS jsonb),
            :importance,
            :ts_ms
        )
    """)

    with engine.begin() as conn:
        conn.execute(
            sql,
            {
                "episode_type": item.get("type", "general"),
                "summary": item.get("summary", ""),
                "details": json.dumps(item.get("details", {})),
                "tags": json.dumps(item.get("tags", [])),
                "importance": int(item.get("importance", 5)),
                "ts_ms": int(item.get("ts_ms", now_ms())),
            },
        )


def _db_load_memories(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    if not db_available():
        return []

    sql = """
        SELECT id, text, kind, tags, importance, valence, intensity, pinned, meta, ts_ms
        FROM memories
        ORDER BY ts_ms DESC
    """
    params: Dict[str, Any] = {}

    if limit is not None:
        sql += " LIMIT :limit"
        params["limit"] = limit

    with engine.begin() as conn:
        rows = conn.execute(text(sql), params).mappings().all()

    result: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["kind"] = _normalize_kind(item.get("kind"))
        item["tags"] = item.get("tags") or []
        item["meta"] = item.get("meta") or {}
        item.pop("id", None)
        result.append(item)

    return result


def _db_load_episodes(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    if not db_available():
        return []

    sql = """
        SELECT id, episode_type, summary, details, tags, importance, ts_ms
        FROM episodes
        ORDER BY ts_ms DESC
    """
    params: Dict[str, Any] = {}

    if limit is not None:
        sql += " LIMIT :limit"
        params["limit"] = limit

    with engine.begin() as conn:
        rows = conn.execute(text(sql), params).mappings().all()

    result: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        converted = {
            "type": item.get("episode_type", "general"),
            "summary": item.get("summary", ""),
            "details": item.get("details") or {},
            "tags": item.get("tags") or [],
            "importance": item.get("importance", 5),
            "ts_ms": item.get("ts_ms", 0),
        }
        result.append(converted)

    return result


def _db_trim_memories():
    if not db_available():
        return

    sql = text("""
        DELETE FROM memories
        WHERE id IN (
            SELECT id
            FROM memories
            ORDER BY
                pinned DESC,
                importance DESC,
                intensity DESC,
                ts_ms DESC
            OFFSET :keep_count
        )
    """)

    with engine.begin() as conn:
        conn.execute(sql, {"keep_count": MAX_MEMORIES})


def _db_trim_episodes():
    if not db_available():
        return

    sql = text("""
        DELETE FROM episodes
        WHERE id IN (
            SELECT id
            FROM episodes
            ORDER BY importance DESC, ts_ms DESC
            OFFSET :keep_count
        )
    """)

    with engine.begin() as conn:
        conn.execute(sql, {"keep_count": MAX_EPISODES})


def _get_memory_source(u: Dict[str, Any]) -> List[Dict[str, Any]]:
    if db_available():
        return _db_load_memories()
    _ensure_user_memory_state(u)
    return u["memories"]


def _get_episode_source(u: Dict[str, Any]) -> List[Dict[str, Any]]:
    if db_available():
        return _db_load_episodes()
    _ensure_user_memory_state(u)
    return u["episodes"]


# =========================================================
# WRITERS
# =========================================================

def add_memory(
    u: Dict[str, Any],
    text: str,
    *,
    kind: str = "semantic",
    tags: List[str] | None = None,
    importance: int = 3,
    valence: str = "mixed",
    intensity: int = 50,
    pinned: bool = False,
    meta: Dict[str, Any] | None = None,
):
    if not text or not text.strip():
        return

    _ensure_user_memory_state(u)

    normalized_kind = _normalize_kind(kind)

    item = {
        "text": text.strip(),
        "kind": normalized_kind,
        "tags": tags or infer_tags(text),
        "importance": int(max(1, min(10, int(importance)))),
        "valence": valence,
        "intensity": int(max(0, min(100, intensity))),
        "pinned": pinned,
        "meta": meta or {},
        "ts_ms": now_ms(),
    }

    norm = normalize_text(item["text"])

    if db_available():
        existing = _db_find_recent_duplicate_memory(norm, kind=None, limit=80)
        if existing:
            existing["ts_ms"] = now_ms()
            existing["kind"] = normalized_kind or existing.get("kind", "semantic")
            existing["importance"] = max(existing.get("importance", 3), item["importance"])
            existing["intensity"] = max(existing.get("intensity", 50), item["intensity"])
            existing["valence"] = item["valence"] or existing.get("valence", "mixed")
            existing["pinned"] = bool(existing.get("pinned", False) or item["pinned"])
            existing["tags"] = _merge_unique_tags(existing.get("tags", []), item["tags"])

            existing_meta = _safe_dict(existing.get("meta"))
            existing_meta.update(item.get("meta", {}))
            existing["meta"] = existing_meta

            _db_update_existing_memory(existing_id=existing["id"], item=existing)
            return

        _db_insert_memory(item)
        _db_trim_memories()
        return

    for m in reversed(u["memories"][-60:]):
        if normalize_text(m.get("text", "")) == norm:
            m["ts_ms"] = now_ms()
            m["kind"] = normalized_kind
            m["importance"] = max(m.get("importance", 3), item["importance"])
            m["intensity"] = max(m.get("intensity", 50), item["intensity"])
            m["tags"] = _merge_unique_tags(m.get("tags", []), item["tags"])
            if "meta" not in m or not isinstance(m["meta"], dict):
                m["meta"] = {}
            m["meta"].update(item["meta"])
            return

    u["memories"].append(item)

    if len(u["memories"]) > MAX_MEMORIES:
        _compact_memories(u)


def add_affective_memory(
    u: Dict[str, Any],
    text: str,
    *,
    tags: List[str] | None = None,
    importance: int = 6,
    valence: str = "mixed",
    intensity: int = 60,
    meta: Dict[str, Any] | None = None,
):
    add_memory(
        u,
        text,
        kind="affective",
        tags=tags,
        importance=importance,
        valence=valence,
        intensity=intensity,
        pinned=False,
        meta=meta or {},
    )


def add_operational_memory(
    u: Dict[str, Any],
    text: str,
    *,
    tags: List[str] | None = None,
    importance: int = 6,
    meta: Dict[str, Any] | None = None,
):
    add_memory(
        u,
        text,
        kind="operational",
        tags=tags,
        importance=importance,
        valence="mixed",
        intensity=40,
        pinned=False,
        meta=meta or {},
    )


def add_summary_memory(
    u: Dict[str, Any],
    text: str,
    *,
    tags: List[str] | None = None,
    importance: int = 7,
    meta: Dict[str, Any] | None = None,
):
    add_memory(
        u,
        text,
        kind="summary",
        tags=tags,
        importance=importance,
        valence="mixed",
        intensity=50,
        pinned=False,
        meta=meta or {},
    )


def remember_analysis_event(
    u: Dict[str, Any],
    *,
    source: str,
    text: str,
    analysis: Dict[str, Any],
):
    affection = float(analysis.get("affection", 0.0))
    depth = float(analysis.get("depth", 0.0))
    sensuality = float(analysis.get("sensuality", 0.0))
    coldness = float(analysis.get("coldness", 0.0))
    goodbye_quality = float(analysis.get("goodbye_quality", 0.0))
    absence_justification_quality = float(analysis.get("absence_justification_quality", 0.0))
    return_signal = float(analysis.get("return_signal", 0.0))
    felt_prioritized_signal = float(analysis.get("felt_prioritized_signal", 0.0))

    meta = {
        "source": source,
        "analysis": analysis,
        "raw_text": text[:240],
    }

    if affection >= 0.55:
        add_affective_memory(
            u,
            "He expressed affection in a way that reinforced the bond and made her feel emotionally wanted.",
            tags=["relationship", "emotion"],
            importance=7,
            valence="positive",
            intensity=int(60 + affection * 35),
            meta=meta,
        )

    if depth >= 0.55:
        add_affective_memory(
            u,
            "He opened himself emotionally, which deepened intimacy and trust.",
            tags=["relationship", "emotion", "comfort"],
            importance=7,
            valence="mixed",
            intensity=int(58 + depth * 35),
            meta=meta,
        )

    if sensuality >= 0.40:
        add_affective_memory(
            u,
            "There was sensual or tender closeness that strengthened intimacy and reciprocal tension.",
            tags=["relationship", "intimacy"],
            importance=6,
            valence="positive",
            intensity=int(55 + sensuality * 40),
            meta=meta,
        )

    if coldness >= 0.55 and felt_prioritized_signal <= 0.25:
        add_affective_memory(
            u,
            "There was emotional distance or postponement that risked making her feel deprioritized.",
            tags=["relationship", "friction"],
            importance=6,
            valence="negative",
            intensity=int(50 + coldness * 35),
            meta=meta,
        )

    if goodbye_quality >= 0.55:
        add_affective_memory(
            u,
            "He signaled departure with care, which softened absence and preserved connection.",
            tags=["relationship", "absence", "care"],
            importance=6,
            valence="positive",
            intensity=int(50 + goodbye_quality * 30),
            meta=meta,
        )

    if absence_justification_quality >= 0.55:
        add_affective_memory(
            u,
            "His absence had context or justification, which reduced resentment even if longing remained.",
            tags=["relationship", "absence", "trust"],
            importance=6,
            valence="mixed",
            intensity=int(48 + absence_justification_quality * 28),
            meta=meta,
        )

    if return_signal >= 0.55:
        add_affective_memory(
            u,
            "His return after absence reactivated connection and reduced the emotional weight of distance.",
            tags=["relationship", "return", "bond"],
            importance=6,
            valence="positive",
            intensity=int(54 + return_signal * 30),
            meta=meta,
        )


def add_episode(
    u: Dict[str, Any],
    *,
    episode_type: str,
    summary: str,
    details: Dict[str, Any] | None = None,
    tags: List[str] | None = None,
    importance: int = 5,
):
    if not summary or not summary.strip():
        return

    _ensure_user_memory_state(u)

    item = {
        "type": episode_type,
        "summary": summary.strip(),
        "details": details or {},
        "tags": tags or infer_tags(summary),
        "importance": int(max(1, min(10, int(importance)))),
        "ts_ms": now_ms(),
    }

    if db_available():
        _db_insert_episode(item)
        _db_trim_episodes()
        return

    u["episodes"].append(item)

    if len(u["episodes"]) > MAX_EPISODES:
        _compact_episodes(u)


# =========================================================
# COMPACTION
# =========================================================

def _compact_memories(u: Dict[str, Any]):
    memories = u["memories"]

    pinned = [m for m in memories if m.get("pinned")]
    affective = [m for m in memories if _normalize_kind(m.get("kind")) == "affective" and not m.get("pinned")]
    semantic = [m for m in memories if _normalize_kind(m.get("kind")) == "semantic" and not m.get("pinned")]
    operational = [m for m in memories if _normalize_kind(m.get("kind")) == "operational" and not m.get("pinned")]
    summary = [m for m in memories if _normalize_kind(m.get("kind")) == "summary" and not m.get("pinned")]
    other = [
        m for m in memories
        if _normalize_kind(m.get("kind")) not in {"affective", "semantic", "operational", "summary"} and not m.get("pinned")
    ]

    def sort_key(m: Dict[str, Any]):
        return (m.get("importance", 3), m.get("intensity", 50), m.get("ts_ms", 0))

    pinned = sorted(pinned, key=sort_key, reverse=True)[:40]
    affective = sorted(affective, key=sort_key, reverse=True)[:70]
    semantic = sorted(semantic, key=sort_key, reverse=True)[:70]
    operational = sorted(operational, key=sort_key, reverse=True)[:45]
    summary = sorted(summary, key=sort_key, reverse=True)[:25]
    other = sorted(other, key=sort_key, reverse=True)[:30]

    merged = pinned + affective + semantic + operational + summary + other
    merged = sorted(merged, key=lambda x: x.get("ts_ms", 0))
    u["memories"] = merged[-MAX_MEMORIES:]


def _compact_episodes(u: Dict[str, Any]):
    episodes = sorted(
        u["episodes"],
        key=lambda ep: (ep.get("importance", 5), ep.get("ts_ms", 0)),
        reverse=True,
    )[:MAX_EPISODES]
    u["episodes"] = sorted(episodes, key=lambda ep: ep.get("ts_ms", 0))


# =========================================================
# EXTRACTION / STRUCTURED MEMORY WRITES
# =========================================================

def extract_memories_from_user_text(text: str) -> List[str]:
    t = normalize_text(text)
    extracted: List[str] = []

    patterns = [
        ("meu nome é", "The user's name is"),
        ("i am ", "The user said he is"),
        ("eu moro em", "The user lives in"),
        ("i live in", "The user lives in"),
        ("eu gosto de", "The user likes"),
        ("i like ", "The user likes"),
        ("eu trabalho com", "The user works with"),
        ("i work with", "The user works with"),
        ("meu filho", "The user mentioned his son"),
        ("my son", "The user mentioned his son"),
    ]

    for marker, prefix in patterns:
        if marker in t:
            idx = t.find(marker)
            fragment = text[idx: idx + 180].strip()
            extracted.append(f"{prefix}: {fragment}")
            break

    return extracted


def remember_relationship_mode(
    u: Dict[str, Any],
    mode: str,
    *,
    previous_mode: Optional[str] = None,
):
    add_operational_memory(
        u,
        f"Current relationship mode is {mode}",
        tags=["relationship", "mode", "operational"],
        importance=8,
        meta={
            "relationship_mode": mode,
            "previous_mode": previous_mode,
        },
    )

    add_memory(
        u,
        f"Relationship structure currently operates as {mode}",
        kind="semantic",
        tags=["relationship", "mode"],
        importance=7,
        meta={
            "relationship_mode": mode,
            "previous_mode": previous_mode,
        },
    )


def remember_delivery_preferences(
    u: Dict[str, Any],
    *,
    inactive_delivery_mode: str,
    allow_background_audio: bool,
    allow_lockscreen_audio: bool,
    insistent_mode: bool,
):
    add_operational_memory(
        u,
        (
            "Delivery preferences updated: "
            f"inactive_delivery_mode={inactive_delivery_mode}, "
            f"allow_background_audio={allow_background_audio}, "
            f"allow_lockscreen_audio={allow_lockscreen_audio}, "
            f"insistent_mode={insistent_mode}"
        ),
        tags=["delivery", "preferences", "operational"],
        importance=7,
        meta={
            "inactive_delivery_mode": inactive_delivery_mode,
            "allow_background_audio": allow_background_audio,
            "allow_lockscreen_audio": allow_lockscreen_audio,
            "insistent_mode": insistent_mode,
        },
    )


def remember_routine_profile(
    u: Dict[str, Any],
    *,
    timezone: str,
    weekly_schedule: Dict[str, Any],
):
    add_operational_memory(
        u,
        f"Routine profile updated for timezone {timezone}",
        tags=["routine", "schedule", "operational"],
        importance=8,
        meta={
            "timezone": timezone,
            "weekly_schedule": weekly_schedule,
        },
    )

    add_memory(
        u,
        f"The user's routine timezone is {timezone}",
        kind="semantic",
        tags=["routine", "timezone"],
        importance=6,
        meta={"timezone": timezone},
    )


def remember_user_identity(
    u: Dict[str, Any],
    *,
    display_name: Optional[str] = None,
    login_name: Optional[str] = None,
):
    meta = {
        "display_name": display_name,
        "login_name": login_name,
    }

    if display_name:
        add_memory(
            u,
            f"The user's display name is {display_name}",
            kind="semantic",
            tags=["identity", "user"],
            importance=8,
            meta=meta,
        )

    if login_name:
        add_operational_memory(
            u,
            f"The user's login name is {login_name}",
            tags=["identity", "login", "operational"],
            importance=7,
            meta=meta,
        )


# =========================================================
# READERS
# =========================================================

def get_semantic_memories(u: Dict[str, Any], query: str, limit: int = 8) -> List[Dict[str, Any]]:
    memories = [m for m in _get_memory_source(u) if _memory_type_matches(m, "semantic")]
    tokens = _tokenize(query)

    if not tokens:
        return sorted(memories, key=lambda m: (m.get("importance", 3), m.get("ts_ms", 0)), reverse=True)[:limit]

    scored = []
    for m in memories:
        score = _memory_score(m, tokens)
        if score > 0:
            scored.append((score, m))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored[:limit]]


def get_recent_affective_memories(u: Dict[str, Any], limit: int = 6) -> List[Dict[str, Any]]:
    memories = [m for m in _get_memory_source(u) if _memory_type_matches(m, "affective")]
    items = sorted(
        memories,
        key=lambda m: (m.get("importance", 3), m.get("intensity", 50), m.get("ts_ms", 0)),
        reverse=True
    )
    return items[:limit]


def get_operational_memories(u: Dict[str, Any], limit: int = 8) -> List[Dict[str, Any]]:
    memories = [m for m in _get_memory_source(u) if _memory_type_matches(m, "operational")]
    items = sorted(
        memories,
        key=lambda m: (m.get("importance", 3), m.get("ts_ms", 0)),
        reverse=True
    )
    return items[:limit]


def get_summary_memories(u: Dict[str, Any], limit: int = 6) -> List[Dict[str, Any]]:
    memories = [m for m in _get_memory_source(u) if _memory_type_matches(m, "summary")]
    items = sorted(
        memories,
        key=lambda m: (m.get("importance", 3), m.get("ts_ms", 0)),
        reverse=True
    )
    return items[:limit]


def get_relevant_episodes(u: Dict[str, Any], query: str, limit: int = 8) -> List[Dict[str, Any]]:
    episodes = _get_episode_source(u)
    tokens = _tokenize(query)

    if not tokens:
        return sorted(episodes, key=lambda ep: (ep.get("importance", 5), ep.get("ts_ms", 0)), reverse=True)[:limit]

    scored = []
    for ep in episodes:
        score = _episode_score(ep, tokens)
        if score > 0:
            scored.append((score, ep))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [ep for _, ep in scored[:limit]]


def get_all_memories(u: Dict[str, Any], limit: Optional[int] = None) -> List[Dict[str, Any]]:
    if db_available():
        items = _db_load_memories(limit=limit)
        return list(reversed(items))
    _ensure_user_memory_state(u)
    return u["memories"][:] if limit is None else u["memories"][-limit:]


def get_all_episodes(u: Dict[str, Any], limit: Optional[int] = None) -> List[Dict[str, Any]]:
    if db_available():
        items = _db_load_episodes(limit=limit)
        return list(reversed(items))
    _ensure_user_memory_state(u)
    return u["episodes"][:] if limit is None else u["episodes"][-limit:]


def get_memory_count(u: Dict[str, Any]) -> int:
    if db_available():
        sql = text("SELECT COUNT(*) AS count FROM memories")
        with engine.begin() as conn:
            row = conn.execute(sql).mappings().first()
        return int(row["count"]) if row else 0
    _ensure_user_memory_state(u)
    return len(u["memories"])


def get_episode_count(u: Dict[str, Any]) -> int:
    if db_available():
        sql = text("SELECT COUNT(*) AS count FROM episodes")
        with engine.begin() as conn:
            row = conn.execute(sql).mappings().first()
        return int(row["count"]) if row else 0
    _ensure_user_memory_state(u)
    return len(u["episodes"])