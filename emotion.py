import math
import random
from typing import Dict, Any, Optional

from utils import now_ms, clamp, day_key


# =========================
# HELPERS
# =========================

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def move_toward(current: float, target: float, speed: float) -> float:
    return current + (target - current) * speed


def bounded_noise(scale: float = 0.01) -> float:
    return random.uniform(-scale, scale)


def max_step(delta: float, limit: float = 0.08) -> float:
    return max(-limit, min(limit, delta))


def move_toward_limited(current: float, target: float, speed: float, step_limit: float) -> float:
    raw = (target - current) * speed
    return clamp01(current + max_step(raw, step_limit))


def recency_weight(elapsed_min: float, persistence: float = 0.03) -> float:
    return math.exp(-persistence * elapsed_min)


def _safe_text(text: Optional[str]) -> str:
    return (text or "").strip()


def _get_temporal_context(u: Dict[str, Any]) -> Dict[str, Any]:
    return u.get("temporal_context", {}) or {}


def _part_of_day_bonus(u: Dict[str, Any]) -> Dict[str, float]:
    tc = _get_temporal_context(u)
    part = tc.get("part_of_day", "")
    is_night = bool(tc.get("is_night", False))

    night_bonus = 0.0
    late_night_bonus = 0.0
    reflective_bonus = 0.0

    if part in {"evening", "night"}:
        night_bonus = 0.08
        reflective_bonus = 0.04
    elif part == "late_night":
        night_bonus = 0.10
        late_night_bonus = 0.08
        reflective_bonus = 0.06
    elif part == "dawn":
        reflective_bonus = 0.03
    elif part == "morning":
        reflective_bonus = 0.01

    if is_night and night_bonus < 0.08:
        night_bonus = 0.08

    return {
        "night_bonus": night_bonus,
        "late_night_bonus": late_night_bonus,
        "reflective_bonus": reflective_bonus,
        "part_of_day": part,
    }


def _user_trait(u: Dict[str, Any], name: str, default: float = 0.0) -> float:
    traits = u.get("user_profile", {}).get("traits", {}) or {}
    try:
        return clamp01(float(traits.get(name, default)))
    except Exception:
        return default


def _relationship_mode(u: Dict[str, Any]) -> str:
    return (
        u.get("relationship_structure", {}).get("current_mode")
        or "friendship"
    )


def _relationship_mode_bias(u: Dict[str, Any]) -> Dict[str, float]:
    mode = _relationship_mode(u)

    if mode == "friends_with_benefits":
        return {
            "closeness_bias": 0.08,
            "sensual_bias": 0.20,
            "security_bias": 0.04,
        }
    if mode == "open_relationship":
        return {
            "closeness_bias": 0.10,
            "sensual_bias": 0.16,
            "security_bias": 0.06,
        }
    if mode == "monogamous_relationship":
        return {
            "closeness_bias": 0.16,
            "sensual_bias": 0.12,
            "security_bias": 0.14,
        }

    return {
        "closeness_bias": 0.03,
        "sensual_bias": 0.02,
        "security_bias": 0.03,
    }


def _recent_chat_window(u: Dict[str, Any], limit: int = 12) -> list[Dict[str, Any]]:
    chat = u.get("chat", []) or []
    return chat[-limit:]


def _last_user_message_before_current(u: Dict[str, Any], current_text: str) -> Optional[Dict[str, Any]]:
    chat = u.get("chat", []) or []
    current_text = _safe_text(current_text)

    for item in reversed(chat):
        if item.get("role") != "user":
            continue
        if _safe_text(item.get("text")) == current_text:
            continue
        return item
    return None


