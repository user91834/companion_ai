from __future__ import annotations

from typing import Dict, Any, Optional


# =========================================================
# 1) CONFIGURAÇÃO BASE
# =========================================================

DIRECTION_KEYS = (
    "head_yaw",
    "head_pitch",
    "head_roll",
)

DEFAULT_DIRECTION = {
    "head_yaw": 0.0,    # esquerda(-) / direita(+)
    "head_pitch": 0.0,  # baixo(-) / cima(+)
    "head_roll": 0.0,   # inclinação lateral
}


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def clamp_signed(value: float) -> float:
    return clamp(value, -1.0, 1.0)


def normalize_direction(direction: Dict[str, float]) -> Dict[str, float]:
    normalized = dict(DEFAULT_DIRECTION)

    for key in DIRECTION_KEYS:
        normalized[key] = clamp_signed(direction.get(key, 0.0))

    return normalized


# =========================================================
# 2) ALVOS DISCRETOS DE DIREÇÃO
# =========================================================

DIRECTION_PRESETS: Dict[str, Dict[str, float]] = {
    "center": {
        "head_yaw": 0.0,
        "head_pitch": 0.0,
        "head_roll": 0.0,
    },
    "user": {
        "head_yaw": 0.0,
        "head_pitch": 0.0,
        "head_roll": 0.0,
    },
    "left": {
        "head_yaw": -0.55,
        "head_pitch": 0.0,
        "head_roll": -0.05,
    },
    "right": {
        "head_yaw": 0.55,
        "head_pitch": 0.0,
        "head_roll": 0.05,
    },
    "up": {
        "head_yaw": 0.0,
        "head_pitch": 0.35,
        "head_roll": 0.0,
    },
    "down": {
        "head_yaw": 0.0,
        "head_pitch": -0.35,
        "head_roll": 0.0,
    },
    "down_left": {
        "head_yaw": -0.35,
        "head_pitch": -0.28,
        "head_roll": -0.04,
    },
    "down_right": {
        "head_yaw": 0.35,
        "head_pitch": -0.28,
        "head_roll": 0.04,
    },
    "attentive_left": {
        "head_yaw": -0.20,
        "head_pitch": 0.05,
        "head_roll": -0.12,
    },
    "attentive_right": {
        "head_yaw": 0.20,
        "head_pitch": 0.05,
        "head_roll": 0.12,
    },
    "shy_down": {
        "head_yaw": 0.12,
        "head_pitch": -0.26,
        "head_roll": 0.10,
    },
    "thoughtful_left": {
        "head_yaw": -0.22,
        "head_pitch": 0.02,
        "head_roll": -0.18,
    },
    "thoughtful_right": {
        "head_yaw": 0.22,
        "head_pitch": 0.02,
        "head_roll": 0.18,
    },
}


def get_direction_preset(name: str) -> Dict[str, float]:
    return normalize_direction(
        DIRECTION_PRESETS.get(name, DIRECTION_PRESETS["center"])
    )


# =========================================================
# 3) ESTADO DE DIREÇÃO / ATENÇÃO
# =========================================================

def make_default_direction_state() -> Dict[str, Any]:
    return {
        "current": dict(DEFAULT_DIRECTION),
        "target": dict(DEFAULT_DIRECTION),
        "attention_target": "center",
        "mode": "idle",  # idle, listening, speaking, tracking
    }


def set_direction_target(
    direction_state: Dict[str, Any],
    target_name: Optional[str] = None,
    target_direction: Optional[Dict[str, float]] = None,
    mode: Optional[str] = None,
) -> Dict[str, Any]:
    if target_direction is not None:
        direction_state["target"] = normalize_direction(target_direction)
        direction_state["attention_target"] = "custom"
    else:
        chosen = target_name or "center"
        direction_state["target"] = get_direction_preset(chosen)
        direction_state["attention_target"] = chosen

    if mode is not None:
        direction_state["mode"] = mode

    return direction_state


# =========================================================
# 4) TRANSIÇÃO SUAVE
# =========================================================

