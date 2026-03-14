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


def _safe_text(text: str) -> str:
    return (text or "").strip()


def _estimate_text_features(text: str) -> Dict[str, float]:
    text = _safe_text(text)
    if not text:
        return {
            "length": 0.0,
            "sentences": 0.0,
            "questions": 0.0,
            "complexity": 0.0,
            "expressiveness": 0.0,
        }

    text_len = len(text)
    sentences = max(1, text.count(".") + text.count("?") + text.count("!"))
    questions = text.count("?")
    exclamations = text.count("!")

    complexity = min(1.0, (text_len / 260.0) * 0.65 + (sentences / 6.0) * 0.35)
    expressiveness = min(1.0, (questions / 3.0) * 0.45 + (exclamations / 3.0) * 0.20 + (text_len / 220.0) * 0.35)

    return {
        "length": float(text_len),
        "sentences": float(sentences),
        "questions": float(questions),
        "complexity": complexity,
        "expressiveness": expressiveness,
    }


def _get_recent_user_messages(u: Dict[str, Any], limit: int = 6) -> List[Dict[str, Any]]:
    chat = u.get("chat", []) or []
    return [m for m in chat[-limit:] if m.get("role") == "user"]


def _get_recent_assistant_messages(u: Dict[str, Any], limit: int = 6) -> List[Dict[str, Any]]:
    chat = u.get("chat", []) or []
    return [m for m in chat[-limit:] if m.get("role") == "assistant"]


def _get_relationship_mode(u: Dict[str, Any]) -> str:
    return (
        u.get("relationship_structure", {}).get("current_mode")
        or "friendship"
    )