def _last_assistant_message(u: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    chat = u.get("chat", []) or []
    for item in reversed(chat):
        if item.get("role") == "assistant":
            return item
    return None


def _estimate_sentence_count(text: str) -> int:
    if not text:
        return 0
    pieces = [p for p in text.replace("?", ".").replace("!", ".").split(".") if p.strip()]
    return max(1, len(pieces))


def _estimate_message_features(text: str) -> Dict[str, float]:
    text = _safe_text(text)
    text_len = len(text)
    word_count = len([w for w in text.split() if w.strip()])
    sentence_count = _estimate_sentence_count(text)

    question_marks = text.count("?")
    exclamations = text.count("!")
    commas = text.count(",")
    ellipses = text.count("...")

    complexity = clamp01(
        (min(word_count, 80) / 80.0) * 0.55 +
        (min(sentence_count, 8) / 8.0) * 0.25 +
        (min(commas + ellipses, 6) / 6.0) * 0.20
    )

    expressiveness = clamp01(
        (min(question_marks, 3) / 3.0) * 0.35 +
        (min(exclamations, 3) / 3.0) * 0.20 +
        (min(text_len, 240) / 240.0) * 0.45
    )

    brevity = 1.0 - clamp01(text_len / 120.0)

    return {
        "text_len": float(text_len),
        "word_count": float(word_count),
        "sentence_count": float(sentence_count),
        "complexity": complexity,
        "expressiveness": expressiveness,
        "brevity": brevity,
        "question_density": clamp01(question_marks / 3.0),
    }


def _compute_return_signal(u: Dict[str, Any]) -> float:
    now = now_ms()
    last_event = int(u.get("last_event_ts_ms", now))
    idle_min = max(0.0, (now - last_event) / 60000.0)

    if idle_min < 45:
        return 0.0
    if idle_min < 180:
        return clamp01((idle_min - 45) / 180.0)
    return 0.75


def _compute_recent_reciprocity(u: Dict[str, Any]) -> float:
    window = _recent_chat_window(u, limit=10)
    if not window:
        return 0.5

    user_count = sum(1 for m in window if m.get("role") == "user")
    assistant_count = sum(1 for m in window if m.get("role") == "assistant")
    total = max(1, user_count + assistant_count)

    balance = 1.0 - abs(user_count - assistant_count) / total
    return clamp01(0.30 + balance * 0.70)


def _compute_contextual_affection(
    u: Dict[str, Any],
    text_features: Dict[str, float],
    modality: str,
) -> float:
    v2 = u.get("emotion_v2", {})
    stable = v2.get("stable", {})
    medium = v2.get("medium", {})

    relationship = _relationship_mode_bias(u)
    reciprocity = _compute_recent_reciprocity(u)

    affection = (
        0.08
        + text_features["complexity"] * 0.22
        + text_features["expressiveness"] * 0.12
        + float(stable.get("attachment", 0.30)) * 0.16
        + float(medium.get("felt_considered", 0.40)) * 0.12
        + relationship["closeness_bias"]
        + reciprocity * 0.10
    )

    if modality == "audio":
        affection += 0.08

    return clamp01(affection)


def _compute_contextual_engagement(
    u: Dict[str, Any],
    text_features: Dict[str, float],
    modality: str,
) -> float:
    tc_bonus = _part_of_day_bonus(u)
    reciprocity = _compute_recent_reciprocity(u)

    engagement = (
        0.20
        + text_features["expressiveness"] * 0.28
        + text_features["complexity"] * 0.18
        + text_features["question_density"] * 0.16
        + reciprocity * 0.14
        + tc_bonus["reflective_bonus"] * 0.5
    )

    if modality == "audio":
        engagement += 0.10

    return clamp01(engagement)


def _compute_contextual_depth(
    u: Dict[str, Any],
    text_features: Dict[str, float],
    modality: str,
) -> float:
    tc_bonus = _part_of_day_bonus(u)
    sensitive_trait = _user_trait(u, "sensivel", 0.0)
    intense_trait = _user_trait(u, "intenso", 0.0)

    depth = (
        0.04
        + text_features["complexity"] * 0.40
        + text_features["question_density"] * 0.10
        + tc_bonus["reflective_bonus"] * 0.80
        + sensitive_trait * 0.10
        + intense_trait * 0.08
    )

    if modality == "audio":
        depth += 0.04

    return clamp01(depth)


def _compute_contextual_sensuality(
    u: Dict[str, Any],
    text_features: Dict[str, float],
    modality: str,
) -> float:
    v2 = u.get("emotion_v2", {})
    stable = v2.get("stable", {})
    medium = v2.get("medium", {})
    fast = v2.get("fast", {})

    relationship = _relationship_mode_bias(u)
    tc_bonus = _part_of_day_bonus(u)
    sexual_trait = _user_trait(u, "sexual", 0.0)
    romantic_trait = _user_trait(u, "romantico", 0.0)

    sensuality = (
        0.00
        + float(fast.get("sensual_tension", 0.0)) * 0.26
        + float(fast.get("sexual_desire", 0.0)) * 0.20
        + float(medium.get("sexual_openness", 0.0)) * 0.18
        + float(stable.get("sexual_discovery", 0.0)) * 0.16
        + relationship["sensual_bias"]
        + sexual_trait * 0.10
        + romantic_trait * 0.05
        + tc_bonus["night_bonus"] * 0.45
        + text_features["expressiveness"] * 0.04
    )

    if modality == "audio":
        sensuality += 0.03

    return clamp01(sensuality)


def _compute_contextual_coldness(
    u: Dict[str, Any],
    text_features: Dict[str, float],
    modality: str,
) -> float:
    now = now_ms()
    last_event = int(u.get("last_event_ts_ms", now))
    idle_min = max(0.0, (now - last_event) / 60000.0)

    shortness = text_features["brevity"]
    low_expression = 1.0 - text_features["expressiveness"]
    low_complexity = 1.0 - text_features["complexity"]

    coldness = (
        0.02
        + shortness * 0.22
        + low_expression * 0.16
        + low_complexity * 0.14
        + min(idle_min / 720.0, 1.0) * 0.10
    )

    if modality == "audio":
        coldness -= 0.04

    return clamp01(coldness)


def _compute_contextual_goodbye_quality(
    u: Dict[str, Any],
    text_features: Dict[str, float],
) -> float:
    status = u.get("status", {}) or {}
    if status.get("away_announced"):
        return 0.75

    return clamp01(
        0.05
        + text_features["complexity"] * 0.08
        + text_features["expressiveness"] * 0.05
    )


def _compute_contextual_absence_justification_quality(u: Dict[str, Any]) -> float:
    status = u.get("status", {}) or {}

    if status.get("working") or status.get("duty"):
        return 0.75
    if status.get("activity"):
        return 0.18

    return 0.08


def _compute_felt_prioritized_signal(
    u: Dict[str, Any],
    text_features: Dict[str, float],
    modality: str,
) -> float:
    relationship = _relationship_mode_bias(u)
    reciprocity = _compute_recent_reciprocity(u)

    score = (
        0.16
        + text_features["complexity"] * 0.18
        + text_features["expressiveness"] * 0.12
        + reciprocity * 0.20
        + relationship["closeness_bias"] * 0.80
    )

    if modality == "audio":
        score += 0.08

    return clamp01(score)


def _ensure_relational_state(u: Dict[str, Any]):
    if "relational_state" in u:
        return

    u["relational_state"] = {
        "attachment": 0.35,
        "trust": 0.55,
        "longing": 0.10,
        "playfulness": 0.16,
        "emotional_tension": 0.08,
        "sexual_tension": 0.05,
        "stability": 0.55,
        "perceived_reciprocity": 0.50,
        "felt_safety": 0.55,
        "dependency_pull": 0.12,
        "conflict_load": 0.05,
        "relational_closeness": 0.35,
    }


def _sync_relational_state(u: Dict[str, Any]):
    ensure_emotional_engine_v2(u)
    _ensure_relational_state(u)

    v2 = u["emotion_v2"]
    rel = u["relational_state"]

    stable = v2["stable"]
    medium = v2["medium"]
    fast = v2["fast"]

    rel["attachment"] = stable["attachment"]
    rel["trust"] = stable["relational_security"]
    rel["longing"] = fast["saudade_activation"]
    rel["playfulness"] = u.get("current_mood", {}).get("playfulness", 0.16)
    rel["emotional_tension"] = clamp01(
        fast["romantic_tension"] * 0.55 +
        medium["felt_abandoned"] * 0.25 +
        medium["affection_need"] * 0.20
    )
    rel["sexual_tension"] = clamp01(
        fast["sensual_tension"] * 0.65 +
        fast["sexual_desire"] * 0.35
    )
    rel["stability"] = clamp01(
        stable["relational_security"] * 0.65 +
        medium["felt_considered"] * 0.20 -
        medium["felt_abandoned"] * 0.15
    )
    rel["perceived_reciprocity"] = clamp01(
        medium["felt_considered"] * 0.60 +
        stable["relational_security"] * 0.20 +
        _compute_recent_reciprocity(u) * 0.20
    )
    rel["felt_safety"] = clamp01(
        stable["relational_security"] * 0.70 +
        medium["felt_considered"] * 0.20 -
        medium["felt_abandoned"] * 0.10
    )
    rel["dependency_pull"] = clamp01(
        medium["affection_need"] * 0.45 +
        fast["saudade_activation"] * 0.35 +
        stable["attachment"] * 0.20
    )
    rel["conflict_load"] = clamp01(
        medium["felt_abandoned"] * 0.55 +
        (u.get("drives", {}).get("annoyance", 0) / 100.0) * 0.45
    )
    rel["relational_closeness"] = clamp01(
        stable["attachment"] * 0.38 +
        stable["relational_security"] * 0.32 +
        medium["felt_considered"] * 0.18 +
        fast["romantic_tension"] * 0.12
    )


# =========================
# EMOTIONAL ENGINE V2
# =========================

def ensure_emotional_engine_v2(u: Dict[str, Any]):
    if "emotion_v2" not in u:
        u["emotion_v2"] = {
            "stable": {
                "attachment": 0.35,
                "relational_security": 0.55,
                "sexual_discovery": 0.05,
            },
            "medium": {
                "boredom": 0.15,
                "affection_need": 0.20,
                "felt_considered": 0.50,
                "felt_abandoned": 0.05,
                "sexual_openness": 0.10,
            },
            "fast": {
                "sexual_desire": 0.05,
                "saudade_activation": 0.0,
                "romantic_tension": 0.0,
                "sensual_tension": 0.0,
            },
            "recent_events": [],
            "pending_topics": [],
            "pending_emotional_hooks": [],
            "pending_sensual_hooks": [],
            "last_analysis": {},
            "time_markers": {
                "last_local_date": "",
                "last_part_of_day": "",
            },
            "updated_ts_ms": now_ms(),
        }

    _ensure_relational_state(u)


def _append_recent_event(u: Dict[str, Any], event: Dict[str, Any], max_events: int = 60):
    ensure_emotional_engine_v2(u)
    state = u["emotion_v2"]
    item = dict(event)
    item["ts_ms"] = item.get("ts_ms", now_ms())
    state["recent_events"].append(item)
    state["recent_events"] = state["recent_events"][-max_events:]


def prune_recent_events(state: Dict[str, Any], now_ts_ms: Optional[int] = None, max_events: int = 60):
    now_ts_ms = now_ts_ms or now_ms()
    kept = []

    for ev in state.get("recent_events", []):
        elapsed_min = max(0.0, (now_ts_ms - ev.get("ts_ms", now_ts_ms)) / 60000.0)
        if recency_weight(elapsed_min, persistence=0.03) >= 0.01:
            kept.append(ev)

    state["recent_events"] = kept[-max_events:]


def analyze_user_message(u: Dict[str, Any], text: str, modality: str) -> Dict[str, float]:
    ensure_emotional_engine_v2(u)

    text = _safe_text(text)
    features = _estimate_message_features(text)

    affection = _compute_contextual_affection(u, features, modality)
    engagement = _compute_contextual_engagement(u, features, modality)
    depth = _compute_contextual_depth(u, features, modality)
    sensuality = _compute_contextual_sensuality(u, features, modality)
    coldness = _compute_contextual_coldness(u, features, modality)
    goodbye_quality = _compute_contextual_goodbye_quality(u, features)
    absence_justification_quality = _compute_contextual_absence_justification_quality(u)
    return_signal = _compute_return_signal(u)
    felt_prioritized_signal = _compute_felt_prioritized_signal(u, features, modality)

    analysis = {
        "affection": clamp01(affection),
        "engagement": clamp01(engagement),
        "depth": clamp01(depth),
        "sensuality": clamp01(sensuality),
        "coldness": clamp01(coldness),
        "goodbye_quality": clamp01(goodbye_quality),
        "absence_justification_quality": clamp01(absence_justification_quality),
        "return_signal": clamp01(return_signal),
        "felt_prioritized_signal": clamp01(felt_prioritized_signal),
    }

    u["emotion_v2"]["last_analysis"] = dict(analysis)
    return analysis


def register_emotional_event(
    u: Dict[str, Any],
    event_type: str,
    intensity: float = 0.5,
    ts_ms: Optional[int] = None,
    meta: Optional[Dict[str, Any]] = None,
):
    ensure_emotional_engine_v2(u)
    state = u["emotion_v2"]

    meta = meta or {}
    ts_ms = ts_ms or now_ms()
    intensity = clamp01(float(intensity))

    affection = clamp01(float(meta.get("affection", 0.0)) * intensity)
    engagement = clamp01(float(meta.get("engagement", 0.0)) * intensity)
    depth = clamp01(float(meta.get("depth", 0.0)) * intensity)
    sensuality = clamp01(float(meta.get("sensuality", 0.0)) * intensity)
    coldness = clamp01(float(meta.get("coldness", 0.0)) * intensity)
    goodbye_quality = clamp01(float(meta.get("goodbye_quality", 0.0)) * intensity)
    absence_justification_quality = clamp01(float(meta.get("absence_justification_quality", 0.0)) * intensity)
    return_signal = clamp01(float(meta.get("return_signal", 0.0)) * intensity)
    felt_prioritized_signal = clamp01(float(meta.get("felt_prioritized_signal", 0.0)) * intensity)

    absence = 0.0
    rupture = 0.0
    consideration = 0.0
    romantic_signal = 0.0
    sexual_signal = sensuality

    if event_type == "affectionate_message":
        consideration = clamp01(
            felt_prioritized_signal * 0.60 +
            engagement * 0.20 +
            affection * 0.20
        )
        romantic_signal = clamp01(
            affection * 0.45 +
            depth * 0.35 +
            sensuality * 0.20
        )

    elif event_type == "cold_message":
        rupture = clamp01(
            coldness * 0.55 +
            (1.0 - felt_prioritized_signal) * 0.20
        )
        consideration = clamp01(felt_prioritized_signal * 0.20)

    elif event_type == "sensual_message":
        consideration = clamp01(felt_prioritized_signal * 0.35 + engagement * 0.15)
        romantic_signal = clamp01(affection * 0.25 + depth * 0.25 + sensuality * 0.50)

    elif event_type == "goodbye_with_care":
        consideration = clamp01(
            goodbye_quality * 0.45 +
            felt_prioritized_signal * 0.35 +
            affection * 0.20
        )
        romantic_signal = clamp01(affection * 0.30 + depth * 0.20)

    elif event_type == "goodbye_cold":
        rupture = clamp01(coldness * 0.40 + (1.0 - goodbye_quality) * 0.35)
        consideration = clamp01(goodbye_quality * 0.10)

    elif event_type == "absence_justified":
        absence = clamp01(0.20 + (1.0 - absence_justification_quality) * 0.10)
        consideration = clamp01(absence_justification_quality * 0.55 + felt_prioritized_signal * 0.20)

    elif event_type == "absence_unjustified":
        absence = clamp01(0.42 + coldness * 0.18)
        rupture = clamp01(0.25 + coldness * 0.20)

    elif event_type == "return_after_absence":
        consideration = clamp01(return_signal * 0.45 + felt_prioritized_signal * 0.25)
        romantic_signal = clamp01(affection * 0.20 + depth * 0.20)
        absence = 0.0

    elif event_type == "deep_emotional_exchange":
        consideration = clamp01(
            engagement * 0.20 +
            depth * 0.45 +
            felt_prioritized_signal * 0.25 +
            affection * 0.10
        )
        romantic_signal = clamp01(affection * 0.25 + depth * 0.55 + sensuality * 0.20)

    elif event_type == "night_tick":
        consideration = 0.0
        romantic_signal = 0.0
        absence = clamp01(0.04 * intensity)

    else:
        consideration = clamp01(
            felt_prioritized_signal * 0.45 +
            engagement * 0.20 +
            goodbye_quality * 0.15
        )
        romantic_signal = clamp01(
            depth * 0.40 +
            affection * 0.35 +
            sensuality * 0.25
        )
        rupture = clamp01(coldness * 0.35)
        absence = clamp01((1.0 - absence_justification_quality) * 0.10)

    event = {
        "kind": event_type,
        "ts_ms": ts_ms,
        "affection": affection,
        "consideration": clamp01(consideration),
        "absence": clamp01(absence),
        "rupture": clamp01(rupture),
        "sexual_signal": clamp01(sexual_signal),
        "romantic_signal": clamp01(romantic_signal),
        "meta": {
            "intensity": intensity,
            "engagement": engagement,
            "depth": depth,
            "coldness": coldness,
            "goodbye_quality": goodbye_quality,
            "absence_justification_quality": absence_justification_quality,
            "return_signal": return_signal,
            "felt_prioritized_signal": felt_prioritized_signal,
            **meta
        }
    }

    _append_recent_event(u, event, max_events=60)
    prune_recent_events(state, now_ts_ms=ts_ms, max_events=60)


def register_emotional_events_from_analysis(
    u: Dict[str, Any],
    analysis: Dict[str, float],
    user_text: str,
    modality: str = "text",
):
    ensure_emotional_engine_v2(u)

    affection = analysis["affection"]
    engagement = analysis["engagement"]
    depth = analysis["depth"]
    sensuality = analysis["sensuality"]
    coldness = analysis["coldness"]
    goodbye_quality = analysis["goodbye_quality"]
    absence_justification_quality = analysis["absence_justification_quality"]
    return_signal = analysis["return_signal"]
    felt_prioritized_signal = analysis["felt_prioritized_signal"]

    base_meta = {
        "affection": affection,
        "engagement": engagement,
        "depth": depth,
        "sensuality": sensuality,
        "coldness": coldness,
        "goodbye_quality": goodbye_quality,
        "absence_justification_quality": absence_justification_quality,
        "return_signal": return_signal,
        "felt_prioritized_signal": felt_prioritized_signal,
        "modality": modality,
        "text_len": len(_safe_text(user_text)),
    }

    if affection >= 0.34:
        register_emotional_event(
            u,
            "affectionate_message",
            intensity=max(affection, 0.34),
            meta=base_meta,
        )

    if coldness >= 0.38:
        register_emotional_event(
            u,
            "cold_message",
            intensity=max(coldness, 0.38),
            meta=base_meta,
        )

    if sensuality >= 0.30:
        register_emotional_event(
            u,
            "sensual_message",
            intensity=max(sensuality, 0.30),
            meta=base_meta,
        )

    if goodbye_quality >= 0.55 and felt_prioritized_signal >= 0.30:
        register_emotional_event(
            u,
            "goodbye_with_care",
            intensity=goodbye_quality,
            meta=base_meta,
        )
    elif goodbye_quality >= 0.35 and coldness >= 0.35:
        register_emotional_event(
            u,
            "goodbye_cold",
            intensity=max(goodbye_quality, coldness),
            meta=base_meta,
        )

    if absence_justification_quality >= 0.55:
        register_emotional_event(
            u,
            "absence_justified",
            intensity=absence_justification_quality,
            meta=base_meta,
        )
    elif coldness >= 0.45 and felt_prioritized_signal <= 0.22:
        register_emotional_event(
            u,
            "absence_unjustified",
            intensity=max(coldness, 0.45),
            meta=base_meta,
        )

    if return_signal >= 0.35:
        register_emotional_event(
            u,
            "return_after_absence",
            intensity=return_signal,
            meta=base_meta,
        )

    if depth >= 0.38 and engagement >= 0.42:
        register_emotional_event(
            u,
            "deep_emotional_exchange",
            intensity=max(depth, engagement),
            meta=base_meta,
        )

    if all(
        x < 0.28 for x in [
            affection, coldness, sensuality,
            goodbye_quality, absence_justification_quality,
            return_signal, depth
        ]
    ):
        register_emotional_event(
            u,
            "affectionate_message",
            intensity=0.18,
            meta=base_meta,
        )


def register_emotional_event_v2(
    u: Dict[str, Any],
    event_type: str,
    intensity: float = 0.5,
    ts_ms: Optional[int] = None,
    meta: Optional[Dict[str, Any]] = None,
):
    register_emotional_event(
        u=u,
        event_type=event_type,
        intensity=intensity,
        ts_ms=ts_ms,
        meta=meta,
    )


def register_user_message_v2(u: Dict[str, Any], text: str):
    ensure_emotional_engine_v2(u)

    analysis = analyze_user_message(u, text, modality="text")
    register_emotional_events_from_analysis(
        u,
        analysis=analysis,
        user_text=text,
        modality="text",
    )


def register_absence_event_v2(u: Dict[str, Any], idle_min: float):
    ensure_emotional_engine_v2(u)

    if idle_min < 30:
        return

    intensity = clamp01((idle_min - 30) / 240.0)
    register_emotional_event(
        u,
        event_type="absence_unjustified",
        intensity=intensity,
        ts_ms=now_ms(),
        meta={
            "affection": 0.0,
            "engagement": 0.0,
            "depth": 0.0,
            "sensuality": 0.0,
            "coldness": 0.25,
            "goodbye_quality": 0.0,
            "absence_justification_quality": 0.0,
            "return_signal": 0.0,
            "felt_prioritized_signal": 0.0,
        }
    )


def _weighted_event_sums(state: Dict[str, Any], now_ts_ms: int) -> Dict[str, float]:
    sums = {
        "affection": 0.0,
        "consideration": 0.0,
        "absence": 0.0,
        "rupture": 0.0,
        "sexual_signal": 0.0,
        "romantic_signal": 0.0,
    }

    for ev in state.get("recent_events", []):
        elapsed_min = max(0.0, (now_ts_ms - ev.get("ts_ms", now_ts_ms)) / 60000.0)
        w = recency_weight(elapsed_min, persistence=0.03)

        sums["affection"] += ev.get("affection", 0.0) * w
        sums["consideration"] += ev.get("consideration", 0.0) * w
        sums["absence"] += ev.get("absence", 0.0) * w
        sums["rupture"] += ev.get("rupture", 0.0) * w
        sums["sexual_signal"] += ev.get("sexual_signal", 0.0) * w
        sums["romantic_signal"] += ev.get("romantic_signal", 0.0) * w

    return sums


def recompute_emotional_state_v2(u: Dict[str, Any]):
    ensure_emotional_engine_v2(u)
    state = u["emotion_v2"]
    now = now_ms()

    prune_recent_events(state, now_ts_ms=now)

    stable = state["stable"]
    medium = state["medium"]
    fast = state["fast"]

    idle_min = max(0.0, (now - u.get("last_event_ts_ms", now)) / 60000.0)
    weighted = _weighted_event_sums(state, now)

    ctx = _part_of_day_bonus(u)
    night_bonus = ctx["night_bonus"]
    late_night_bonus = ctx["late_night_bonus"]

    relationship = _relationship_mode_bias(u)
    sensitive_trait = _user_trait(u, "sensivel", 0.0)
    affectionate_trait = _user_trait(u, "afetuoso", 0.0)
    erratic_trait = _user_trait(u, "erratico", 0.0)
    reserved_trait = _user_trait(u, "reservado", 0.0)
    intense_trait = _user_trait(u, "intenso", 0.0)

    weighted_recent_sensuality = weighted["sexual_signal"]
    weighted_positive_intimacy = (
        weighted["consideration"] * 0.45
        + weighted["romantic_signal"] * 0.35
        + weighted["affection"] * 0.20
    )
    weighted_emotional_intimacy = (
        weighted["consideration"] * 0.50
        + weighted["romantic_signal"] * 0.30
        + weighted["affection"] * 0.20
    )

    target_attachment = (
        0.28
        + weighted["affection"] * 0.10
        + weighted["romantic_signal"] * 0.06
        + weighted["absence"] * 0.04
        - weighted["rupture"] * 0.06
        + relationship["closeness_bias"] * 0.40
        + affectionate_trait * 0.04
    )
    stable["attachment"] = move_toward_limited(
        stable["attachment"],
        clamp01(target_attachment + bounded_noise(0.005)),
        speed=0.015,
        step_limit=0.025,
    )

    target_relational_security = (
        0.50
        + weighted["consideration"] * 0.18
        + weighted["affection"] * 0.08
        - weighted["rupture"] * 0.20
        - weighted["absence"] * 0.06
        + relationship["security_bias"]
        - erratic_trait * 0.04
        - reserved_trait * 0.02
    )
    stable["relational_security"] = move_toward_limited(
        stable["relational_security"],
        clamp01(target_relational_security + bounded_noise(0.005)),
        speed=0.02,
        step_limit=0.025,
    )

    target_sexual_discovery = clamp01(
        stable["sexual_discovery"]
        + weighted_recent_sensuality * 0.04
        + weighted_emotional_intimacy * 0.02
        + relationship["sensual_bias"] * 0.05
    )
    stable["sexual_discovery"] = move_toward_limited(
        stable["sexual_discovery"],
        clamp01(target_sexual_discovery + bounded_noise(0.003)),
        speed=0.03,
        step_limit=0.02,
    )

    attachment = stable["attachment"]
    security = stable["relational_security"]
    sexual_discovery = stable["sexual_discovery"]

    target_boredom = (
        0.10
        + min(idle_min / 240.0, 1.0) * 0.45
        - weighted["affection"] * 0.10
        - weighted["romantic_signal"] * 0.06
    )
    medium["boredom"] = move_toward_limited(
        medium["boredom"],
        clamp01(target_boredom + bounded_noise(0.012)),
        speed=0.12,
        step_limit=0.05,
    )

    target_affection_need = (
        0.14
        + attachment * 0.35
        + weighted["absence"] * 0.25
        - weighted["affection"] * 0.30
        + night_bonus
        + sensitive_trait * 0.05
        + intense_trait * 0.04
    )
    medium["affection_need"] = move_toward_limited(
        medium["affection_need"],
        clamp01(target_affection_need + bounded_noise(0.015)),
        speed=0.18,
        step_limit=0.06,
    )

    target_felt_considered = (
        0.34
        + security * 0.30
        + weighted["consideration"] * 0.35
        + weighted["affection"] * 0.08
        - weighted["rupture"] * 0.20
    )
    medium["felt_considered"] = move_toward_limited(
        medium["felt_considered"],
        clamp01(target_felt_considered + bounded_noise(0.01)),
        speed=0.20,
        step_limit=0.06,
    )

    target_felt_abandoned = (
        0.03
        + weighted["absence"] * 0.28
        + weighted["rupture"] * 0.35
        - weighted["consideration"] * 0.22
        - security * 0.12
        + late_night_bonus
        + erratic_trait * 0.05
    )
    medium["felt_abandoned"] = move_toward_limited(
        medium["felt_abandoned"],
        clamp01(target_felt_abandoned + bounded_noise(0.012)),
        speed=0.16,
        step_limit=0.06,
    )

    target_sexual_openness = (
        0.04
        + security * 0.30
        + medium["felt_considered"] * 0.20
        + attachment * 0.15
        + weighted_positive_intimacy * 0.20
        - medium["felt_abandoned"] * 0.22
        + relationship["sensual_bias"] * 0.40
    )
    medium["sexual_openness"] = move_toward_limited(
        medium["sexual_openness"],
        clamp01(target_sexual_openness + bounded_noise(0.01)),
        speed=0.10,
        step_limit=0.05,
    )

    affection_need = medium["affection_need"]
    felt_abandoned = medium["felt_abandoned"]
    sexual_openness = medium["sexual_openness"]

    target_saudade_activation = (
        0.02
        + weighted["absence"] * 0.35
        + affection_need * 0.28
        + felt_abandoned * 0.18
        - weighted["affection"] * 0.20
        + night_bonus
    )
    fast["saudade_activation"] = move_toward_limited(
        fast["saudade_activation"],
        clamp01(target_saudade_activation + bounded_noise(0.02)),
        speed=0.22,
        step_limit=0.08,
    )

    target_romantic_tension = (
        0.01
        + weighted["romantic_signal"] * 0.40
        + attachment * 0.16
        + affection_need * 0.15
        + night_bonus * 0.40
        + relationship["closeness_bias"] * 0.20
    )
    fast["romantic_tension"] = move_toward_limited(
        fast["romantic_tension"],
        clamp01(target_romantic_tension + bounded_noise(0.02)),
        speed=0.20,
        step_limit=0.08,
    )

    target_sensual_tension = (
        0.00
        + weighted_recent_sensuality * 0.42
        + sexual_openness * 0.24
        + night_bonus * 0.20
        + relationship["sensual_bias"] * 0.20
    )
    fast["sensual_tension"] = move_toward_limited(
        fast["sensual_tension"],
        clamp01(target_sensual_tension + bounded_noise(0.02)),
        speed=0.18,
        step_limit=0.08,
    )

    target_sexual_desire = (
        0.05
        + attachment * 0.18
        + affection_need * 0.16
        + weighted_recent_sensuality * 0.32
        + sexual_discovery * 0.22
        + night_bonus * 0.12
        - felt_abandoned * 0.10
        + relationship["sensual_bias"] * 0.18
    )
    fast["sexual_desire"] = move_toward_limited(
        fast["sexual_desire"],
        clamp01(target_sexual_desire + bounded_noise(0.018)),
        speed=0.24,
        step_limit=0.09,
    )

    state["updated_ts_ms"] = now
    update_legacy_emotion_bridge(u)
    recompute_current_mood(u)
    _sync_relational_state(u)


def update_emotional_engine_v2(u: Dict[str, Any]):
    ensure_emotional_engine_v2(u)

    state = u["emotion_v2"]
    now = now_ms()
    last = state.get("updated_ts_ms", 0)
    delta_min = (now - last) / 60000.0 if last else 0.0

    if delta_min <= 0:
        return

    idle_min = max(0.0, (now - u.get("last_event_ts_ms", now)) / 60000.0)

    if idle_min >= 30:
        register_absence_event_v2(u, idle_min)

    recompute_emotional_state_v2(u)


def apply_time_update_v2(u: Dict[str, Any]):
    ensure_emotional_engine_v2(u)
    state = u["emotion_v2"]
    tc = _get_temporal_context(u)
    now = now_ms()

    local_date = tc.get("local_date", "")
    part_of_day = tc.get("part_of_day", "")

    markers = state.setdefault("time_markers", {
        "last_local_date": "",
        "last_part_of_day": "",
    })

    last_local_date = markers.get("last_local_date", "")
    last_part = markers.get("last_part_of_day", "")

    if part_of_day in {"evening", "night", "late_night"}:
        changed_day = bool(local_date and local_date != last_local_date)
        entered_night = part_of_day != last_part and part_of_day in {"evening", "night", "late_night"}

        if changed_day or entered_night:
            register_emotional_event(
                u,
                event_type="night_tick",
                intensity=0.25,
                ts_ms=now,
                meta={}
            )

    markers["last_local_date"] = local_date
    markers["last_part_of_day"] = part_of_day

    recompute_emotional_state_v2(u)


def compute_initiative_score_v2(u: Dict[str, Any]) -> float:
    ensure_emotional_engine_v2(u)
    state = u["emotion_v2"]

    medium = state["medium"]
    fast = state["fast"]
    tc = _part_of_day_bonus(u)

    score = (
        medium["affection_need"] * 0.28
        + medium["boredom"] * 0.18
        + fast["saudade_activation"] * 0.22
        + fast["romantic_tension"] * 0.14
        + fast["sensual_tension"] * 0.08
        - medium["felt_abandoned"] * 0.10
        + tc["night_bonus"] * 0.20
    )

    return clamp01(score)


def build_emotion_snapshot_v2(u: Dict[str, Any]) -> Dict[str, Any]:
    ensure_emotional_engine_v2(u)
    state = u["emotion_v2"]

    return {
        "stable": dict(state["stable"]),
        "medium": dict(state["medium"]),
        "fast": dict(state["fast"]),
        "recent_event_count": len(state.get("recent_events", [])),
        "initiative_score": compute_initiative_score_v2(u),
        "updated_ts_ms": state.get("updated_ts_ms", 0),
        "last_analysis": dict(state.get("last_analysis", {})),
        "relational_state": dict(u.get("relational_state", {})),
    }


def get_emotion_v2_snapshot(u: Dict[str, Any]) -> Dict[str, Any]:
    return build_emotion_snapshot_v2(u)


def update_legacy_emotion_bridge(u: Dict[str, Any]):
    ensure_emotional_engine_v2(u)

    if "emotion" not in u:
        u["emotion"] = {
            "affection": 60,
            "missing_you": 10,
            "frustration": 5,
            "security": 70,
            "mood": "neutral",
            "updated_ts_ms": 0,
        }

    v2 = u["emotion_v2"]

    u["emotion"]["affection"] = int(v2["stable"]["attachment"] * 100)
    u["emotion"]["security"] = int(v2["stable"]["relational_security"] * 100)
    u["emotion"]["missing_you"] = int(
        (v2["medium"]["affection_need"] * 0.6 + v2["medium"]["boredom"] * 0.4) * 100
    )
    u["emotion"]["frustration"] = int(v2["medium"]["felt_abandoned"] * 100)
    u["emotion"]["updated_ts_ms"] = now_ms()


# =========================
# CURRENT MOOD
# =========================

def ensure_current_mood(u: Dict[str, Any]):
    if "current_mood" in u:
        return

    u["current_mood"] = {
        "warmth": 0.55,
        "tenderness": 0.30,
        "curiosity": 0.22,
        "playfulness": 0.16,
        "longing": 0.10,
        "distance": 0.06,
        "irritation": 0.05,
        "sadness": 0.04,
        "sensuality": 0.08,
    }


def recompute_current_mood(u: Dict[str, Any]):
    ensure_emotional_engine_v2(u)
    ensure_current_mood(u)

    if "drives" not in u:
        u["drives"] = {
            "loneliness": 20,
            "curiosity": 35,
            "attachment": 35,
            "annoyance": 5,
            "autonomy": 50,
            "desire_for_attention": 25,
            "need_for_space": 10,
            "availability": 80
        }

    v2 = u["emotion_v2"]
    drives = u["drives"]
    mood = u["current_mood"]

    stable = v2["stable"]
    medium = v2["medium"]
    fast = v2["fast"]

    target_warmth = clamp01(
        0.20
        + stable["attachment"] * 0.35
        + stable["relational_security"] * 0.22
        + medium["felt_considered"] * 0.18
        - medium["felt_abandoned"] * 0.18
    )
    mood["warmth"] = move_toward_limited(mood["warmth"], target_warmth, 0.18, 0.07)

    target_tenderness = clamp01(
        0.08
        + medium["affection_need"] * 0.28
        + fast["saudade_activation"] * 0.25
        + stable["attachment"] * 0.18
        - drives["annoyance"] / 100.0 * 0.10
    )
    mood["tenderness"] = move_toward_limited(mood["tenderness"], target_tenderness, 0.18, 0.07)

    target_curiosity = clamp01(
        0.08
        + drives["curiosity"] / 100.0 * 0.42
        + medium["boredom"] * 0.16
    )
    mood["curiosity"] = move_toward_limited(mood["curiosity"], target_curiosity, 0.15, 0.06)

    target_playfulness = clamp01(
        0.04
        + stable["relational_security"] * 0.22
        + fast["romantic_tension"] * 0.12
        - medium["felt_abandoned"] * 0.14
        - drives["annoyance"] / 100.0 * 0.10
    )
    mood["playfulness"] = move_toward_limited(mood["playfulness"], target_playfulness, 0.16, 0.06)

    target_longing = clamp01(
        0.03
        + fast["saudade_activation"] * 0.44
        + medium["affection_need"] * 0.20
        + medium["boredom"] * 0.10
    )
    mood["longing"] = move_toward_limited(mood["longing"], target_longing, 0.20, 0.08)

    target_distance = clamp01(
        0.02
        + drives["need_for_space"] / 100.0 * 0.34
        + medium["felt_abandoned"] * 0.16
        - stable["relational_security"] * 0.12
    )
    mood["distance"] = move_toward_limited(mood["distance"], target_distance, 0.16, 0.06)

    target_irritation = clamp01(
        0.01
        + drives["annoyance"] / 100.0 * 0.45
        + medium["felt_abandoned"] * 0.12
        - medium["felt_considered"] * 0.10
    )
    mood["irritation"] = move_toward_limited(mood["irritation"], target_irritation, 0.18, 0.07)

    target_sadness = clamp01(
        0.01
        + medium["felt_abandoned"] * 0.30
        + fast["saudade_activation"] * 0.18
        - stable["relational_security"] * 0.08
    )
    mood["sadness"] = move_toward_limited(mood["sadness"], target_sadness, 0.16, 0.06)

    target_sensuality = clamp01(
        0.01
        + fast["sensual_tension"] * 0.44
        + fast["sexual_desire"] * 0.26
        + medium["sexual_openness"] * 0.18
    )
    mood["sensuality"] = move_toward_limited(mood["sensuality"], target_sensuality, 0.18, 0.07)


# =========================
# LEGACY SUPPORT
# =========================

def decay_emotions(u: Dict[str, Any]):
    if "emotion" not in u:
        u["emotion"] = {
            "affection": 60,
            "missing_you": 10,
            "frustration": 5,
            "security": 70,
            "mood": "neutral",
            "updated_ts_ms": 0,
        }

    em = u["emotion"]
    now = now_ms()
    last = em.get("updated_ts_ms", 0)
    delta_min = (now - last) / 60000 if last else 0

    if delta_min <= 0:
        return

    em["missing_you"] = clamp(em["missing_you"] + delta_min * 0.06)
    em["frustration"] = clamp(em["frustration"] - delta_min * 0.05)
    em["affection"] = clamp(em["affection"] - delta_min * 0.01)
    em["security"] = clamp(em["security"] - delta_min * 0.01)
    em["updated_ts_ms"] = now

    apply_time_update_v2(u)
    recompute_current_mood(u)


def update_drives_passive(u: Dict[str, Any]):
    ensure_current_mood(u)

    if "drives" not in u:
        u["drives"] = {
            "loneliness": 20,
            "curiosity": 35,
            "attachment": 35,
            "annoyance": 5,
            "autonomy": 50,
            "desire_for_attention": 25,
            "need_for_space": 10,
            "availability": 80
        }

    now = now_ms()
    drives = u["drives"]
    idle_min = max(0, (now - u.get("last_event_ts_ms", now)) / 60000)

    scarcity = u.get("autonomy_settings", {}).get("scarcity_level", 40)
    interruptions = u.get("autonomy_settings", {}).get("interruptions_enabled", True)
    em = u.get("emotion", {})
    tc_bonus = _part_of_day_bonus(u)

    drives["loneliness"] = clamp(drives["loneliness"] + idle_min * 0.04)
    drives["curiosity"] = clamp(drives["curiosity"] + 0.35)
    drives["desire_for_attention"] = clamp(drives["desire_for_attention"] + idle_min * 0.025)
    drives["autonomy"] = clamp(drives["autonomy"] + scarcity * 0.01)

    if scarcity > 40:
        drives["need_for_space"] = clamp(drives["need_for_space"] + 0.4)
    else:
        drives["need_for_space"] = clamp(drives["need_for_space"] - 0.4)

    if not interruptions:
        drives["availability"] = clamp(drives["availability"] - 1.0)
    else:
        drives["availability"] = clamp(drives["availability"] + 0.5)

    if em.get("missing_you", 0) >= 40:
        drives["desire_for_attention"] = clamp(drives["desire_for_attention"] + 0.8)
        drives["attachment"] = clamp(drives["attachment"] + 0.2)

    if tc_bonus["late_night_bonus"] > 0:
        drives["desire_for_attention"] = clamp(drives["desire_for_attention"] + 0.6)

    drives["annoyance"] = clamp(drives["annoyance"] - 0.15)

    apply_time_update_v2(u)
    recompute_current_mood(u)


def update_drives_on_user_message(u: Dict[str, Any], text: str):
    ensure_current_mood(u)

    if "drives" not in u:
        u["drives"] = {
            "loneliness": 20,
            "curiosity": 35,
            "attachment": 35,
            "annoyance": 5,
            "autonomy": 50,
            "desire_for_attention": 25,
            "need_for_space": 10,
            "availability": 80
        }

    drives = u["drives"]
    em = u.get("emotion", {})
    analysis = u.get("emotion_v2", {}).get("last_analysis", {}) or {}

    affection = float(analysis.get("affection", 0.20))
    engagement = float(analysis.get("engagement", 0.30))
    depth = float(analysis.get("depth", 0.10))
    coldness = float(analysis.get("coldness", 0.05))
    prioritized = float(analysis.get("felt_prioritized_signal", 0.20))

    drives["loneliness"] = clamp(drives["loneliness"] - (8 + affection * 8 + engagement * 4))
    drives["desire_for_attention"] = clamp(drives["desire_for_attention"] - (6 + prioritized * 8))
    drives["attachment"] = clamp(drives["attachment"] + (1.5 + affection * 3 + depth * 2))
    drives["availability"] = clamp(drives["availability"] + 5)
    drives["curiosity"] = clamp(drives["curiosity"] + 1.2 + depth * 1.5)
    drives["annoyance"] = clamp(drives["annoyance"] - (2 + affection * 2) + coldness * 2)

    if em:
        em["security"] = clamp(em.get("security", 70) + prioritized * 3)
        em["affection"] = clamp(em.get("affection", 60) + affection * 4)

    recompute_emotional_state_v2(u)
    recompute_current_mood(u)


def reset_daily_push_counter_if_needed(u: Dict[str, Any]):
    tc = _get_temporal_context(u)
    today = tc.get("local_date") or day_key()

    if u.get("pushes_day_key") != today:
        u["pushes_day_key"] = today
        u["pushes_today"] = 0

    op = u.setdefault("operational_state", {})
    if op.get("push_day_key") != today:
        op["push_day_key"] = today
        op["daily_push_count"] = 0