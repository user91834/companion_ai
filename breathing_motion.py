# breathing_motion.py
from __future__ import annotations

import math
from typing import Any, Dict, Optional


# =========================================================
# 1) CONFIGURAÇÃO BASE
# =========================================================

BREATH_KEYS = (
    "chest_expand",      # expansão do tórax
    "shoulder_raise",    # leve subida dos ombros
    "head_micro_lift",   # micro subida/queda associada à respiração
)

DEFAULT_BREATH_STATE = {
    "chest_expand": 0.0,
    "shoulder_raise": 0.0,
    "head_micro_lift": 0.0,
}


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def clamp01(value: float) -> float:
    return clamp(value, 0.0, 1.0)


def clamp_signed(value: float) -> float:
    return clamp(value, -1.0, 1.0)


def normalize_breath_pose(pose: Optional[Dict[str, float]]) -> Dict[str, float]:
    out = dict(DEFAULT_BREATH_STATE)
    if not pose:
        return out

    out["chest_expand"] = clamp01(float(pose.get("chest_expand", 0.0)))
    out["shoulder_raise"] = clamp01(float(pose.get("shoulder_raise", 0.0)))
    out["head_micro_lift"] = clamp_signed(float(pose.get("head_micro_lift", 0.0)))
    return out


# =========================================================
# 2) PRESETS DE RESPIRAÇÃO
# =========================================================

BREATH_PRESETS: Dict[str, Dict[str, float]] = {
    "idle": {
        "rate_bpm": 11.0,
        "depth": 0.22,
        "shoulder_factor": 0.10,
        "head_factor": 0.04,
        "inhale_ratio": 0.42,
    },
    "calm": {
        "rate_bpm": 8.5,
        "depth": 0.18,
        "shoulder_factor": 0.07,
        "head_factor": 0.03,
        "inhale_ratio": 0.45,
    },
    "affectionate": {
        "rate_bpm": 10.0,
        "depth": 0.24,
        "shoulder_factor": 0.08,
        "head_factor": 0.05,
        "inhale_ratio": 0.44,
    },
    "happy": {
        "rate_bpm": 13.0,
        "depth": 0.26,
        "shoulder_factor": 0.12,
        "head_factor": 0.05,
        "inhale_ratio": 0.40,
    },
    "sad": {
        "rate_bpm": 9.0,
        "depth": 0.16,
        "shoulder_factor": 0.06,
        "head_factor": 0.03,
        "inhale_ratio": 0.48,
    },
    "anxious": {
        "rate_bpm": 18.0,
        "depth": 0.30,
        "shoulder_factor": 0.18,
        "head_factor": 0.07,
        "inhale_ratio": 0.36,
    },
    "speaking": {
        "rate_bpm": 14.0,
        "depth": 0.20,
        "shoulder_factor": 0.09,
        "head_factor": 0.04,
        "inhale_ratio": 0.32,
    },
    "kiss": {
        "rate_bpm": 12.0,
        "depth": 0.18,
        "shoulder_factor": 0.06,
        "head_factor": 0.03,
        "inhale_ratio": 0.38,
    },
}


def get_breath_preset(name: Optional[str]) -> Dict[str, float]:
    if not name:
        name = "idle"
    return dict(BREATH_PRESETS.get(name, BREATH_PRESETS["idle"]))


# =========================================================
# 3) ESTADO
# =========================================================

def make_default_breath_controller_state() -> Dict[str, Any]:
    return {
        "mode": "idle",
        "last_pose": dict(DEFAULT_BREATH_STATE),
    }


# =========================================================
# 4) CICLO RESPIRATÓRIO
# =========================================================

def breath_phase_from_time(t_ms: int, rate_bpm: float) -> float:
    """
    Retorna fase normalizada 0..1 do ciclo respiratório.
    """
    rate_bpm = max(1.0, float(rate_bpm))
    cycle_ms = 60000.0 / rate_bpm
    phase = (float(t_ms) % cycle_ms) / cycle_ms
    return phase


def breath_wave(
    phase: float,
    inhale_ratio: float = 0.42,
) -> float:
    """
    Onda respiratória simplificada:
    - subida mais curta na inspiração
    - descida mais longa na expiração
    Retorna 0..1
    """
    phase = phase % 1.0
    inhale_ratio = clamp(inhale_ratio, 0.20, 0.80)

    if phase < inhale_ratio:
        # inspiração
        x = phase / inhale_ratio
        return 0.5 - 0.5 * math.cos(math.pi * x)
    else:
        # expiração
        x = (phase - inhale_ratio) / (1.0 - inhale_ratio)
        return 0.5 + 0.5 * math.cos(math.pi * x)


