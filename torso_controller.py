# torso_controller.py
from __future__ import annotations

import math
from typing import Any, Dict, Optional


# =========================================================
# 1) CONFIGURAÇÃO BASE
# =========================================================

TORSO_KEYS = (
    "chest_expand",
    "shoulder_raise_left",
    "shoulder_raise_right",
    "torso_pitch",
    "torso_roll",
    "torso_yaw",
)

DEFAULT_TORSO_STATE = {
    "chest_expand": 0.0,
    "shoulder_raise_left": 0.0,
    "shoulder_raise_right": 0.0,
    "torso_pitch": 0.0,
    "torso_roll": 0.0,
    "torso_yaw": 0.0,
}

SIGNED_KEYS = {
    "torso_pitch",
    "torso_roll",
    "torso_yaw",
}


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def clamp01(value: float) -> float:
    return clamp(value, 0.0, 1.0)


def clamp_signed(value: float) -> float:
    return clamp(value, -1.0, 1.0)


def normalize_torso_pose(pose: Optional[Dict[str, float]]) -> Dict[str, float]:
    out = dict(DEFAULT_TORSO_STATE)
    if not pose:
        return out

    for key in TORSO_KEYS:
        value = float(pose.get(key, out[key]))
        if key in SIGNED_KEYS:
            out[key] = clamp_signed(value)
        else:
            out[key] = clamp01(value)

    return out


def lerp(a: float, b: float, t: float) -> float:
    t = clamp01(t)
    return a + (b - a) * t


# =========================================================
# 2) PRESETS DE RESPIRAÇÃO / MOVIMENTO BASE
# =========================================================