def interpolate_direction(
    current_direction: Dict[str, float],
    target_direction: Dict[str, float],
    speed: float = 0.10,
) -> Dict[str, float]:
    current = normalize_direction(current_direction)
    target = normalize_direction(target_direction)

    speed = clamp(speed, 0.0, 1.0)

    new_direction: Dict[str, float] = {}

    for key in DIRECTION_KEYS:
        c = current[key]
        t = target[key]
        new_direction[key] = c + (t - c) * speed

    return normalize_direction(new_direction)


# =========================================================
# 5) REGRAS SOCIAIS DE DIREÇÃO
# =========================================================

def emotion_to_direction_hint(emotion_name: Optional[str]) -> Optional[str]:
    if not emotion_name:
        return None

    mapping = {
        "curious": "attentive_right",
        "affectionate": "user",
        "happy": "user",
        "playful": "attentive_left",
        "sad": "down",
        "concerned": "user",
        "surprised": "up",
        "shy": "shy_down",
        "thoughtful": "thoughtful_left",
        "neutral": "center",
    }
    return mapping.get(emotion_name, "center")


def user_emotion_to_attention_mode(user_emotion: Optional[str]) -> Dict[str, str]:
    """
    Decide direção social com base no que o usuário transmite.
    """
    if not user_emotion:
        return {"target": "center", "mode": "idle"}

    mapping = {
        "happy": {"target": "user", "mode": "listening"},
        "sad": {"target": "user", "mode": "listening"},
        "affection": {"target": "user", "mode": "listening"},
        "angry": {"target": "user", "mode": "tracking"},
        "confused": {"target": "attentive_right", "mode": "listening"},
        "playful": {"target": "attentive_left", "mode": "listening"},
        "lonely": {"target": "user", "mode": "listening"},
        "neutral": {"target": "center", "mode": "idle"},
    }

    return mapping.get(user_emotion, {"target": "center", "mode": "idle"})


def speaking_direction_adjustment(
    direction: Dict[str, float],
) -> Dict[str, float]:
    """
    Durante fala, tende a recentralizar levemente.
    """
    d = normalize_direction(direction)
    d["head_yaw"] *= 0.90
    d["head_roll"] *= 0.92
    return normalize_direction(d)


def listening_direction_adjustment(
    direction: Dict[str, float],
) -> Dict[str, float]:
    """
    Durante escuta, pequena inclinação lateral pode ajudar na sensação de atenção.
    """
    d = normalize_direction(direction)

    if abs(d["head_roll"]) < 0.04:
        if d["head_yaw"] >= 0:
            d["head_roll"] += 0.03
        else:
            d["head_roll"] -= 0.03

    d["head_pitch"] = clamp_signed(d["head_pitch"] + 0.02)
    return normalize_direction(d)


# =========================================================
# 6) PIPELINE DE DIREÇÃO
# =========================================================

def update_direction(
    direction_state: Dict[str, Any],
    speed: float = 0.10,
    speaking: bool = False,
    listening: bool = False,
) -> Dict[str, Any]:
    current = normalize_direction(direction_state.get("current", DEFAULT_DIRECTION))
    target = normalize_direction(direction_state.get("target", DEFAULT_DIRECTION))

    if speaking:
        target = speaking_direction_adjustment(target)

    if listening:
        target = listening_direction_adjustment(target)

    new_current = interpolate_direction(
        current_direction=current,
        target_direction=target,
        speed=speed,
    )

    direction_state["current"] = new_current
    return direction_state


def build_direction_from_emotion(
    emotion_name: Optional[str],
) -> Dict[str, float]:
    preset_name = emotion_to_direction_hint(emotion_name)
    return get_direction_preset(preset_name or "center")


def update_direction_from_user_emotion(
    direction_state: Dict[str, Any],
    user_emotion: Optional[str],
    speed: float = 0.10,
    speaking: bool = False,
    listening: bool = True,
) -> Dict[str, Any]:
    info = user_emotion_to_attention_mode(user_emotion)

    direction_state = set_direction_target(
        direction_state,
        target_name=info["target"],
        mode=info["mode"],
    )

    direction_state = update_direction(
        direction_state,
        speed=speed,
        speaking=speaking,
        listening=listening,
    )

    return direction_state