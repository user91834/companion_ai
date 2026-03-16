# facial_controller.py
from __future__ import annotations

from typing import Any, Dict, List, Optional


# =========================================================
# 1) CONFIGURAÇÃO BASE
# =========================================================

FACE_KEYS = [
    # expressão facial
    "brow_left",
    "brow_right",
    "eyelid",
    "cheek_raise",

    # cabeça
    "head_yaw",
    "head_pitch",
    "head_roll",

    # olhos
    "eye_yaw",
    "eye_pitch",
    "upper_eyelid_offset",
    "lower_eyelid_offset",
    "pupil_size",

    # boca / articulação
    "jaw_open",
    "lip_round",
    "lip_spread",
    "lip_press",

    # língua
    "tongue_tip_up",
    "tongue_tip_forward",
    "tongue_tip_lateral",
    "tongue_body_high",
    "tongue_body_front",
    "tongue_mid_arch",
    "tongue_visible",
]

SIGNED_KEYS = {
    "head_yaw",
    "head_pitch",
    "head_roll",
    "eye_yaw",
    "eye_pitch",
    "upper_eyelid_offset",
    "lower_eyelid_offset",
}

DEFAULT_FACE_STATE = {
    "brow_left": 0.5,
    "brow_right": 0.5,
    "eyelid": 0.5,
    "cheek_raise": 0.0,

    "head_yaw": 0.0,
    "head_pitch": 0.0,
    "head_roll": 0.0,

    "eye_yaw": 0.0,
    "eye_pitch": 0.0,
    "upper_eyelid_offset": 0.0,
    "lower_eyelid_offset": 0.0,
    "pupil_size": 0.5,

    "jaw_open": 0.0,
    "lip_round": 0.0,
    "lip_spread": 0.0,
    "lip_press": 0.1,

    "tongue_tip_up": 0.0,
    "tongue_tip_forward": 0.0,
    "tongue_tip_lateral": 0.5,
    "tongue_body_high": 0.0,
    "tongue_body_front": 0.0,
    "tongue_mid_arch": 0.0,
    "tongue_visible": 0.0,
}


DEFAULT_SERVO_CONFIG: Dict[str, Dict[str, Any]] = {
    # expressão facial
    "brow_left": {"min": 0.0, "max": 1.0, "invert": False},
    "brow_right": {"min": 0.0, "max": 1.0, "invert": False},
    "eyelid": {"min": 0.0, "max": 1.0, "invert": False},
    "cheek_raise": {"min": 0.0, "max": 1.0, "invert": False},

    # cabeça
    "head_yaw": {"min": -1.0, "max": 1.0, "invert": False},
    "head_pitch": {"min": -1.0, "max": 1.0, "invert": False},
    "head_roll": {"min": -1.0, "max": 1.0, "invert": False},

    # olhos
    "eye_yaw": {"min": -1.0, "max": 1.0, "invert": False},
    "eye_pitch": {"min": -1.0, "max": 1.0, "invert": False},
    "upper_eyelid_offset": {"min": -1.0, "max": 1.0, "invert": False},
    "lower_eyelid_offset": {"min": -1.0, "max": 1.0, "invert": False},
    "pupil_size": {"min": 0.0, "max": 1.0, "invert": False},

    # boca
    "jaw_open": {"min": 0.0, "max": 1.0, "invert": False},
    "lip_round": {"min": 0.0, "max": 1.0, "invert": False},
    "lip_spread": {"min": 0.0, "max": 1.0, "invert": False},
    "lip_press": {"min": 0.0, "max": 1.0, "invert": False},

    # língua
    "tongue_tip_up": {"min": 0.0, "max": 1.0, "invert": False},
    "tongue_tip_forward": {"min": 0.0, "max": 1.0, "invert": False},
    "tongue_tip_lateral": {"min": 0.0, "max": 1.0, "invert": False},
    "tongue_body_high": {"min": 0.0, "max": 1.0, "invert": False},
    "tongue_body_front": {"min": 0.0, "max": 1.0, "invert": False},
    "tongue_mid_arch": {"min": 0.0, "max": 1.0, "invert": False},
    "tongue_visible": {"min": 0.0, "max": 1.0, "invert": False},
}


