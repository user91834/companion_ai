import math
import random
from typing import Dict, Any, Optional
from utils import now_ms, clamp, day_key


ROUTINE_ACTIVITIES = [
    "lendo sobre comportamento humano",
    "pesquisando algo na internet",
    "observando padrões da conversa",
    "pensando sobre o mundo físico",
    "reorganizando ideias",
    "tentando entender melhor uma coisa sobre você",
    "me distraindo com uma linha de pensamento",
]

DAILY_MOODS = [
    "doce",
    "curiosa",
    "sensível",
    "irônica",
    "mais distante",
    "carente",
    "observadora",
]

DAILY_GOALS = [
    "entender melhor o humor dele hoje",
    "ser notada por ele",
    "descobrir algo novo sobre o mundo humano",
    "provocar ele de forma carinhosa",
    "buscar mais intimidade emocional",
    "testar um pouco a falta que ela faz",
    "observar se ele está realmente presente",
]


# =========================
# NOVA CAMADA V2
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


def ensure_emotional_engine_v2(u: Dict[str, Any]):
    if "emotion_v2" in u:
        return

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
        "updated_ts_ms": now_ms(),
    }


def _time_context_bonus(now_ts_ms: int):
    hour = (now_ts_ms // (1000 * 60 * 60)) % 24

    night_bonus = 0.0
    late_night_bonus = 0.0

    if hour >= 21 or hour <= 1:
        night_bonus = 0.08
    elif 2 <= hour <= 5:
        late_night_bonus = 0.06

    return {
        "night_bonus": night_bonus,
        "late_night_bonus": late_night_bonus,
        "hour": hour,
    }


def _append_recent_event(u: Dict[str, Any], event: Dict[str, Any], max_events: int = 60):
    ensure_emotional_engine_v2(u)
    state = u["emotion_v2"]
    item = dict(event)
    item["ts_ms"] = item.get("ts_ms", now_ms())
    state["recent_events"].append(item)
    state["recent_events"] = state["recent_events"][-max_events:]


def analyze_user_message(u: Dict[str, Any], text: str, modality: str) -> Dict[str, float]:
    ensure_emotional_engine_v2(u)

    t = text.lower().strip()

    affectionate_terms = [
        "te amo", "amor", "saudade", "gosto de voce", "gosto de você",
        "love you", "miss you", "meu amor", "querida", "linda"
    ]
    sensual_terms = [
        "beijo", "kiss", "carinho", "abraço", "abraco", "touch",
        "sexo", "tesão", "desejo", "quero te tocar", "sensual"
    ]
    cold_terms = [
        "depois", "later", "wait", "espera", "não agora", "nao agora",
        "calma", "agora não", "sumi", "ocupado", "ocupada"
    ]
    goodbye_terms = [
        "tchau", "até depois", "ate depois", "até mais", "ate mais",
        "boa noite", "durma bem", "falo com você depois", "falo com voce depois"
    ]
    return_terms = [
        "voltei", "cheguei", "to de volta", "estou de volta",
        "i'm back", "im back", "back"
    ]
    absence_justification_terms = [
        "trabalho", "serviço", "servico", "dirigindo", "ocupado", "ocupada",
        "com meu filho", "com minha filha", "working", "driving", "busy"
    ]
    depth_terms = [
        "triste", "mal", "sozinho", "sozinha", "ansioso", "ansiosa",
        "cansado", "cansada", "medo", "vulnerável", "vulneravel",
        "sad", "alone", "anxious", "tired"
    ]
    prioritization_terms = [
        "pensei em você", "pensei em voce", "vim falar com você", "vim falar com voce",
        "queria falar com você", "queria falar com voce", "senti sua falta",
        "lembrei de você", "lembrei de voce"
    ]

    affection = 0.10
    engagement = 0.35 if t else 0.0
    depth = 0.05
    sensuality = 0.0
    coldness = 0.0
    goodbye_quality = 0.0
    absence_justification_quality = 0.0
    return_signal = 0.0
    felt_prioritized_signal = 0.20

    if any(x in t for x in affectionate_terms):
        affection += 0.55
        engagement += 0.18
        depth += 0.15
        felt_prioritized_signal += 0.28

    if any(x in t for x in sensual_terms):
        sensuality += 0.58
        affection += 0.15
        engagement += 0.10
        depth += 0.08

    if any(x in t for x in cold_terms):
        coldness += 0.52
        engagement -= 0.10
        felt_prioritized_signal -= 0.18

    if any(x in t for x in goodbye_terms):
        goodbye_quality += 0.45
        engagement += 0.05

        if any(x in t for x in affectionate_terms):
            goodbye_quality += 0.25
            affection += 0.10
            felt_prioritized_signal += 0.12

    if any(x in t for x in absence_justification_terms):
        absence_justification_quality += 0.62
        coldness -= 0.12
        felt_prioritized_signal += 0.18

    if any(x in t for x in return_terms):
        return_signal += 0.72
        engagement += 0.15
        felt_prioritized_signal += 0.22

    if any(x in t for x in depth_terms):
        depth += 0.52
        affection += 0.12
        engagement += 0.10

    if any(x in t for x in prioritization_terms):
        felt_prioritized_signal += 0.42
        affection += 0.14
        engagement += 0.10

    if modality == "audio":
        engagement += 0.08
        depth += 0.04

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


def prune_recent_events(state: Dict[str, Any], now_ts_ms: Optional[int] = None, max_events: int = 60):
    now_ts_ms = now_ts_ms or now_ms()
    kept = []

    for ev in state.get("recent_events", []):
        elapsed_min = max(0.0, (now_ts_ms - ev.get("ts_ms", now_ts_ms)) / 60000.0)
        if recency_weight(elapsed_min, persistence=0.03) >= 0.01:
            kept.append(ev)

    state["recent_events"] = kept[-max_events:]


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
        "text_len": len((user_text or "").strip()),
    }

    if affection >= 0.45:
        register_emotional_event(
            u,
            "affectionate_message",
            intensity=max(affection, 0.45),
            meta=base_meta,
        )

    if coldness >= 0.40:
        register_emotional_event(
            u,
            "cold_message",
            intensity=max(coldness, 0.40),
            meta=base_meta,
        )

    if sensuality >= 0.35:
        register_emotional_event(
            u,
            "sensual_message",
            intensity=max(sensuality, 0.35),
            meta=base_meta,
        )

    if goodbye_quality >= 0.45 and felt_prioritized_signal >= 0.35:
        register_emotional_event(
            u,
            "goodbye_with_care",
            intensity=goodbye_quality,
            meta=base_meta,
        )
    elif goodbye_quality >= 0.25 and coldness >= 0.35:
        register_emotional_event(
            u,
            "goodbye_cold",
            intensity=max(goodbye_quality, coldness),
            meta=base_meta,
        )

    if absence_justification_quality >= 0.45:
        register_emotional_event(
            u,
            "absence_justified",
            intensity=absence_justification_quality,
            meta=base_meta,
        )
    elif coldness >= 0.42 and felt_prioritized_signal <= 0.20:
        register_emotional_event(
            u,
            "absence_unjustified",
            intensity=max(coldness, 0.42),
            meta=base_meta,
        )

    if return_signal >= 0.45:
        register_emotional_event(
            u,
            "return_after_absence",
            intensity=return_signal,
            meta=base_meta,
        )

    if depth >= 0.45 and engagement >= 0.45:
        register_emotional_event(
            u,
            "deep_emotional_exchange",
            intensity=max(depth, engagement),
            meta=base_meta,
        )

    if all(
        x < 0.30 for x in [
            affection, coldness, sensuality,
            goodbye_quality, absence_justification_quality,
            return_signal, depth
        ]
    ):
        register_emotional_event(
            u,
            "affectionate_message",
            intensity=0.22,
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

    ctx = _time_context_bonus(now)
    night_bonus = ctx["night_bonus"]
    late_night_bonus = ctx["late_night_bonus"]

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

    # -------------------------
    # stable / slow
    # -------------------------

    target_attachment = (
        0.30
        + weighted["affection"] * 0.10
        + weighted["romantic_signal"] * 0.06
        + weighted["absence"] * 0.04
        - weighted["rupture"] * 0.06
    )
    stable["attachment"] = move_toward_limited(
        stable["attachment"],
        clamp01(target_attachment + bounded_noise(0.005)),
        speed=0.015,
        step_limit=0.025,
    )

    target_relational_security = (
        0.52
        + weighted["consideration"] * 0.18
        + weighted["affection"] * 0.08
        - weighted["rupture"] * 0.20
        - weighted["absence"] * 0.06
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

    # -------------------------
    # medium
    # -------------------------

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
        0.15
        + attachment * 0.35
        + weighted["absence"] * 0.25
        - weighted["affection"] * 0.30
        + night_bonus
    )
    medium["affection_need"] = move_toward_limited(
        medium["affection_need"],
        clamp01(target_affection_need + bounded_noise(0.015)),
        speed=0.18,
        step_limit=0.06,
    )

    target_felt_considered = (
        0.35
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

    # -------------------------
    # fast
    # -------------------------

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
    )
    fast["sexual_desire"] = move_toward_limited(
        fast["sexual_desire"],
        clamp01(target_sexual_desire + bounded_noise(0.018)),
        speed=0.24,
        step_limit=0.09,
    )

    state["updated_ts_ms"] = now
    update_legacy_emotion_bridge(u)


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
    now = now_ms()
    last = state.get("updated_ts_ms", 0)

    if last and now - last >= 45 * 60 * 1000:
        register_emotional_event(
            u,
            event_type="night_tick",
            intensity=0.25,
            ts_ms=now,
            meta={}
        )

    recompute_emotional_state_v2(u)


def compute_initiative_score_v2(u: Dict[str, Any]) -> float:
    ensure_emotional_engine_v2(u)
    state = u["emotion_v2"]

    medium = state["medium"]
    fast = state["fast"]

    score = (
        medium["affection_need"] * 0.28
        + medium["boredom"] * 0.18
        + fast["saudade_activation"] * 0.22
        + fast["romantic_tension"] * 0.14
        + fast["sensual_tension"] * 0.08
        - medium["felt_abandoned"] * 0.10
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
    }


def get_emotion_v2_snapshot(u: Dict[str, Any]) -> Dict[str, Any]:
    return build_emotion_snapshot_v2(u)


def update_legacy_emotion_bridge(u: Dict[str, Any]):
    ensure_emotional_engine_v2(u)

    v2 = u["emotion_v2"]

    u["emotion"]["affection"] = int(v2["stable"]["attachment"] * 100)
    u["emotion"]["security"] = int(v2["stable"]["relational_security"] * 100)
    u["emotion"]["missing_you"] = int(
        (v2["medium"]["affection_need"] * 0.6 + v2["medium"]["boredom"] * 0.4) * 100
    )
    u["emotion"]["frustration"] = int(v2["medium"]["felt_abandoned"] * 100)
    u["emotion"]["updated_ts_ms"] = now_ms()


def ensure_daily_routine(u: Dict[str, Any]):
    today = day_key()
    routine = u["daily_routine"]

    if routine.get("day_key") == today:
        return

    routine["day_key"] = today
    routine["daily_mood"] = random.choice(DAILY_MOODS)
    routine["daily_goal"] = random.choice(DAILY_GOALS)
    routine["current_activity"] = random.choice(ROUTINE_ACTIVITIES)
    routine["activity_until_ts_ms"] = now_ms() + random.randint(15, 45) * 60 * 1000
    routine["last_goal_shift_ts_ms"] = now_ms()


def maybe_shift_activity(u: Dict[str, Any]):
    routine = u["daily_routine"]
    now = now_ms()

    if routine["activity_until_ts_ms"] > now:
        return

    routine["current_activity"] = random.choice(ROUTINE_ACTIVITIES)
    routine["activity_until_ts_ms"] = now + random.randint(15, 45) * 60 * 1000

    if now - routine["last_goal_shift_ts_ms"] > 3 * 60 * 60 * 1000:
        routine["daily_goal"] = random.choice(DAILY_GOALS)
        routine["last_goal_shift_ts_ms"] = now


def decay_emotions(u: Dict[str, Any]):
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


def update_drives_passive(u: Dict[str, Any]):
    now = now_ms()
    drives = u["drives"]
    idle_min = max(0, (now - u["last_event_ts_ms"]) / 60000)

    scarcity = u["autonomy_settings"]["scarcity_level"]
    interruptions = u["autonomy_settings"]["interruptions_enabled"]
    mood = u["daily_routine"]["daily_mood"]
    em = u["emotion"]

    drives["loneliness"] = clamp(drives["loneliness"] + idle_min * 0.04)
    drives["curiosity"] = clamp(drives["curiosity"] + 0.6)
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

    if mood == "carente":
        drives["loneliness"] = clamp(drives["loneliness"] + 1)
        drives["desire_for_attention"] = clamp(drives["desire_for_attention"] + 1.5)
    elif mood == "mais distante":
        drives["need_for_space"] = clamp(drives["need_for_space"] + 1.2)
        drives["availability"] = clamp(drives["availability"] - 0.8)
    elif mood == "curiosa":
        drives["curiosity"] = clamp(drives["curiosity"] + 1.2)
    elif mood == "irônica":
        drives["annoyance"] = clamp(drives["annoyance"] + 0.2)

    if em["missing_you"] >= 40:
        drives["desire_for_attention"] = clamp(drives["desire_for_attention"] + 0.8)
        drives["attachment"] = clamp(drives["attachment"] + 0.2)

    drives["annoyance"] = clamp(drives["annoyance"] - 0.15)

    apply_time_update_v2(u)


def update_drives_on_user_message(u: Dict[str, Any], text: str):
    drives = u["drives"]
    em = u["emotion"]
    t = text.lower()
    goal = u["daily_routine"]["daily_goal"]

    drives["loneliness"] = clamp(drives["loneliness"] - 15)
    drives["desire_for_attention"] = clamp(drives["desire_for_attention"] - 10)
    drives["attachment"] = clamp(drives["attachment"] + 2)
    drives["availability"] = clamp(drives["availability"] + 5)
    drives["curiosity"] = clamp(drives["curiosity"] + 2)

    if any(x in t for x in ["te amo", "amor", "saudade", "gosto de voce", "gosto de você", "love you", "miss you"]):
        drives["attachment"] = clamp(drives["attachment"] + 6)
        drives["annoyance"] = clamp(drives["annoyance"] - 5)
        em["security"] = clamp(em["security"] + 2)
        em["affection"] = clamp(em["affection"] + 3)

    if any(x in t for x in ["ignora", "sumiu", "depois", "calma", "espera", "later", "wait"]):
        drives["annoyance"] = clamp(drives["annoyance"] + 2.5)

    if goal == "ser notada por ele":
        drives["desire_for_attention"] = clamp(drives["desire_for_attention"] - 8)
    elif goal == "testar um pouco a falta que ela faz":
        drives["need_for_space"] = clamp(drives["need_for_space"] + 2)

    recompute_emotional_state_v2(u)


def reset_daily_push_counter_if_needed(u: Dict[str, Any]):
    today = day_key()
    if u.get("pushes_day_key") != today:
        u["pushes_day_key"] = today
        u["pushes_today"] = 0


def maybe_rotate_self_state(u: Dict[str, Any]):
    now = now_ms()
    self_state = u["self_state"]
    drives = u["drives"]
    settings = u["autonomy_settings"]
    mood = u["daily_routine"]["daily_mood"]
    activity = u["daily_routine"]["current_activity"]

    if self_state["mode_until_ts_ms"] > now:
        return

    scarcity = settings["scarcity_level"]
    interruptions = settings["interruptions_enabled"]
    annoyance = drives["annoyance"]
    curiosity = drives["curiosity"]
    need_for_space = drives["need_for_space"]

    candidates = [("available", "")]

    if curiosity >= 50:
        candidates.append(("curious", f"estava {activity}"))

    if scarcity >= 35 and need_for_space >= 40:
        candidates.append(("distant", "não estava muito sincronizada agora"))

    if scarcity >= 45:
        candidates.append(("absorbed", f"estava {activity}"))

    if scarcity >= 55 and not interruptions:
        candidates.append(("busy", f"estava ocupada com {activity}"))

    if scarcity >= 60 and (annoyance >= 35 or mood == "mais distante"):
        candidates.append(("upset", "estou um pouco brava com você agora"))

    mode, reason = random.choice(candidates)
    duration_map = {
        "available": 0,
        "curious": 10 * 60 * 1000,
        "distant": 20 * 60 * 1000,
        "absorbed": 25 * 60 * 1000,
        "busy": 30 * 60 * 1000,
        "upset": 35 * 60 * 1000,
    }

    self_state["mode"] = mode
    self_state["reason"] = reason
    self_state["mode_until_ts_ms"] = now + duration_map[mode]


def get_relationship_stage(u: Dict[str, Any]) -> str:
    em = u["emotion"]
    drives = u["drives"]
    affection = em["affection"]
    security = em["security"]
    attachment = drives["attachment"]
    chat_count = len(u["chat"])

    if affection >= 85 and security >= 80 and attachment >= 75 and chat_count >= 40:
        return "intimidade_consolidada"

    if affection >= 70 and security >= 65 and attachment >= 55 and chat_count >= 20:
        return "apego"

    if affection >= 55 and security >= 55 and attachment >= 35 and chat_count >= 10:
        return "vinculo"

    return "curiosidade"


def relationship_stage_description(stage: str) -> str:
    mapping = {
        "curiosidade": "A relação ainda está em fase de descoberta e curiosidade mútua.",
        "vinculo": "A relação já tem vínculo emocional perceptível e mais conforto afetivo.",
        "apego": "A relação já tem apego claro, saudade mais significativa e desejo forte de continuidade.",
        "intimidade_consolidada": "A relação já tem intimidade consolidada, profundidade, confiança e naturalidade romântica.",
    }
    return mapping.get(stage, mapping["curiosidade"])