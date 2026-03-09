from __future__ import annotations

from typing import Dict, Any, List
from utils import now_ms, normalize_text, clamp


MAX_MEMORIES = 220
MAX_EPISODES = 220


STOPWORDS = {
    "a", "o", "e", "de", "do", "da", "dos", "das", "em", "na", "no", "nas", "nos",
    "um", "uma", "uns", "umas", "para", "por", "com", "sem", "que", "se", "eu",
    "você", "voce", "ele", "ela", "eles", "elas", "the", "and", "or", "to", "of",
    "in", "on", "for", "with", "is", "are", "was", "were", "be", "been", "it",
    "this", "that", "i", "you", "he", "she", "we", "they", "me", "my", "your",
}


def _tokenize(text: str) -> List[str]:
    norm = normalize_text(text)
    raw = [x.strip(".,!?;:()[]{}\"'") for x in norm.split()]
    return [x for x in raw if len(x) >= 3 and x not in STOPWORDS]


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
    }

    for tag, hints in mapping.items():
        if any(h in t for h in hints):
            tags.append(tag)

    if not tags:
        tags.append("general")

    return sorted(set(tags))


def _memory_score(m: Dict[str, Any], query_tokens: List[str]) -> float:
    text = normalize_text(m.get("text", ""))
    mem_tokens = set(_tokenize(text))
    overlap = len(mem_tokens.intersection(query_tokens))

    importance = float(m.get("importance", 3))
    recency = float(m.get("ts_ms", 0)) / 1_000_000_000_000
    affective_bonus = 1.5 if m.get("kind") == "affective" else 0.0
    pinned_bonus = 3.0 if m.get("pinned", False) else 0.0

    return overlap * 4.0 + importance * 1.2 + affective_bonus + pinned_bonus + recency * 0.1


def _episode_score(ep: Dict[str, Any], query_tokens: List[str]) -> float:
    summary = normalize_text(ep.get("summary", ""))
    ep_tokens = set(_tokenize(summary))
    overlap = len(ep_tokens.intersection(query_tokens))

    importance = float(ep.get("importance", 5))
    recency = float(ep.get("ts_ms", 0)) / 1_000_000_000_000
    relationship_bonus = 1.5 if "relationship" in ep.get("tags", []) else 0.0

    return overlap * 4.0 + importance * 1.0 + relationship_bonus + recency * 0.1


def add_memory(
    u: Dict[str, Any],
    text: str,
    *,
    kind: str = "fact",
    tags: List[str] | None = None,
    importance: int = 3,
    valence: str = "mixed",
    intensity: int = 50,
    pinned: bool = False,
):
    if not text or not text.strip():
        return

    item = {
        "text": text.strip(),
        "kind": kind,
        "tags": tags or infer_tags(text),
        "importance": int(clamp(importance * 10) / 10) if isinstance(importance, float) else int(max(1, min(10, importance))),
        "valence": valence,
        "intensity": int(max(0, min(100, intensity))),
        "pinned": pinned,
        "ts_ms": now_ms(),
    }

    norm = normalize_text(item["text"])
    for m in reversed(u["memories"][-40:]):
        if normalize_text(m.get("text", "")) == norm:
            m["ts_ms"] = now_ms()
            m["importance"] = max(m.get("importance", 3), item["importance"])
            m["intensity"] = max(m.get("intensity", 50), item["intensity"])
            for tag in item["tags"]:
                if tag not in m["tags"]:
                    m["tags"].append(tag)
            return

    u["memories"].append(item)

    if len(u["memories"]) > MAX_MEMORIES:
        _compact_memories(u)


def _compact_memories(u: Dict[str, Any]):
    memories = u["memories"]

    pinned = [m for m in memories if m.get("pinned")]
    affective = [m for m in memories if m.get("kind") == "affective" and not m.get("pinned")]
    facts = [m for m in memories if m.get("kind") == "fact" and not m.get("pinned")]
    other = [m for m in memories if m.get("kind") not in {"affective", "fact"} and not m.get("pinned")]

    def sort_key(m: Dict[str, Any]):
        return (m.get("importance", 3), m.get("intensity", 50), m.get("ts_ms", 0))

    pinned = sorted(pinned, key=sort_key, reverse=True)[:40]
    affective = sorted(affective, key=sort_key, reverse=True)[:70]
    facts = sorted(facts, key=sort_key, reverse=True)[:70]
    other = sorted(other, key=sort_key, reverse=True)[:40]

    merged = pinned + affective + facts + other
    merged = sorted(merged, key=lambda x: x.get("ts_ms", 0))
    u["memories"] = merged[-MAX_MEMORIES:]


def add_episode(
    u: Dict[str, Any],
    *,
    episode_type: str,
    summary: str,
    details: Dict[str, Any] | None = None,
    tags: List[str] | None = None,
    importance: int = 5,
):
    item = {
        "type": episode_type,
        "summary": summary.strip(),
        "details": details or {},
        "tags": tags or infer_tags(summary),
        "importance": int(max(1, min(10, importance))),
        "ts_ms": now_ms(),
    }
    u["episodes"].append(item)

    if len(u["episodes"]) > MAX_EPISODES:
        _compact_episodes(u)


def _compact_episodes(u: Dict[str, Any]):
    episodes = sorted(
        u["episodes"],
        key=lambda ep: (ep.get("importance", 5), ep.get("ts_ms", 0)),
        reverse=True,
    )[:MAX_EPISODES]
    u["episodes"] = sorted(episodes, key=lambda ep: ep.get("ts_ms", 0))


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


def get_semantic_memories(u: Dict[str, Any], query: str, limit: int = 8) -> List[Dict[str, Any]]:
    tokens = _tokenize(query)
    if not tokens:
        return sorted(u["memories"], key=lambda m: (m.get("importance", 3), m.get("ts_ms", 0)), reverse=True)[:limit]

    scored = []
    for m in u["memories"]:
        score = _memory_score(m, tokens)
        if score > 0:
            scored.append((score, m))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored[:limit]]


def get_recent_affective_memories(u: Dict[str, Any], limit: int = 6) -> List[Dict[str, Any]]:
    items = [m for m in u["memories"] if m.get("kind") == "affective"]
    items = sorted(items, key=lambda m: (m.get("importance", 3), m.get("ts_ms", 0)), reverse=True)
    return items[:limit]


def get_relevant_episodes(u: Dict[str, Any], query: str, limit: int = 8) -> List[Dict[str, Any]]:
    tokens = _tokenize(query)
    if not tokens:
        return sorted(u["episodes"], key=lambda ep: (ep.get("importance", 5), ep.get("ts_ms", 0)), reverse=True)[:limit]

    scored = []
    for ep in u["episodes"]:
        score = _episode_score(ep, tokens)
        if score > 0:
            scored.append((score, ep))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [ep for _, ep in scored[:limit]]