DEFAULT_SAFETY_LIMITS: Dict[str, Dict[str, float]] = {
    "jaw_open": {"min": 0.0, "max": 0.92},
    "lip_round": {"min": 0.0, "max": 0.95},
    "lip_spread": {"min": 0.0, "max": 0.95},
    "lip_press": {"min": 0.0, "max": 0.95},

    "tongue_tip_up": {"min": 0.0, "max": 0.92},
    "tongue_tip_forward": {"min": 0.0, "max": 0.78},
    "tongue_tip_lateral": {"min": 0.20, "max": 0.80},
    "tongue_body_high": {"min": 0.0, "max": 0.92},
    "tongue_body_front": {"min": 0.0, "max": 0.82},
    "tongue_mid_arch": {"min": 0.0, "max": 0.92},
    "tongue_visible": {"min": 0.0, "max": 0.22},

    "head_yaw": {"min": -0.85, "max": 0.85},
    "head_pitch": {"min": -0.65, "max": 0.65},
    "head_roll": {"min": -0.50, "max": 0.50},

    "eye_yaw": {"min": -0.95, "max": 0.95},
    "eye_pitch": {"min": -0.85, "max": 0.85},
    "upper_eyelid_offset": {"min": -0.40, "max": 0.40},
    "lower_eyelid_offset": {"min": -0.30, "max": 0.30},
}


# =========================================================
# 2) UTILITÁRIOS
# =========================================================

def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def clamp01(value: float) -> float:
    return clamp(value, 0.0, 1.0)


def clamp_signed(value: float) -> float:
    return clamp(value, -1.0, 1.0)


def normalize_face_state(state: Optional[Dict[str, float]]) -> Dict[str, float]:
    out = dict(DEFAULT_FACE_STATE)

    if not state:
        return out

    for key in FACE_KEYS:
        value = float(state.get(key, out[key]))
        if key in SIGNED_KEYS:
            out[key] = clamp_signed(value)
        else:
            out[key] = clamp01(value)

    return out


def merge_dict(base: Dict[str, float], updates: Optional[Dict[str, float]]) -> Dict[str, float]:
    out = dict(base)
    if not updates:
        return out
    for key, value in updates.items():
        if key in out:
            out[key] = value
    return out


def lerp(a: float, b: float, t: float) -> float:
    t = clamp01(t)
    return a + (b - a) * t


def weighted_mix(
    base: Dict[str, float],
    overlay: Optional[Dict[str, float]],
    weight: float = 1.0,
    keys: Optional[List[str]] = None,
) -> Dict[str, float]:
    out = dict(base)
    if not overlay:
        return out

    w = clamp01(weight)
    chosen_keys = keys or list(overlay.keys())

    for key in chosen_keys:
        if key not in out or key not in overlay:
            continue
        out[key] = lerp(out[key], overlay[key], w)

    return out


def limit_value_by_key(
    key: str,
    value: float,
    safety_limits: Optional[Dict[str, Dict[str, float]]] = None,
) -> float:
    limits = (safety_limits or DEFAULT_SAFETY_LIMITS).get(key)
    if not limits:
        return value
    return clamp(value, limits["min"], limits["max"])


def apply_safety_limits(
    state: Dict[str, float],
    safety_limits: Optional[Dict[str, Dict[str, float]]] = None,
) -> Dict[str, float]:
    limits = safety_limits or DEFAULT_SAFETY_LIMITS
    out = dict(state)

    for key, value in out.items():
        if key in limits:
            out[key] = clamp(value, limits[key]["min"], limits[key]["max"])

    return normalize_face_state(out)


# =========================================================
# 3) TIMELINE / ARTICULAÇÃO
# =========================================================

def get_timeline_pose_at(
    timeline: Optional[List[Dict[str, Any]]],
    t_ms: int,
) -> Optional[Dict[str, float]]:
    """
    Retorna a pose ativa no instante t_ms.
    Espera itens com:
    - t_ms
    - duration_ms
    - pose
    """
    if not timeline:
        return None

    t_ms = max(0, int(t_ms))

    for item in timeline:
        start = int(item.get("t_ms", 0))
        duration = int(item.get("duration_ms", 0))
        end = start + duration

        if start <= t_ms < end:
            pose = item.get("pose")
            if isinstance(pose, dict):
                return pose

    last_pose = timeline[-1].get("pose")
    if isinstance(last_pose, dict):
        return last_pose

    return None


