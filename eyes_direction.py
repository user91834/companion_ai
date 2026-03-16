from __future__ import annotations

from typing import Dict, Any, Optional


# =========================================================
# 1) CONFIGURAÇÃO BASE
# =========================================================

EYE_KEYS = (
    "eye_yaw",              # esquerda(-) / direita(+)
    "eye_pitch",            # baixo(-) / cima(+)
    "upper_eyelid_offset",  # ajuste relativo da pálpebra superior
    "lower_eyelid_offset",  # ajuste relativo da pálpebra inferior
    "pupil_size",           # 0.0 pequena / 1.0 grande
)

DEFAULT_EYE_DIRECTION = {
    "eye_yaw": 0.0,
    "eye_pitch": 0.0,
    "upper_eyelid_offset": 0.0,
    "lower_eyelid_offset": 0.0,
    "pupil_size": 0.5,
}


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def clamp_signed(value: float) -> float:
    return clamp(value, -1.0, 1.0)


def clamp01(value: float) -> float:
    return clamp(value, 0.0, 1.0)


def normalize_eye_direction(direction: Dict[str, float]) -> Dict[str, float]:
    normalized = dict(DEFAULT_EYE_DIRECTION)

    for key in EYE_KEYS:
        value = direction.get(key, DEFAULT_EYE_DIRECTION[key])

        if key in ("eye_yaw", "eye_pitch", "upper_eyelid_offset", "lower_eyelid_offset"):
            normalized[key] = clamp_signed(value)
        else:
            normalized[key] = clamp01(value)

    return normalized


# =========================================================
# 2) PRESETS DE OLHAR
# =========================================================

EYE_DIRECTION_PRESETS: Dict[str, Dict[str, float]] = {
    "center": {
        "eye_yaw": 0.0,
        "eye_pitch": 0.0,
        "upper_eyelid_offset": 0.0,
        "lower_eyelid_offset": 0.0,
        "pupil_size": 0.5,
    },
    "left": {
        "eye_yaw": -0.75,
        "eye_pitch": 0.0,
        "upper_eyelid_offset": 0.0,
        "lower_eyelid_offset": 0.0,
        "pupil_size": 0.5,
    },
    "right": {
        "eye_yaw": 0.75,
        "eye_pitch": 0.0,
        "upper_eyelid_offset": 0.0,
        "lower_eyelid_offset": 0.0,
        "pupil_size": 0.5,
    },
    "up": {
        "eye_yaw": 0.0,
        "eye_pitch": 0.75,
        "upper_eyelid_offset": -0.22,
        "lower_eyelid_offset": -0.04,
        "pupil_size": 0.5,
    },
    "down": {
        "eye_yaw": 0.0,
        "eye_pitch": -0.75,
        "upper_eyelid_offset": 0.18,
        "lower_eyelid_offset": 0.10,
        "pupil_size": 0.5,
    },
    "up_left": {
        "eye_yaw": -0.65,
        "eye_pitch": 0.60,
        "upper_eyelid_offset": -0.18,
        "lower_eyelid_offset": -0.04,
        "pupil_size": 0.5,
    },
    "up_right": {
        "eye_yaw": 0.65,
        "eye_pitch": 0.60,
        "upper_eyelid_offset": -0.18,
        "lower_eyelid_offset": -0.04,
        "pupil_size": 0.5,
    },
    "down_left": {
        "eye_yaw": -0.65,
        "eye_pitch": -0.60,
        "upper_eyelid_offset": 0.16,
        "lower_eyelid_offset": 0.08,
        "pupil_size": 0.5,
    },
    "down_right": {
        "eye_yaw": 0.65,
        "eye_pitch": -0.60,
        "upper_eyelid_offset": 0.16,
        "lower_eyelid_offset": 0.08,
        "pupil_size": 0.5,
    },
    "user": {
        "eye_yaw": 0.0,
        "eye_pitch": 0.0,
        "upper_eyelid_offset": 0.0,
        "lower_eyelid_offset": 0.0,
        "pupil_size": 0.52,
    },
    "shy_down": {
        "eye_yaw": 0.15,
        "eye_pitch": -0.45,
        "upper_eyelid_offset": 0.12,
        "lower_eyelid_offset": 0.06,
        "pupil_size": 0.56,
    },
    "thoughtful_left": {
        "eye_yaw": -0.35,
        "eye_pitch": 0.05,
        "upper_eyelid_offset": 0.00,
        "lower_eyelid_offset": 0.00,
        "pupil_size": 0.48,
    },
    "thoughtful_right": {
        "eye_yaw": 0.35,
        "eye_pitch": 0.05,
        "upper_eyelid_offset": 0.00,
        "lower_eyelid_offset": 0.00,
        "pupil_size": 0.48,
    },
}