# =========================================================
# 5) GERAÇÃO DA POSE
# =========================================================

def build_breath_pose(
    t_ms: int,
    mode: str = "idle",
    intensity: float = 0.5,
) -> Dict[str, float]:
    preset = get_breath_preset(mode)
    intensity = clamp01(intensity)

    rate_bpm = preset["rate_bpm"]
    depth = preset["depth"] * (0.85 + 0.30 * intensity)
    shoulder_factor = preset["shoulder_factor"]
    head_factor = preset["head_factor"]
    inhale_ratio = preset["inhale_ratio"]

    phase = breath_phase_from_time(t_ms, rate_bpm=rate_bpm)
    wave = breath_wave(phase, inhale_ratio=inhale_ratio)

    chest_expand = clamp01(wave * depth)
    shoulder_raise = clamp01(wave * depth * shoulder_factor / max(depth, 1e-6))
    head_micro_lift = clamp_signed((wave - 0.5) * 2.0 * head_factor)

    return normalize_breath_pose({
        "chest_expand": chest_expand,
        "shoulder_raise": shoulder_raise,
        "head_micro_lift": head_micro_lift,
    })


# =========================================================
# 6) ESCOLHA DE MODO
# =========================================================

def infer_breath_mode(
    emotion_name: Optional[str] = None,
    speaking: bool = False,
    kiss_active: bool = False,
) -> str:
    if kiss_active:
        return "kiss"
    if speaking:
        return "speaking"

    mapping = {
        "neutral": "idle",
        "curious": "idle",
        "affectionate": "affectionate",
        "happy": "happy",
        "playful": "happy",
        "sad": "sad",
        "concerned": "idle",
        "surprised": "anxious",
        "shy": "affectionate",
        "thoughtful": "calm",
    }
    return mapping.get(emotion_name or "neutral", "idle")


# =========================================================
# 7) SUAVIZAÇÃO
# =========================================================

def lerp(a: float, b: float, t: float) -> float:
    t = clamp01(t)
    return a + (b - a) * t


def smooth_breath_pose(
    current_pose: Dict[str, float],
    target_pose: Dict[str, float],
    speed: float = 0.18,
) -> Dict[str, float]:
    current = normalize_breath_pose(current_pose)
    target = normalize_breath_pose(target_pose)

    out = {
        "chest_expand": lerp(current["chest_expand"], target["chest_expand"], speed),
        "shoulder_raise": lerp(current["shoulder_raise"], target["shoulder_raise"], speed),
        "head_micro_lift": lerp(current["head_micro_lift"], target["head_micro_lift"], speed),
    }
    return normalize_breath_pose(out)


# =========================================================
# 8) STEP PRINCIPAL
# =========================================================

def step_breathing(
    controller_state: Dict[str, Any],
    t_ms: int,
    emotion_name: Optional[str] = None,
    speaking: bool = False,
    kiss_active: bool = False,
    intensity: float = 0.5,
    smoothing_speed: float = 0.18,
) -> Dict[str, Any]:
    mode = infer_breath_mode(
        emotion_name=emotion_name,
        speaking=speaking,
        kiss_active=kiss_active,
    )

    target_pose = build_breath_pose(
        t_ms=t_ms,
        mode=mode,
        intensity=intensity,
    )

    last_pose = normalize_breath_pose(controller_state.get("last_pose"))
    smoothed_pose = smooth_breath_pose(
        current_pose=last_pose,
        target_pose=target_pose,
        speed=smoothing_speed,
    )

    controller_state["mode"] = mode
    controller_state["last_pose"] = smoothed_pose

    return {
        "controller_state": controller_state,
        "mode": mode,
        "breath_pose": smoothed_pose,
    }


if __name__ == "__main__":
    state = make_default_breath_controller_state()

    for t_ms in range(0, 5000, 250):
        result = step_breathing(
            controller_state=state,
            t_ms=t_ms,
            emotion_name="affectionate",
            speaking=False,
            kiss_active=False,
            intensity=0.55,
        )
        state = result["controller_state"]
        print(t_ms, result["mode"], result["breath_pose"])