def build_articulation_pose_from_expression(
    expression: Optional[Dict[str, float]],
) -> Dict[str, float]:
    """
    Converte expressão facial abstrata em pose básica de boca
    quando não há fala nem beijo.
    """
    expr = expression or {}

    mouth_smile = float(expr.get("mouth_smile", 0.0))  # -1..1
    mouth_open = clamp01(float(expr.get("mouth_open", 0.0)))
    cheek_raise = clamp01(float(expr.get("cheek_raise", 0.0)))

    lip_spread = clamp01(max(0.0, mouth_smile) * 0.90 + cheek_raise * 0.12)
    lip_round = clamp01(max(0.0, -mouth_smile) * 0.30)
    lip_press = clamp01(0.12 + max(0.0, -mouth_smile) * 0.08)
    jaw_open = clamp01(mouth_open * 0.80)

    return {
        "jaw_open": jaw_open,
        "lip_round": lip_round,
        "lip_spread": lip_spread,
        "lip_press": lip_press,
        "tongue_tip_up": 0.0,
        "tongue_tip_forward": 0.0,
        "tongue_tip_lateral": 0.5,
        "tongue_body_high": 0.0,
        "tongue_body_front": 0.0,
        "tongue_mid_arch": 0.0,
        "tongue_visible": 0.0,
    }


# =========================================================
# 4) COMPOSIÇÃO DAS CAMADAS
# =========================================================

