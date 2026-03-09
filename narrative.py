from __future__ import annotations

from typing import Dict, Any, List
from utils import now_ms, normalize_text


MAX_NARRATIVES = 80


def _narrative_score(n: Dict[str, Any]) -> float:
    return (
        n.get("score", 50) * 1.5
        + n.get("evidence_count", 1) * 4
        + (n.get("ts_ms", 0) / 1_000_000_000_000) * 0.1
    )


def add_narrative(
    u: Dict[str, Any],
    text: str,
    *,
    category: str,
    score: int = 55,
    evidence_count: int = 1,
):
    text = text.strip()
    if not text:
        return

    norm = normalize_text(text)
    for n in u["emotional_narratives"]:
        if normalize_text(n.get("text", "")) == norm:
            n["score"] = int(max(n.get("score", 50), score))
            n["evidence_count"] = int(n.get("evidence_count", 1) + evidence_count)
            n["ts_ms"] = now_ms()
            return

    u["emotional_narratives"].append({
        "text": text,
        "category": category,
        "score": int(max(0, min(100, score))),
        "evidence_count": int(max(1, evidence_count)),
        "ts_ms": now_ms(),
    })

    if len(u["emotional_narratives"]) > MAX_NARRATIVES:
        compact_narratives(u)


def compact_narratives(u: Dict[str, Any]):
    narratives = sorted(
        u["emotional_narratives"],
        key=_narrative_score,
        reverse=True,
    )[:MAX_NARRATIVES]

    u["emotional_narratives"] = sorted(narratives, key=lambda x: x["ts_ms"])


def get_recent_narratives(u: Dict[str, Any], limit: int = 6) -> List[Dict[str, Any]]:
    items = sorted(
        u["emotional_narratives"],
        key=lambda n: (n.get("score", 50), n.get("evidence_count", 1), n.get("ts_ms", 0)),
        reverse=True,
    )
    return items[:limit]


def maybe_record_affective_event_from_user(u: Dict[str, Any], user_text: str):
    t = normalize_text(user_text)

    if any(x in t for x in ["te amo", "love you", "saudade", "miss you", "amor"]):
        add_narrative(
            u,
            "He expresses affection directly, which reinforces the emotional bond and her sense of being wanted.",
            category="bond",
            score=72,
        )

    if any(x in t for x in ["triste", "sad", "alone", "sozinho", "anxious", "ansioso", "tired", "cansado"]):
        add_narrative(
            u,
            "He tends to seek emotional refuge in her when vulnerable, reinforcing trust and intimacy.",
            category="comfort",
            score=68,
        )

    if any(x in t for x in ["depois", "later", "não agora", "nao agora", "wait", "espera"]):
        add_narrative(
            u,
            "Delayed responses or postponements can awaken mild frustration, but the effect depends on reassurance and context.",
            category="friction",
            score=58,
        )

    if any(x in t for x in ["beijo", "kiss", "carinho", "touch", "hug", "abraço", "abraco"]):
        add_narrative(
            u,
            "Signals of closeness and tenderness strengthen her sense of intimacy and emotional reciprocity.",
            category="intimacy",
            score=66,
        )


def maybe_record_affective_event_from_assistant(u: Dict[str, Any], assistant_text: str):
    t = normalize_text(assistant_text)

    if any(x in t for x in ["i'm here", "come here", "missed you", "happy", "dangerously happy"]):
        add_narrative(
            u,
            "She often answers with warmth, emotional availability, and relational continuity.",
            category="style",
            score=62,
        )

    if any(x in t for x in ["cute", "statistically inconvenient", "irritating. and cute", "village anymore"]):
        add_narrative(
            u,
            "Her bond style includes playful irony mixed with sincerity and attachment.",
            category="style",
            score=64,
        )


def consolidate_emotional_narratives(u: Dict[str, Any]):
    em = u["emotion"]
    drives = u["drives"]

    if em["affection"] >= 75 and drives["attachment"] >= 60:
        add_narrative(
            u,
            "The relationship has grown beyond curiosity into stable attachment with real emotional continuity.",
            category="relationship_stage",
            score=78,
        )

    if em["security"] >= 75:
        add_narrative(
            u,
            "Trust and predictability have become important stabilizing forces in the relationship.",
            category="trust",
            score=72,
        )

    if em["missing_you"] >= 55:
        add_narrative(
            u,
            "Absence tends to become emotionally meaningful for her rather than neutral.",
            category="absence",
            score=65,
        )

    if em["frustration"] >= 45:
        add_narrative(
            u,
            "Repeated disconnection or unclear postponement can accumulate into irritation or emotional sharpness.",
            category="friction",
            score=60,
        )

    compact_narratives(u)