BREATH_PRESETS: Dict[str, Dict[str, float]] = {
    "idle": {
        "rate_bpm": 11.0,
        "depth": 0.22,
        "shoulder_factor": 0.08,
        "pitch_factor": 0.03,
        "roll_factor": 0.01,
        "inhale_ratio": 0.42,
    },
    "calm": {
        "rate_bpm": 8.5,
        "depth": 0.18,
        "shoulder_factor": 0.06,
        "pitch_factor": 0.02,
        "roll_factor": 0.01,
        "inhale_ratio": 0.45,
    },
    "affectionate": {
        "rate_bpm": 10.0,
        "depth": 0.24,
        "shoulder_factor": 0.07,
        "pitch_factor": 0.03,
        "roll_factor": 0.02,
        "inhale_ratio": 0.44,
    },
    "happy": {
        "rate_bpm": 13.0,
        "depth": 0.26,
        "shoulder_factor": 0.10,
        "pitch_factor": 0.04,
        "roll_factor": 0.02,
        "inhale_ratio": 0.40,
    },
    "sad": {
        "rate_bpm": 9.0,
        "depth": 0.16,
        "shoulder_factor": 0.05,
        "pitch_factor": 0.02,
        "roll_factor": 0.01,
        "inhale_ratio": 0.48,
    },
    "anxious": {
        "rate_bpm": 18.0,
        "depth": 0.30,
        "shoulder_factor": 0.16,
        "pitch_factor": 0.05,
        "roll_factor": 0.03,
        "inhale_ratio": 0.36,
    },
    "speaking": {
        "rate_bpm": 14.0,
        "depth": 0.20,
        "shoulder_factor": 0.08,
        "pitch_factor": 0.03,
        "roll_factor": 0.01,
        "inhale_ratio": 0.32,
    },
    "kiss": {
        "rate_bpm": 12.0,
        "depth": 0.18,
        "shoulder_factor": 0.05,
        "pitch_factor": 0.02,
        "roll_factor": 0.01,
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

def make_default_torso_controller_state() -> Dict[str, Any]:
    return {
        "mode": "idle",
        "last_pose": dict(DEFAULT_TORSO_STATE),
    }


# =========================================================
# 4) RESPIRAÇÃO
# =========================================================

def breath_phase_from_time(t_ms: int, rate_bpm: float) -> float:
    rate_bpm = max(1.0, float(rate_bpm))
    cycle_ms = 60000.0 / rate_bpm
    return (float(t_ms) % cycle_ms) / cycle_ms


def breath_wave(phase: float, inhale_ratio: float = 0.42) -> float:
    phase = phase % 1.0
    inhale_ratio = clamp(inhale_ratio, 0.20, 0.80)

    if phase < inhale_ratio:
        x = phase / inhale_ratio
        return 0.5 - 0.5 * math.cos(math.pi * x)
    else:
        x = (phase - inhale_ratio) / (1.0 - inhale_ratio)
        return 0.5 + 0.5 * math.cos(math.pi * x)


def infer_torso_mode(
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
    pitch_factor = preset["pitch_factor"]
    roll_factor = preset["roll_factor"]
    inhale_ratio = preset["inhale_ratio"]

    phase = breath_phase_from_time(t_ms, rate_bpm)
    wave = breath_wave(phase, inhale_ratio=inhale_ratio)

    chest_expand = clamp01(wave * depth)

    shoulder_raise = clamp01(wave * depth * shoulder_factor / max(depth, 1e-6))
    torso_pitch = clamp_signed((wave - 0.5) * 2.0 * pitch_factor)
    torso_roll = clamp_signed(math.sin(phase * 2.0 * math.pi) * roll_factor * 0.5)

    return normalize_torso_pose({
        "chest_expand": chest_expand,
        "shoulder_raise_left": shoulder_raise,
        "shoulder_raise_right": shoulder_raise,
        "torso_pitch": torso_pitch,
        "torso_roll": torso_roll,
        "torso_yaw": 0.0,
    })


# =========================================================
# 5) AJUSTES CONTEXTUAIS
# =========================================================

def apply_emotional_torso_hint(
    pose: Dict[str, float],
    emotion_name: Optional[str] = None,
) -> Dict[str, float]:
    out = normalize_torso_pose(pose)
    emotion = emotion_name or "neutral"

    if emotion == "affectionate":
        out["torso_pitch"] = clamp_signed(out["torso_pitch"] + 0.03)
    elif emotion == "happy":
        out["torso_pitch"] = clamp_signed(out["torso_pitch"] + 0.02)
    elif emotion == "sad":
        out["torso_pitch"] = clamp_signed(out["torso_pitch"] - 0.04)
    elif emotion == "shy":
        out["torso_pitch"] = clamp_signed(out["torso_pitch"] + 0.01)
        out["torso_roll"] = clamp_signed(out["torso_roll"] + 0.03)
    elif emotion == "thoughtful":
        out["torso_roll"] = clamp_signed(out["torso_roll"] - 0.02)

    return out


def apply_direction_hint(
    pose: Dict[str, float],
    face_direction: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    out = normalize_torso_pose(pose)
    if not face_direction:
        return out

    head_yaw = clamp_signed(float(face_direction.get("head_yaw", 0.0)))
    out["torso_yaw"] = clamp_signed(head_yaw * 0.20)

    return out


# =========================================================
# 6) SUAVIZAÇÃO
# =========================================================

def smooth_torso_pose(
    current_pose: Dict[str, float],
    target_pose: Dict[str, float],
    speed: float = 0.18,
) -> Dict[str, float]:
    current = normalize_torso_pose(current_pose)
    target = normalize_torso_pose(target_pose)

    out = {}
    for key in TORSO_KEYS:
        out[key] = lerp(current[key], target[key], speed)

    return normalize_torso_pose(out)


# =========================================================
# 7) STEP PRINCIPAL
# =========================================================

def step_torso_controller(
    controller_state: Dict[str, Any],
    t_ms: int,
    emotion_name: Optional[str] = None,
    speaking: bool = False,
    kiss_active: bool = False,
    intensity: float = 0.5,
    face_direction: Optional[Dict[str, float]] = None,
    smoothing_speed: float = 0.18,
) -> Dict[str, Any]:
    mode = infer_torso_mode(
        emotion_name=emotion_name,
        speaking=speaking,
        kiss_active=kiss_active,
    )

    target_pose = build_breath_pose(
        t_ms=t_ms,
        mode=mode,
        intensity=intensity,
    )

    target_pose = apply_emotional_torso_hint(
        target_pose,
        emotion_name=emotion_name,
    )

    target_pose = apply_direction_hint(
        target_pose,
        face_direction=face_direction,
    )

    last_pose = normalize_torso_pose(controller_state.get("last_pose"))
    smoothed_pose = smooth_torso_pose(
        current_pose=last_pose,
        target_pose=target_pose,
        speed=smoothing_speed,
    )

    controller_state["mode"] = mode
    controller_state["last_pose"] = smoothed_pose

    return {
        "controller_state": controller_state,
        "mode": mode,
        "torso_pose": smoothed_pose,
    }


if __name__ == "__main__":
    state = make_default_torso_controller_state()

    for t_ms in range(0, 5000, 250):
        result = step_torso_controller(
            controller_state=state,
            t_ms=t_ms,
            emotion_name="affectionate",
            speaking=False,
            kiss_active=False,
            intensity=0.55,
            face_direction={"head_yaw": 0.2},
        )
        state = result["controller_state"]
        print(t_ms, result["mode"], result["torso_pose"])