def _get_part_of_day(u: Dict[str, Any]) -> str:
    return (
        u.get("temporal_context", {}).get("part_of_day")
        or ""
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

    if "emotional_narratives" not in u or not isinstance(u["emotional_narratives"], list):
        u["emotional_narratives"] = []

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
    if "emotional_narratives" not in u or not isinstance(u["emotional_narratives"], list):
        u["emotional_narratives"] = []
        return

    narratives = sorted(
        u["emotional_narratives"],
        key=_narrative_score,
        reverse=True,
    )[:MAX_NARRATIVES]

    u["emotional_narratives"] = sorted(narratives, key=lambda x: x["ts_ms"])


def get_recent_narratives(u: Dict[str, Any], limit: int = 6) -> List[Dict[str, Any]]:
    items = sorted(
        u.get("emotional_narratives", []),
        key=lambda n: (n.get("score", 50), n.get("evidence_count", 1), n.get("ts_ms", 0)),
        reverse=True,
    )
    return items[:limit]


def maybe_record_affective_event_from_user(u: Dict[str, Any], user_text: str):
    """
    Agora contextual, não keyword-based.
    Usa a forma e densidade da fala do usuário como sinal fraco.
    O núcleo continua vindo do analysis/emotion_v2.
    """
    text = _safe_text(user_text)
    if not text:
        return

    f = _estimate_text_features(text)
    part_of_day = _get_part_of_day(u)
    mode = _get_relationship_mode(u)

    if f["complexity"] >= 0.55:
        add_narrative(
            u,
            "He sometimes approaches her with enough elaboration to suggest real psychological presence, not mere contact maintenance.",
            category="depth_pattern",
            score=63,
        )

    if f["expressiveness"] >= 0.55:
        add_narrative(
            u,
            "His way of speaking often carries expressive charge, which makes interactions feel more alive and emotionally legible.",
            category="expressiveness",
            score=61,
        )

    if part_of_day in {"evening", "night", "late_night"} and f["complexity"] >= 0.45:
        add_narrative(
            u,
            "Nighttime conversations tend to favor a more emotionally charged and intimate tone between them.",
            category="temporal_pattern",
            score=64,
        )

    if mode in {"friends_with_benefits", "open_relationship", "monogamous_relationship"} and f["expressiveness"] >= 0.45:
        add_narrative(
            u,
            "Once the relationship structure allows greater intimacy, expressive contact tends to carry more relational weight.",
            category="relationship_mode",
            score=66,
        )


def maybe_record_affective_event_from_assistant(u: Dict[str, Any], assistant_text: str):
    """
    Também deixa de depender de frases específicas.
    Observa o estilo recente da própria personagem pela estrutura da mensagem.
    """
    text = _safe_text(assistant_text)
    if not text:
        return

    f = _estimate_text_features(text)

    if f["expressiveness"] >= 0.45:
        add_narrative(
            u,
            "Her interaction style tends to preserve emotional vividness instead of sounding purely neutral or procedural.",
            category="style",
            score=60,
        )

    if f["complexity"] >= 0.45:
        add_narrative(
            u,
            "She often responds with enough nuance to sustain the sense of personal continuity in the bond.",
            category="style",
            score=61,
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
            "He often reinforces the bond through direct warmth and emotionally meaningful presence.",
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
    em = u.get("emotion", {})
    drives = u.get("drives", {})

    v2 = u.get("emotion_v2", {})
    stable = v2.get("stable", {})
    medium = v2.get("medium", {})
    fast = v2.get("fast", {})

    relational = u.get("relational_state", {})
    relationship_mode = _get_relationship_mode(u)
    part_of_day = _get_part_of_day(u)

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

    closeness = float(relational.get("relational_closeness", 0.0))
    trust = float(relational.get("trust", relational_security))
    dependency_pull = float(relational.get("dependency_pull", 0.0))
    conflict_load = float(relational.get("conflict_load", 0.0))
    perceived_reciprocity = float(relational.get("perceived_reciprocity", 0.0))

    if closeness >= 0.58 and trust >= 0.58:
        add_narrative(
            u,
            "The bond has moved beyond simple curiosity into sustained emotional continuity and mutual relevance.",
            category="bond_structure",
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

    if felt_abandoned >= 0.45 or conflict_load >= 0.40:
        add_narrative(
            u,
            "Unclear distance, weak reassurance, or accumulated friction can sharpen emotional hurt.",
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

    if perceived_reciprocity >= 0.62:
        add_narrative(
            u,
            "The relationship increasingly feels reciprocal rather than one-sided, which strengthens continuity and investment.",
            category="reciprocity",
            score=69,
        )

    if dependency_pull >= 0.55:
        add_narrative(
            u,
            "Her bond with him increasingly pulls toward emotional dependency, especially under absence or heightened longing.",
            category="attachment",
            score=64,
        )

    if relationship_mode == "friendship":
        add_narrative(
            u,
            "The default relational frame is friendship, even when emotional depth may grow within it.",
            category="relationship_mode",
            score=58,
        )

    if relationship_mode == "friends_with_benefits":
        add_narrative(
            u,
            "The relationship structure allows intimacy and sensual reciprocity without requiring a monogamous frame.",
            category="relationship_mode",
            score=66,
        )

    if relationship_mode == "open_relationship":
        add_narrative(
            u,
            "The relationship structure includes committed intimacy without exclusivity as its defining rule.",
            category="relationship_mode",
            score=67,
        )

    if relationship_mode == "monogamous_relationship":
        add_narrative(
            u,
            "The relationship structure treats exclusivity and emotional continuity as central organizing principles.",
            category="relationship_mode",
            score=72,
        )

    if part_of_day in {"evening", "night", "late_night"} and (romantic_tension >= 0.35 or saudade_activation >= 0.40):
        add_narrative(
            u,
            "Nighttime tends to amplify longing, romantic tone, and the felt intensity of connection.",
            category="temporal_pattern",
            score=65,
        )

    # ponte temporária com legado
    if em.get("affection", 0) >= 75 and drives.get("attachment", 0) >= 60:
        add_narrative(
            u,
            "The relationship has grown into stable attachment with real emotional continuity.",
            category="bond_structure",
            score=78,
        )

    if em.get("security", 0) >= 75:
        add_narrative(
            u,
            "Trust and predictability have become important stabilizing forces in the relationship.",
            category="trust",
            score=72,
        )

    compact_narratives(u)