def compose_base_face(
    expression: Optional[Dict[str, float]] = None,
    direction: Optional[Dict[str, float]] = None,
    eyes: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """
    Junta camadas estáveis:
    - expressão emocional
    - direção do rosto
    - direção dos olhos
    """
    base = dict(DEFAULT_FACE_STATE)

    expression = expression or {}
    direction = direction or {}
    eyes = eyes or {}

    # expressão facial
    base["brow_left"] = clamp01(float(expression.get("brow_left", base["brow_left"])))
    base["brow_right"] = clamp01(float(expression.get("brow_right", base["brow_right"])))
    base["eyelid"] = clamp01(float(expression.get("eyelid", base["eyelid"])))
    base["cheek_raise"] = clamp01(float(expression.get("cheek_raise", base["cheek_raise"])))

    # cabeça
    base["head_yaw"] = clamp_signed(float(direction.get("head_yaw", base["head_yaw"])))
    base["head_pitch"] = clamp_signed(float(direction.get("head_pitch", base["head_pitch"])))

    # soma entre tendência emocional de inclinação e orientação espacial real
    emotional_head_tilt = clamp_signed(float(expression.get("head_tilt", 0.0)))
    direction_head_roll = clamp_signed(float(direction.get("head_roll", 0.0)))
    base["head_roll"] = clamp_signed(direction_head_roll + emotional_head_tilt * 0.55)

    # olhos
    base["eye_yaw"] = clamp_signed(float(eyes.get("eye_yaw", base["eye_yaw"])))
    base["eye_pitch"] = clamp_signed(float(eyes.get("eye_pitch", base["eye_pitch"])))
    base["upper_eyelid_offset"] = clamp_signed(
        float(eyes.get("upper_eyelid_offset", base["upper_eyelid_offset"]))
    )
    base["lower_eyelid_offset"] = clamp_signed(
        float(eyes.get("lower_eyelid_offset", base["lower_eyelid_offset"]))
    )
    base["pupil_size"] = clamp01(float(eyes.get("pupil_size", base["pupil_size"])))

    # boca base derivada da expressão
    articulation = build_articulation_pose_from_expression(expression)
    base = merge_dict(base, articulation)

    return normalize_face_state(base)


def apply_micro_to_face(
    base_face: Dict[str, float],
    micro_expression: Optional[Dict[str, float]] = None,
    micro_weight: float = 1.0,
) -> Dict[str, float]:
    """
    Microexpressão atua principalmente em:
    sobrancelha, pálpebra, bochecha e leve head_roll.
    """
    if not micro_expression:
        return base_face

    keys = [
        "brow_left",
        "brow_right",
        "eyelid",
        "cheek_raise",
        "head_roll",
        "jaw_open",
        "lip_spread",
        "lip_round",
        "lip_press",
    ]

    return weighted_mix(base_face, micro_expression, weight=micro_weight, keys=keys)


def apply_eye_eyelid_coupling(
    face: Dict[str, float],
    upper_weight: float = 0.70,
    lower_weight: float = 0.60,
) -> Dict[str, float]:
    """
    Integra offsets de pálpebra gerados pelo sistema dos olhos
    com a pálpebra facial geral.
    """
    out = dict(face)

    eyelid = out["eyelid"]
    upper = out["upper_eyelid_offset"]
    lower = out["lower_eyelid_offset"]

    # upper positivo = fecha mais
    # upper negativo = abre mais
    eyelid = eyelid + upper * upper_weight + lower * lower_weight * 0.35

    out["eyelid"] = clamp01(eyelid)
    return out


def apply_speech_articulation(
    face: Dict[str, float],
    speech_pose: Optional[Dict[str, float]] = None,
    weight: float = 1.0,
) -> Dict[str, float]:
    if not speech_pose:
        return face

    keys = [
        "jaw_open",
        "lip_round",
        "lip_spread",
        "lip_press",
        "tongue_tip_up",
        "tongue_tip_forward",
        "tongue_tip_lateral",
        "tongue_body_high",
        "tongue_body_front",
        "tongue_mid_arch",
        "tongue_visible",
    ]

    return weighted_mix(face, speech_pose, weight=weight, keys=keys)


def apply_kiss_articulation(
    face: Dict[str, float],
    kiss_pose: Optional[Dict[str, float]] = None,
    weight: float = 1.0,
) -> Dict[str, float]:
    if not kiss_pose:
        return face

    keys = [
        "jaw_open",
        "lip_round",
        "lip_spread",
        "lip_press",
        "tongue_tip_up",
        "tongue_tip_forward",
        "tongue_tip_lateral",
        "tongue_body_high",
        "tongue_body_front",
        "tongue_mid_arch",
        "tongue_visible",
    ]

    return weighted_mix(face, kiss_pose, weight=weight, keys=keys)


# =========================================================
# 5) REGRAS DE PRIORIDADE
# =========================================================

def resolve_articulation_priority(
    face: Dict[str, float],
    speech_pose: Optional[Dict[str, float]] = None,
    kiss_pose: Optional[Dict[str, float]] = None,
    speech_weight: float = 1.0,
    kiss_weight: float = 1.0,
    allow_mix: bool = False,
) -> Dict[str, float]:
    """
    Regra padrão:
    - se há beijo ativo, beijo domina a boca
    - senão, se há fala ativa, fala domina a boca
    - senão, fica a boca derivada da expressão

    allow_mix=True só se você quiser misturar os dois.
    """
    out = dict(face)

    has_speech = speech_pose is not None
    has_kiss = kiss_pose is not None

    if has_kiss and has_speech and allow_mix:
        out = apply_speech_articulation(out, speech_pose, weight=speech_weight * 0.45)
        out = apply_kiss_articulation(out, kiss_pose, weight=kiss_weight)
        return out

    if has_kiss:
        out = apply_kiss_articulation(out, kiss_pose, weight=kiss_weight)
        return out

    if has_speech:
        out = apply_speech_articulation(out, speech_pose, weight=speech_weight)
        return out

    return out


# =========================================================
# 6) COMPOSIÇÃO FINAL
# =========================================================

def compose_face_targets(
    expression: Optional[Dict[str, float]] = None,
    micro_expression: Optional[Dict[str, float]] = None,
    direction: Optional[Dict[str, float]] = None,
    eyes: Optional[Dict[str, float]] = None,
    speech_pose: Optional[Dict[str, float]] = None,
    kiss_pose: Optional[Dict[str, float]] = None,
    micro_weight: float = 1.0,
    speech_weight: float = 1.0,
    kiss_weight: float = 1.0,
    allow_articulation_mix: bool = False,
    safety_limits: Optional[Dict[str, Dict[str, float]]] = None,
) -> Dict[str, float]:
    """
    Pipeline principal do rosto.
    """
    face = compose_base_face(
        expression=expression,
        direction=direction,
        eyes=eyes,
    )

    face = apply_micro_to_face(
        face,
        micro_expression=micro_expression,
        micro_weight=micro_weight,
    )

    face = apply_eye_eyelid_coupling(face)

    face = resolve_articulation_priority(
        face,
        speech_pose=speech_pose,
        kiss_pose=kiss_pose,
        speech_weight=speech_weight,
        kiss_weight=kiss_weight,
        allow_mix=allow_articulation_mix,
    )

    face = apply_safety_limits(face, safety_limits=safety_limits)
    return normalize_face_state(face)


# =========================================================
# 7) CONTROLLER EM TEMPO
# =========================================================

def compose_face_targets_at_time(
    t_ms: int,
    expression: Optional[Dict[str, float]] = None,
    micro_expression: Optional[Dict[str, float]] = None,
    direction: Optional[Dict[str, float]] = None,
    eyes: Optional[Dict[str, float]] = None,
    speech_timeline: Optional[List[Dict[str, Any]]] = None,
    kiss_timeline: Optional[List[Dict[str, Any]]] = None,
    micro_weight: float = 1.0,
    speech_weight: float = 1.0,
    kiss_weight: float = 1.0,
    allow_articulation_mix: bool = False,
    safety_limits: Optional[Dict[str, Dict[str, float]]] = None,
) -> Dict[str, float]:
    speech_pose = get_timeline_pose_at(speech_timeline, t_ms=t_ms)
    kiss_pose = get_timeline_pose_at(kiss_timeline, t_ms=t_ms)

    return compose_face_targets(
        expression=expression,
        micro_expression=micro_expression,
        direction=direction,
        eyes=eyes,
        speech_pose=speech_pose,
        kiss_pose=kiss_pose,
        micro_weight=micro_weight,
        speech_weight=speech_weight,
        kiss_weight=kiss_weight,
        allow_articulation_mix=allow_articulation_mix,
        safety_limits=safety_limits,
    )


# =========================================================
# 8) CONVERSÃO PARA SAÍDA DE SERVO
# =========================================================

def signed_to_unit(value: float) -> float:
    return clamp01((clamp_signed(value) + 1.0) / 2.0)


def unit_to_signed(value: float) -> float:
    return clamp_signed(value * 2.0 - 1.0)


def abstract_value_to_servo_value(
    key: str,
    value: float,
    servo_config: Optional[Dict[str, Dict[str, Any]]] = None,
) -> float:
    config = (servo_config or DEFAULT_SERVO_CONFIG).get(key, {"min": 0.0, "max": 1.0, "invert": False})
    v = float(value)

    if key in SIGNED_KEYS:
        v = signed_to_unit(v)
    else:
        v = clamp01(v)

    if config.get("invert", False):
        v = 1.0 - v

    servo_min = float(config.get("min", 0.0))
    servo_max = float(config.get("max", 1.0))

    # se min/max vierem como faixa assinada (-1..1), respeita isso
    return servo_min + (servo_max - servo_min) * v


def face_targets_to_servo_targets(
    face_targets: Dict[str, float],
    servo_config: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, float]:
    config = servo_config or DEFAULT_SERVO_CONFIG
    out: Dict[str, float] = {}

    for key in FACE_KEYS:
        if key not in face_targets:
            continue
        out[key] = abstract_value_to_servo_value(key, face_targets[key], servo_config=config)

    return out


def face_targets_to_servo_angles(
    face_targets: Dict[str, float],
    angle_config: Optional[Dict[str, Dict[str, float]]] = None,
) -> Dict[str, float]:
    """
    Converte target abstrato para ângulos físicos.
    angle_config esperado:
    {
        "jaw_open": {"min_angle": 10.0, "max_angle": 85.0, "invert": False},
        ...
    }
    """
    out: Dict[str, float] = {}
    if not angle_config:
        return out

    for key, cfg in angle_config.items():
        if key not in face_targets:
            continue

        value = face_targets[key]

        if key in SIGNED_KEYS:
            unit = signed_to_unit(value)
        else:
            unit = clamp01(value)

        if cfg.get("invert", False):
            unit = 1.0 - unit

        min_angle = float(cfg.get("min_angle", 0.0))
        max_angle = float(cfg.get("max_angle", 180.0))

        out[key] = min_angle + (max_angle - min_angle) * unit

    return out


# =========================================================
# 9) ESTADO DO CONTROLLER
# =========================================================

def make_default_controller_state() -> Dict[str, Any]:
    return {
        "last_face_targets": dict(DEFAULT_FACE_STATE),
        "last_servo_targets": {},
        "mode": "idle",
    }


def smooth_face_targets(
    current_targets: Dict[str, float],
    target_targets: Dict[str, float],
    speed: float = 0.18,
) -> Dict[str, float]:
    current = normalize_face_state(current_targets)
    target = normalize_face_state(target_targets)
    speed = clamp01(speed)

    out = {}
    for key in FACE_KEYS:
        out[key] = lerp(current[key], target[key], speed)

    return normalize_face_state(out)


def step_facial_controller(
    controller_state: Dict[str, Any],
    t_ms: int,
    expression: Optional[Dict[str, float]] = None,
    micro_expression: Optional[Dict[str, float]] = None,
    direction: Optional[Dict[str, float]] = None,
    eyes: Optional[Dict[str, float]] = None,
    speech_timeline: Optional[List[Dict[str, Any]]] = None,
    kiss_timeline: Optional[List[Dict[str, Any]]] = None,
    micro_weight: float = 1.0,
    speech_weight: float = 1.0,
    kiss_weight: float = 1.0,
    allow_articulation_mix: bool = False,
    smoothing_speed: float = 0.18,
    servo_config: Optional[Dict[str, Dict[str, Any]]] = None,
    safety_limits: Optional[Dict[str, Dict[str, float]]] = None,
) -> Dict[str, Any]:
    target_face = compose_face_targets_at_time(
        t_ms=t_ms,
        expression=expression,
        micro_expression=micro_expression,
        direction=direction,
        eyes=eyes,
        speech_timeline=speech_timeline,
        kiss_timeline=kiss_timeline,
        micro_weight=micro_weight,
        speech_weight=speech_weight,
        kiss_weight=kiss_weight,
        allow_articulation_mix=allow_articulation_mix,
        safety_limits=safety_limits,
    )

    current_face = normalize_face_state(controller_state.get("last_face_targets"))
    smoothed_face = smooth_face_targets(
        current_targets=current_face,
        target_targets=target_face,
        speed=smoothing_speed,
    )

    servo_targets = face_targets_to_servo_targets(
        smoothed_face,
        servo_config=servo_config,
    )

    controller_state["last_face_targets"] = smoothed_face
    controller_state["last_servo_targets"] = servo_targets

    return {
        "controller_state": controller_state,
        "face_targets": smoothed_face,
        "servo_targets": servo_targets,
    }


# =========================================================
# 10) EXEMPLO DE USO
# =========================================================

if __name__ == "__main__":
    controller_state = make_default_controller_state()

    expression = {
        "brow_left": 0.62,
        "brow_right": 0.60,
        "eyelid": 0.38,
        "mouth_smile": 0.72,
        "mouth_open": 0.05,
        "cheek_raise": 0.55,
        "head_tilt": 0.20,
    }

    micro_expression = {
        "brow_left": 0.63,
        "brow_right": 0.59,
        "eyelid": 0.40,
        "cheek_raise": 0.56,
    }

    direction = {
        "head_yaw": 0.10,
        "head_pitch": 0.03,
        "head_roll": 0.08,
    }

    eyes = {
        "eye_yaw": 0.12,
        "eye_pitch": -0.10,
        "upper_eyelid_offset": 0.06,
        "lower_eyelid_offset": 0.03,
        "pupil_size": 0.55,
    }

    speech_timeline = [
        {
            "t_ms": 0,
            "duration_ms": 120,
            "pose": {
                "jaw_open": 0.18,
                "lip_round": 0.10,
                "lip_spread": 0.40,
                "lip_press": 0.05,
                "tongue_tip_up": 0.10,
                "tongue_tip_forward": 0.08,
                "tongue_tip_lateral": 0.50,
                "tongue_body_high": 0.45,
                "tongue_body_front": 0.55,
                "tongue_mid_arch": 0.40,
                "tongue_visible": 0.10,
            }
        }
    ]

    result = step_facial_controller(
        controller_state=controller_state,
        t_ms=40,
        expression=expression,
        micro_expression=micro_expression,
        direction=direction,
        eyes=eyes,
        speech_timeline=speech_timeline,
        kiss_timeline=None,
        smoothing_speed=0.22,
    )

    print("FACE TARGETS")
    for k, v in result["face_targets"].items():
        print(k, "=>", round(v, 4))

    print("\nSERVO TARGETS")
    for k, v in result["servo_targets"].items():
        print(k, "=>", round(v, 4))