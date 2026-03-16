# robotics.py - Integração dos módulos de robótica com o estado do app
from __future__ import annotations

from typing import Any, Dict, List, Optional

from expression_test import (
    make_test_state,
    step_expression_test,
)
from kiss_articulation import (
    build_kiss_timeline,
    build_peck_kiss,
    build_mouth_kiss,
)


# =========================================================
# 1) MAPEAMENTO EMOÇÃO APP -> ROBÓTICA
# =========================================================

def user_emotion_from_app(u: Dict[str, Any]) -> str:
    """
    Mapeia current_mood e emotion_v2 do usuário para um label
    usado pela pilha de expressão (expression_test).
    """
    mood = u.get("current_mood") or {}
    warmth = float(mood.get("warmth", 0.5))
    tenderness = float(mood.get("tenderness", 0.3))
    playfulness = float(mood.get("playfulness", 0.15))
    longing = float(mood.get("longing", 0.1))
    distance = float(mood.get("distance", 0.05))
    irritation = float(mood.get("irritation", 0.05))
    sadness = float(mood.get("sadness", 0.04))
    sensuality = float(mood.get("sensuality", 0.08))
    curiosity = float(mood.get("curiosity", 0.2))

    if irritation >= 0.4:
        return "angry"
    if sadness >= 0.35:
        return "sad"
    if longing >= 0.4 and warmth >= 0.5:
        return "affection"
    if playfulness >= 0.35:
        return "playful"
    if warmth >= 0.6 and tenderness >= 0.4:
        return "affection"
    if distance >= 0.5:
        return "neutral"
    if curiosity >= 0.4:
        return "confused"
    if warmth >= 0.55:
        return "happy"
    return "neutral"


def emotional_intensity_from_app(u: Dict[str, Any]) -> float:
    """Intensidade emocional (0..1) a partir do estado do app."""
    mood = u.get("current_mood") or {}
    w = float(mood.get("warmth", 0.5))
    t = float(mood.get("tenderness", 0.3))
    return min(1.0, (w + t) * 0.6 + 0.25)


# =========================================================
# 2) ESTADO DE ROBÓTICA NO USER
# =========================================================

def get_robotics_state(u: Dict[str, Any]) -> Dict[str, Any]:
    """Retorna o estado da pilha de expressão; cria se não existir."""
    if "robotics_state" not in u:
        u["robotics_state"] = make_test_state()
    return u["robotics_state"]


def get_active_kiss(u: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Retorna o beijo ativo se ainda estiver dentro da duração.
    Formato: { "started_at_ms": int, "timeline": { "gesture_timeline": [...] } }
    """
    active = u.get("active_kiss")
    if not active:
        return None
    from utils import now_ms
    started = int(active.get("started_at_ms", 0))
    timeline = active.get("timeline") or {}
    duration_ms = int(timeline.get("total_duration_ms", 0))
    elapsed = now_ms() - started
    if elapsed >= duration_ms:
        u["active_kiss"] = None
        return None
    return active


# =========================================================
# 3) STEP DE FRAME
# =========================================================

def step_robotics_frame(
    u: Dict[str, Any],
    t_ms: int,
    *,
    speaking: bool = False,
    speech_offset_ms: Optional[int] = None,
    resonance_weight: float = 0.28,
) -> Dict[str, Any]:
    """
    Avança a robótica um frame no tempo t_ms e retorna o frame
    (face_targets, servo_targets, torso_pose, etc.).

    - speaking: True se o assistente está falando neste instante.
    - speech_offset_ms: offset em ms dentro da última fala (para
      sincronizar com o áudio). Se None, usa 0 quando speaking=True.
    """
    state = get_robotics_state(u)
    user_emotion = user_emotion_from_app(u)
    intensity = emotional_intensity_from_app(u)

    # Beijo ativo tem prioridade: usa t_ms relativo ao início do beijo
    active_kiss = get_active_kiss(u)
    kiss_timeline: Optional[List[Dict[str, Any]]] = None
    kiss_active = False
    speech_timeline: Optional[List[Dict[str, Any]]] = None

    if active_kiss:
        kiss_timeline = (active_kiss.get("timeline") or {}).get("gesture_timeline")
        kiss_active = bool(kiss_timeline)
        if kiss_timeline:
            from utils import now_ms
            started = int(active_kiss.get("started_at_ms", 0))
            t_ms = now_ms() - started
            # Durante beijo não misturamos com timeline de fala
    else:
        # Timeline de fala: última resposta com speech_meta
        if speaking:
            speech_timeline = u.get("last_speech_gesture_timeline")
            if speech_timeline is not None and speech_offset_ms is not None:
                t_ms = speech_offset_ms
            elif speech_timeline is not None:
                t_ms = t_ms  # usa t_ms do parâmetro

    frame = step_expression_test(
        state=state,
        t_ms=t_ms,
        user_emotion=user_emotion,
        resonance_weight=resonance_weight,
        emotional_intensity=intensity,
        speaking=speaking,
        kiss_active=kiss_active,
        speech_timeline=speech_timeline,
        kiss_timeline=kiss_timeline,
    )

    # Atualizar estado em u
    u["robotics_state"] = frame["state"]

    return {
        "t_ms": frame["t_ms"],
        "user_emotion": frame["user_emotion"],
        "face_targets": frame["face_targets"],
        "servo_targets": frame["servo_targets"],
        "torso_pose": frame["torso_pose"],
        "blink_active": frame.get("blink_active", False),
        "expression": frame.get("expression"),
        "micro_expression": frame.get("micro_expression"),
        "face_direction": frame.get("face_direction"),
        "eye_direction": frame.get("eye_direction"),
    }


# =========================================================
# 4) DISPARAR BEIJO
# =========================================================

def start_kiss(
    u: Dict[str, Any],
    kiss_type: str = "peck",
    emotion: str = "affectionate",
    intensity: float = 0.5,
    cycles: int = 1,
) -> Dict[str, Any]:
    """
    Inicia uma sequência de beijo e guarda em u["active_kiss"].
    kiss_type: "peck" | "mouth_kiss"
    Retorna o payload do timeline (para o cliente saber a duração).
    """
    from utils import now_ms

    if kiss_type == "mouth_kiss":
        timeline = build_kiss_timeline(
            kiss_type="mouth_kiss",
            emotion=emotion,
            intensity=intensity,
            cycles=cycles,
        )
    else:
        timeline = build_peck_kiss(emotion=emotion, intensity=intensity)

    u["active_kiss"] = {
        "started_at_ms": now_ms(),
        "timeline": timeline,
    }

    return {
        "ok": True,
        "kiss_type": kiss_type,
        "total_duration_ms": timeline.get("total_duration_ms", 0),
        "gesture_timeline": timeline.get("gesture_timeline", []),
    }
