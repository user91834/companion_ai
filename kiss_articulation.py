# kiss_articulation.py
from __future__ import annotations

from typing import Any, Dict, List, Optional


# =========================
# 1) CONFIGURAÇÃO BASE
# =========================

POSE_KEYS = [
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


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def normalize_pose(pose: Dict[str, float]) -> Dict[str, float]:
    out = {}
    for key in POSE_KEYS:
        out[key] = clamp01(float(pose.get(key, 0.0)))
    return out


def blend_pose(
    a: Dict[str, float],
    b: Dict[str, float],
    weight_a: float = 0.5,
    weight_b: float = 0.5,
) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for key in POSE_KEYS:
        out[key] = clamp01(
            a.get(key, 0.0) * weight_a +
            b.get(key, 0.0) * weight_b
        )
    return out


# =========================
# 2) POSES BASE
# =========================

REST_POSE = {
    "jaw_open": 0.00,
    "lip_round": 0.00,
    "lip_spread": 0.00,
    "lip_press": 0.10,
    "tongue_tip_up": 0.00,
    "tongue_tip_forward": 0.00,
    "tongue_tip_lateral": 0.50,
    "tongue_body_high": 0.00,
    "tongue_body_front": 0.00,
    "tongue_mid_arch": 0.00,
    "tongue_visible": 0.00,
}

PECK_APPROACH_POSE = {
    "jaw_open": 0.04,
    "lip_round": 0.68,
    "lip_spread": 0.00,
    "lip_press": 0.32,
    "tongue_tip_up": 0.00,
    "tongue_tip_forward": 0.00,
    "tongue_tip_lateral": 0.50,
    "tongue_body_high": 0.02,
    "tongue_body_front": 0.02,
    "tongue_mid_arch": 0.04,
    "tongue_visible": 0.00,
}

PECK_CONTACT_POSE = {
    "jaw_open": 0.02,
    "lip_round": 0.82,
    "lip_spread": 0.00,
    "lip_press": 0.92,
    "tongue_tip_up": 0.00,
    "tongue_tip_forward": 0.00,
    "tongue_tip_lateral": 0.50,
    "tongue_body_high": 0.00,
    "tongue_body_front": 0.00,
    "tongue_mid_arch": 0.02,
    "tongue_visible": 0.00,
}

PECK_RELEASE_POSE = {
    "jaw_open": 0.03,
    "lip_round": 0.52,
    "lip_spread": 0.04,
    "lip_press": 0.20,
    "tongue_tip_up": 0.00,
    "tongue_tip_forward": 0.00,
    "tongue_tip_lateral": 0.50,
    "tongue_body_high": 0.00,
    "tongue_body_front": 0.00,
    "tongue_mid_arch": 0.02,
    "tongue_visible": 0.00,
}

MOUTH_KISS_APPROACH_POSE = {
    "jaw_open": 0.10,
    "lip_round": 0.62,
    "lip_spread": 0.02,
    "lip_press": 0.28,
    "tongue_tip_up": 0.06,
    "tongue_tip_forward": 0.05,
    "tongue_tip_lateral": 0.50,
    "tongue_body_high": 0.08,
    "tongue_body_front": 0.10,
    "tongue_mid_arch": 0.10,
    "tongue_visible": 0.00,
}

MOUTH_KISS_CONTACT_POSE = {
    "jaw_open": 0.08,
    "lip_round": 0.78,
    "lip_spread": 0.00,
    "lip_press": 0.72,
    "tongue_tip_up": 0.08,
    "tongue_tip_forward": 0.10,
    "tongue_tip_lateral": 0.50,
    "tongue_body_high": 0.12,
    "tongue_body_front": 0.12,
    "tongue_mid_arch": 0.14,
    "tongue_visible": 0.02,
}

MOUTH_KISS_INNER_POSE = {
    "jaw_open": 0.18,
    "lip_round": 0.54,
    "lip_spread": 0.04,
    "lip_press": 0.18,
    "tongue_tip_up": 0.16,
    "tongue_tip_forward": 0.22,
    "tongue_tip_lateral": 0.50,
    "tongue_body_high": 0.20,
    "tongue_body_front": 0.28,
    "tongue_mid_arch": 0.22,
    "tongue_visible": 0.12,
}

MOUTH_KISS_RELEASE_POSE = {
    "jaw_open": 0.08,
    "lip_round": 0.40,
    "lip_spread": 0.06,
    "lip_press": 0.14,
    "tongue_tip_up": 0.04,
    "tongue_tip_forward": 0.04,
    "tongue_tip_lateral": 0.50,
    "tongue_body_high": 0.06,
    "tongue_body_front": 0.06,
    "tongue_mid_arch": 0.08,
    "tongue_visible": 0.00,
}


# =========================
# 3) MODULAÇÃO EMOCIONAL
# =========================

EMOTION_PRESETS: Dict[str, Dict[str, float]] = {
    "neutral": {
        "jaw_add": 0.00,
        "round_add": 0.00,
        "spread_add": 0.00,
        "press_add": 0.00,
        "tongue_add": 0.00,
    },
    "affectionate": {
        "jaw_add": 0.00,
        "round_add": 0.06,
        "spread_add": 0.03,
        "press_add": 0.05,
        "tongue_add": 0.00,
    },
    "happy": {
        "jaw_add": 0.02,
        "round_add": -0.03,
        "spread_add": 0.10,
        "press_add": -0.04,
        "tongue_add": 0.00,
    },
    "shy": {
        "jaw_add": -0.02,
        "round_add": 0.02,
        "spread_add": -0.02,
        "press_add": 0.08,
        "tongue_add": -0.03,
    },
    "playful": {
        "jaw_add": 0.03,
        "round_add": -0.02,
        "spread_add": 0.06,
        "press_add": -0.02,
        "tongue_add": 0.04,
    },
    "sad": {
        "jaw_add": -0.03,
        "round_add": 0.00,
        "spread_add": -0.04,
        "press_add": 0.04,
        "tongue_add": -0.02,
    },
}


def apply_emotion_to_pose(
    pose: Dict[str, float],
    emotion: str = "affectionate",
    intensity: float = 0.5,
) -> Dict[str, float]:
    preset = EMOTION_PRESETS.get(emotion, EMOTION_PRESETS["neutral"])
    t = clamp01(intensity)

    out = dict(pose)

    out["jaw_open"] = pose["jaw_open"] + preset["jaw_add"] * t
    out["lip_round"] = pose["lip_round"] + preset["round_add"] * t
    out["lip_spread"] = pose["lip_spread"] + preset["spread_add"] * t
    out["lip_press"] = pose["lip_press"] + preset["press_add"] * t

    tongue_delta = preset["tongue_add"] * t
    out["tongue_tip_up"] = pose["tongue_tip_up"] + tongue_delta
    out["tongue_tip_forward"] = pose["tongue_tip_forward"] + tongue_delta
    out["tongue_body_front"] = pose["tongue_body_front"] + tongue_delta
    out["tongue_mid_arch"] = pose["tongue_mid_arch"] + tongue_delta
    out["tongue_visible"] = pose["tongue_visible"] + max(0.0, tongue_delta * 0.8)

    return normalize_pose(out)


def apply_kiss_intensity(
    pose: Dict[str, float],
    kiss_type: str,
    intensity: float = 0.5,
) -> Dict[str, float]:
    """
    Intensidade aqui não é emoção, é força/entrega do beijo.
    """
    t = clamp01(intensity)
    out = dict(pose)

    if kiss_type == "peck":
        out["lip_press"] = pose["lip_press"] + 0.08 * t
        out["lip_round"] = pose["lip_round"] + 0.06 * t
        out["jaw_open"] = pose["jaw_open"] + 0.01 * t
        out["tongue_visible"] = 0.0

    elif kiss_type == "mouth_kiss":
        out["lip_press"] = pose["lip_press"] + 0.04 * t
        out["lip_round"] = pose["lip_round"] + 0.04 * t
        out["jaw_open"] = pose["jaw_open"] + 0.08 * t
        out["tongue_tip_forward"] = pose["tongue_tip_forward"] + 0.10 * t
        out["tongue_body_front"] = pose["tongue_body_front"] + 0.08 * t
        out["tongue_visible"] = pose["tongue_visible"] + 0.08 * t

    return normalize_pose(out)


# =========================
# 4) FASES DO BEIJO
# =========================

def peck_sequence(
    emotion: str = "affectionate",
    intensity: float = 0.5,
) -> List[Dict[str, Any]]:
    phases = [
        {
            "phase": "approach",
            "duration_ms": 90,
            "pose": PECK_APPROACH_POSE,
        },
        {
            "phase": "contact",
            "duration_ms": 120,
            "pose": PECK_CONTACT_POSE,
        },
        {
            "phase": "release",
            "duration_ms": 100,
            "pose": PECK_RELEASE_POSE,
        },
    ]

    out: List[Dict[str, Any]] = []
    for item in phases:
        pose = apply_emotion_to_pose(item["pose"], emotion=emotion, intensity=intensity)
        pose = apply_kiss_intensity(pose, kiss_type="peck", intensity=intensity)

        out.append({
            "phase": item["phase"],
            "duration_ms": int(item["duration_ms"] * (0.92 + 0.22 * clamp01(intensity))),
            "pose": pose,
        })

    return out


def mouth_kiss_sequence(
    emotion: str = "affectionate",
    intensity: float = 0.5,
    cycles: int = 1,
) -> List[Dict[str, Any]]:
    cycles = max(1, min(4, int(cycles)))

    out: List[Dict[str, Any]] = []

    base_approach = apply_emotion_to_pose(
        MOUTH_KISS_APPROACH_POSE,
        emotion=emotion,
        intensity=intensity,
    )
    base_approach = apply_kiss_intensity(
        base_approach,
        kiss_type="mouth_kiss",
        intensity=intensity,
    )
    out.append({
        "phase": "approach",
        "duration_ms": int(140 * (0.92 + 0.22 * clamp01(intensity))),
        "pose": base_approach,
    })

    for idx in range(cycles):
        contact_pose = apply_emotion_to_pose(
            MOUTH_KISS_CONTACT_POSE,
            emotion=emotion,
            intensity=intensity,
        )
        contact_pose = apply_kiss_intensity(
            contact_pose,
            kiss_type="mouth_kiss",
            intensity=intensity,
        )

        inner_pose = apply_emotion_to_pose(
            MOUTH_KISS_INNER_POSE,
            emotion=emotion,
            intensity=intensity,
        )
        inner_pose = apply_kiss_intensity(
            inner_pose,
            kiss_type="mouth_kiss",
            intensity=intensity,
        )

        out.append({
            "phase": f"contact_{idx + 1}",
            "duration_ms": int(180 * (0.90 + 0.25 * clamp01(intensity))),
            "pose": contact_pose,
        })
        out.append({
            "phase": f"inner_{idx + 1}",
            "duration_ms": int(220 * (0.90 + 0.30 * clamp01(intensity))),
            "pose": inner_pose,
        })

    release_pose = apply_emotion_to_pose(
        MOUTH_KISS_RELEASE_POSE,
        emotion=emotion,
        intensity=intensity,
    )
    release_pose = apply_kiss_intensity(
        release_pose,
        kiss_type="mouth_kiss",
        intensity=intensity,
    )
    out.append({
        "phase": "release",
        "duration_ms": int(150 * (0.92 + 0.20 * clamp01(intensity))),
        "pose": release_pose,
    })

    return out


# =========================
# 5) SUAVIZAÇÃO
# =========================

def smooth_pose_sequence(
    items: List[Dict[str, Any]],
    prev_weight: float = 0.20,
    current_weight: float = 0.60,
    next_weight: float = 0.20,
) -> List[Dict[str, Any]]:
    if not items:
        return []

    smoothed: List[Dict[str, Any]] = []

    for idx, item in enumerate(items):
        prev_pose = items[idx - 1]["pose"] if idx > 0 else item["pose"]
        curr_pose = item["pose"]
        next_pose = items[idx + 1]["pose"] if idx < len(items) - 1 else item["pose"]

        blended = {}
        for key in POSE_KEYS:
            blended[key] = clamp01(
                prev_pose[key] * prev_weight +
                curr_pose[key] * current_weight +
                next_pose[key] * next_weight
            )

        smoothed.append({
            **item,
            "pose_raw": item["pose"],
            "pose": blended,
        })

    return smoothed


# =========================
# 6) TIMELINE
# =========================

def gestures_to_timeline(
    gestures: List[Dict[str, Any]],
    leading_silence_ms: int = 50,
    trailing_silence_ms: int = 80,
) -> List[Dict[str, Any]]:
    silence_pose = normalize_pose(REST_POSE)

    timeline: List[Dict[str, Any]] = [
        {
            "t_ms": 0,
            "type": "rest",
            "phase": "pre_rest",
            "duration_ms": leading_silence_ms,
            "pose": silence_pose,
        }
    ]

    t = leading_silence_ms
    for g in gestures:
        timeline.append({
            "t_ms": t,
            "type": "kiss_phase",
            "phase": g["phase"],
            "duration_ms": g["duration_ms"],
            "pose": normalize_pose(g["pose"]),
        })
        t += g["duration_ms"]

    timeline.append({
        "t_ms": t,
        "type": "rest",
        "phase": "post_rest",
        "duration_ms": trailing_silence_ms,
        "pose": silence_pose,
    })

    return timeline


# =========================
# 7) FUNÇÕES PRINCIPAIS
# =========================

def build_kiss_gesture_sequence(
    kiss_type: str = "peck",
    emotion: str = "affectionate",
    intensity: float = 0.5,
    cycles: int = 1,
    smooth: bool = True,
) -> List[Dict[str, Any]]:
    kiss_type = (kiss_type or "peck").strip().lower()

    if kiss_type == "peck":
        gestures = peck_sequence(
            emotion=emotion,
            intensity=intensity,
        )
    elif kiss_type == "mouth_kiss":
        gestures = mouth_kiss_sequence(
            emotion=emotion,
            intensity=intensity,
            cycles=cycles,
        )
    else:
        raise ValueError(f"Unsupported kiss_type: {kiss_type}")

    if smooth:
        gestures = smooth_pose_sequence(gestures)

    return gestures


def build_kiss_timeline(
    kiss_type: str = "peck",
    emotion: str = "affectionate",
    intensity: float = 0.5,
    cycles: int = 1,
    smooth: bool = True,
    leading_silence_ms: int = 50,
    trailing_silence_ms: int = 80,
) -> Dict[str, Any]:
    gestures = build_kiss_gesture_sequence(
        kiss_type=kiss_type,
        emotion=emotion,
        intensity=intensity,
        cycles=cycles,
        smooth=smooth,
    )

    timeline = gestures_to_timeline(
        gestures=gestures,
        leading_silence_ms=leading_silence_ms,
        trailing_silence_ms=trailing_silence_ms,
    )

    total_duration_ms = sum(item["duration_ms"] for item in timeline)

    return {
        "kiss_type": kiss_type,
        "emotion": emotion,
        "intensity": intensity,
        "cycles": cycles,
        "gesture_count": len(gestures),
        "gesture_sequence": gestures,
        "gesture_timeline": timeline,
        "total_duration_ms": total_duration_ms,
    }


def build_peck_kiss(
    emotion: str = "affectionate",
    intensity: float = 0.5,
) -> Dict[str, Any]:
    return build_kiss_timeline(
        kiss_type="peck",
        emotion=emotion,
        intensity=intensity,
        cycles=1,
    )


def build_mouth_kiss(
    emotion: str = "affectionate",
    intensity: float = 0.5,
    cycles: int = 1,
) -> Dict[str, Any]:
    return build_kiss_timeline(
        kiss_type="mouth_kiss",
        emotion=emotion,
        intensity=intensity,
        cycles=cycles,
    )


if __name__ == "__main__":
    peck = build_peck_kiss(
        emotion="affectionate",
        intensity=0.55,
    )

    mouth = build_mouth_kiss(
        emotion="affectionate",
        intensity=0.70,
        cycles=2,
    )

    print("=" * 80)
    print("PECK KISS")
    for item in peck["gesture_timeline"]:
        print(item)

    print("=" * 80)
    print("MOUTH KISS")
    for item in mouth["gesture_timeline"]:
        print(item)