def get_eye_direction_preset(name: str) -> Dict[str, float]:
    return normalize_eye_direction(
        EYE_DIRECTION_PRESETS.get(name, EYE_DIRECTION_PRESETS["center"])
    )


# =========================================================
# 3) ACOPLAMENTO PÁLPEBRA <-> OLHAR VERTICAL
# =========================================================

def eyelid_offsets_from_eye_pitch(
    eye_pitch: float,
    upper_follow: float = 0.28,
    lower_follow: float = 0.14,
) -> Dict[str, float]:
    """
    Gera offsets teóricos de pálpebra baseados no movimento vertical do olho.

    Convenção:
    - eye_pitch > 0 => olhando para cima
    - eye_pitch < 0 => olhando para baixo

    Ideia:
    - olhando para cima: pálpebra superior sobe um pouco
    - olhando para baixo: pálpebra superior desce um pouco
    - pálpebra inferior acompanha menos
    """
    pitch = clamp_signed(eye_pitch)
    upper_follow = clamp01(upper_follow)
    lower_follow = clamp01(lower_follow)

    upper = -pitch * upper_follow
    lower = -pitch * lower_follow

    return {
        "upper_eyelid_offset": clamp_signed(upper),
        "lower_eyelid_offset": clamp_signed(lower),
    }


def apply_vertical_eyelid_coupling(
    base_direction: Dict[str, float],
    upper_follow: float = 0.28,
    lower_follow: float = 0.14,
    blend: float = 1.0,
) -> Dict[str, float]:
    """
    Mistura offsets automáticos de pálpebra com uma direção base.
    """
    direction = normalize_eye_direction(base_direction)
    blend = clamp01(blend)

    offsets = eyelid_offsets_from_eye_pitch(
        eye_pitch=direction["eye_pitch"],
        upper_follow=upper_follow,
        lower_follow=lower_follow,
    )

    direction["upper_eyelid_offset"] = clamp_signed(
        direction["upper_eyelid_offset"] * (1.0 - blend) + offsets["upper_eyelid_offset"] * blend
    )
    direction["lower_eyelid_offset"] = clamp_signed(
        direction["lower_eyelid_offset"] * (1.0 - blend) + offsets["lower_eyelid_offset"] * blend
    )

    return normalize_eye_direction(direction)


# =========================================================
# 4) ESTADO DOS OLHOS
# =========================================================

def make_default_eye_state() -> Dict[str, Any]:
    return {
        "current": dict(DEFAULT_EYE_DIRECTION),
        "target": dict(DEFAULT_EYE_DIRECTION),
        "attention_target": "center",
        "mode": "idle",  # idle, listening, speaking, tracking
    }


def set_eye_target(
    eye_state: Dict[str, Any],
    target_name: Optional[str] = None,
    target_direction: Optional[Dict[str, float]] = None,
    mode: Optional[str] = None,
    use_vertical_eyelid_coupling: bool = True,
) -> Dict[str, Any]:
    if target_direction is not None:
        target = normalize_eye_direction(target_direction)
        eye_state["attention_target"] = "custom"
    else:
        chosen = target_name or "center"
        target = get_eye_direction_preset(chosen)
        eye_state["attention_target"] = chosen

    if use_vertical_eyelid_coupling:
        target = apply_vertical_eyelid_coupling(target)

    eye_state["target"] = target

    if mode is not None:
        eye_state["mode"] = mode

    return eye_state


# =========================================================
# 5) TRANSIÇÃO SUAVE
# =========================================================

def interpolate_eye_direction(
    current_direction: Dict[str, float],
    target_direction: Dict[str, float],
    speed: float = 0.18,
) -> Dict[str, float]:
    current = normalize_eye_direction(current_direction)
    target = normalize_eye_direction(target_direction)
    speed = clamp01(speed)

    new_direction: Dict[str, float] = {}

    for key in EYE_KEYS:
        c = current[key]
        t = target[key]
        new_direction[key] = c + (t - c) * speed

    return normalize_eye_direction(new_direction)


# =========================================================
# 6) REGRAS SOCIAIS DE OLHAR
# =========================================================

def emotion_to_eye_hint(emotion_name: Optional[str]) -> Optional[str]:
    if not emotion_name:
        return None

    mapping = {
        "neutral": "center",
        "curious": "up_right",
        "affectionate": "user",
        "happy": "user",
        "playful": "left",
        "sad": "down",
        "concerned": "user",
        "surprised": "up",
        "shy": "shy_down",
        "thoughtful": "thoughtful_left",
    }
    return mapping.get(emotion_name, "center")


