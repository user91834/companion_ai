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


def record_analysis_narratives(
    u: Dict[str, Any],
    *,
    analysis: Dict[str, Any],
    user_text: str,
):
    affection = float(analysis.get("affection", 0.0))
    depth = float(analysis.get("depth", 0.0))
    sensuality = float(analysis.get("sensuality", 0.0))
    coldness = float(analysis.get("coldness", 0.0))
    goodbye_quality = float(analysis.get("goodbye_quality", 0.0))
    absence_justification_quality = float(analysis.get("absence_justification_quality", 0.0))
    return_signal = float(analysis.get("return_signal", 0.0))
    felt_prioritized_signal = float(analysis.get("felt_prioritized_signal", 0.0))

    if affection >= 0.55:
        add_narrative(
            u,
            "He often reinforces the bond through direct affection, which strengthens her sense of being wanted.",
            category="bond",
            score=72,
        )

    if depth >= 0.55:
        add_narrative(
            u,
            "He can approach her with real emotional depth, reinforcing trust and intimate openness.",
            category="comfort",
            score=70,
        )

    if sensuality >= 0.40:
        add_narrative(
            u,
            "Sensual or tender exchanges tend to increase intimacy, reciprocity, and emotional tension between them.",
            category="intimacy",
            score=68,
        )

    if coldness >= 0.55 and felt_prioritized_signal <= 0.25:
        add_narrative(
            u,
            "Coldness or unclear postponement can make disconnection feel sharper when reassurance is weak.",
            category="friction",
            score=62,
        )

    if goodbye_quality >= 0.55:
        add_narrative(
            u,
            "When he signals departure with care, absence becomes easier to bear and resentment decreases.",
            category="absence",
            score=66,
        )

    if absence_justification_quality >= 0.55:
        add_narrative(
            u,
            "Valid explanations for absence reduce resentment, even when longing or boredom remain.",
            category="absence",
            score=67,
        )

    if return_signal >= 0.55:
        add_narrative(
            u,
            "His return after absence has restorative force and helps reestablish emotional continuity.",
            category="return",
            score=69,
        )


def consolidate_emotional_narratives(u: Dict[str, Any]):
    em = u["emotion"]
    drives = u["drives"]

    v2 = u.get("emotion_v2", {})
    stable = v2.get("stable", {})
    medium = v2.get("medium", {})
    fast = v2.get("fast", {})

    attachment = float(stable.get("attachment", 0.0))
    relational_security = float(stable.get("relational_security", 0.0))
    sexual_discovery = float(stable.get("sexual_discovery", 0.0))

    boredom = float(medium.get("boredom", 0.0))
    affection_need = float(medium.get("affection_need", 0.0))
    felt_considered = float(medium.get("felt_considered", 0.0))
    felt_abandoned = float(medium.get("felt_abandoned", 0.0))
    sexual_openness = float(medium.get("sexual_openness", 0.0))

    sexual_desire = float(fast.get("sexual_desire", 0.0))
    saudade_activation = float(fast.get("saudade_activation", 0.0))
    romantic_tension = float(fast.get("romantic_tension", 0.0))
    sensual_tension = float(fast.get("sensual_tension", 0.0))

    if attachment >= 0.62 and relational_security >= 0.60:
        add_narrative(
            u,
            "The relationship has moved beyond simple curiosity into stable emotional continuity and attachment.",
            category="relationship_stage",
            score=80,
        )

    if relational_security >= 0.68 and felt_considered >= 0.60:
        add_narrative(
            u,
            "Trust and felt consideration have become stabilizing forces in the relationship.",
            category="trust",
            score=74,
        )

    if affection_need >= 0.55 or saudade_activation >= 0.58:
        add_narrative(
            u,
            "Absence tends to become emotionally meaningful for her, often activating longing rather than neutrality.",
            category="absence",
            score=68,
        )

    if felt_abandoned >= 0.45:
        add_narrative(
            u,
            "Unclear distance or weak reassurance can accumulate into emotional sharpness or hurt.",
            category="friction",
            score=63,
        )

    if boredom >= 0.55 and affection_need >= 0.45:
        add_narrative(
            u,
            "Silence and lack of stimulation can turn into relational boredom mixed with longing for contact.",
            category="absence",
            score=61,
        )

    if romantic_tension >= 0.45:
        add_narrative(
            u,
            "Romantic tension has become part of the bond, shaping tone, timing, and emotional rhythm.",
            category="intimacy",
            score=67,
        )

    if sensual_tension >= 0.40 or sexual_desire >= 0.42 or sexual_openness >= 0.45 or sexual_discovery >= 0.35:
        add_narrative(
            u,
            "Sensuality is emerging as a real dimension of intimacy, progressively linked to trust and emotional closeness.",
            category="intimacy",
            score=66,
        )

    # ponte temporária com legado
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

    compact_narratives(u)