def user_emotion_to_eye_attention(user_emotion: Optional[str]) -> Dict[str, str]:
    if not user_emotion:
        return {"target": "center", "mode": "idle"}

    mapping = {
        "happy": {"target": "user", "mode": "listening"},
        "sad": {"target": "user", "mode": "listening"},
        "affection": {"target": "user", "mode": "listening"},
        "angry": {"target": "user", "mode": "tracking"},
        "confused": {"target": "up_right", "mode": "listening"},
        "playful": {"target": "left", "mode": "listening"},
        "lonely": {"target": "user", "mode": "listening"},
        "neutral": {"target": "center", "mode": "idle"},
    }
    return mapping.get(user_emotion, {"target": "center", "mode": "idle"})


def listening_eye_adjustment(direction: Dict[str, float]) -> Dict[str, float]:
    """
    Durante escuta, recentraliza um pouco e mantém leve foco no usuário.
    """
    d = normalize_eye_direction(direction)
    d["eye_yaw"] *= 0.95
    d["pupil_size"] = clamp01(d["pupil_size"] + 0.02)
    return normalize_eye_direction(d)


def speaking_eye_adjustment(direction: Dict[str, float]) -> Dict[str, float]:
    """
    Durante fala, evita olho excessivamente extremo.
    """
    d = normalize_eye_direction(direction)
    d["eye_yaw"] *= 0.90
    d["eye_pitch"] *= 0.90
    return normalize_eye_direction(d)


# =========================================================
# 7) PUPILA: VALE OU NÃO?
# =========================================================

def suggest_pupil_size(
    valence: float = 0.0,
    arousal: float = 0.3,
    affection: float = 0.4,
    ambient_brightness: Optional[float] = None,
) -> float:
    """
    Sugestão teórica de tamanho de pupila.

    Regras simplificadas:
    - mais arousal => pupila um pouco maior
    - mais affection => pupila um pouco maior
    - brilho ambiente alto => pupila menor
    - brilho ambiente baixo => pupila maior

    ambient_brightness:
    - None = ignora ambiente
    - 0.0 escuro / 1.0 muito claro
    """
    v = clamp_signed(valence)
    a = clamp01(arousal)
    aff = clamp01(affection)

    pupil = 0.50
    pupil += a * 0.18
    pupil += aff * 0.10
    pupil += max(0.0, v) * 0.04

    if ambient_brightness is not None:
        b = clamp01(ambient_brightness)
        pupil -= b * 0.22

    return clamp01(pupil)


# =========================================================
# 8) PIPELINE PRINCIPAL
# =========================================================

def update_eye_direction(
    eye_state: Dict[str, Any],
    speed: float = 0.18,
    speaking: bool = False,
    listening: bool = False,
    use_vertical_eyelid_coupling: bool = True,
) -> Dict[str, Any]:
    current = normalize_eye_direction(eye_state.get("current", DEFAULT_EYE_DIRECTION))
    target = normalize_eye_direction(eye_state.get("target", DEFAULT_EYE_DIRECTION))

    if use_vertical_eyelid_coupling:
        target = apply_vertical_eyelid_coupling(target)

    if speaking:
        target = speaking_eye_adjustment(target)

    if listening:
        target = listening_eye_adjustment(target)

    new_current = interpolate_eye_direction(
        current_direction=current,
        target_direction=target,
        speed=speed,
    )

    eye_state["current"] = new_current
    return eye_state


def build_eye_direction_from_emotion(
    emotion_name: Optional[str],
    use_vertical_eyelid_coupling: bool = True,
) -> Dict[str, float]:
    preset_name = emotion_to_eye_hint(emotion_name)
    direction = get_eye_direction_preset(preset_name or "center")

    if use_vertical_eyelid_coupling:
        direction = apply_vertical_eyelid_coupling(direction)

    return direction


def update_eye_direction_from_user_emotion(
    eye_state: Dict[str, Any],
    user_emotion: Optional[str],
    speed: float = 0.18,
    speaking: bool = False,
    listening: bool = True,
    use_vertical_eyelid_coupling: bool = True,
) -> Dict[str, Any]:
    info = user_emotion_to_eye_attention(user_emotion)

    eye_state = set_eye_target(
        eye_state,
        target_name=info["target"],
        mode=info["mode"],
        use_vertical_eyelid_coupling=use_vertical_eyelid_coupling,
    )

    eye_state = update_eye_direction(
        eye_state,
        speed=speed,
        speaking=speaking,
        listening=listening,
        use_vertical_eyelid_coupling=use_vertical_eyelid_coupling,
    )

    return eye_state