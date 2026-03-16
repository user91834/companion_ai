# expression_test.py
from __future__ import annotations

from typing import Any, Dict, Optional

from facial_emotion import (
    make_default_emotional_state,
    build_expression_from_user_emotion,
)

from facial_micro import (
    make_default_micro_state,
    apply_micro_expression,
)

from facial_direction import (
    make_default_direction_state,
    update_direction_from_user_emotion,
)

from eyes_direction import (
    make_default_eye_state,
    update_eye_direction_from_user_emotion,
)

from facial_controller import (
    make_default_controller_state,
    step_facial_controller,
)

from torso_controller import (
    make_default_torso_controller_state,
    step_torso_controller,
)


# =========================================================
# 1) ESTADO GLOBAL DE TESTE
# =========================================================

def make_test_state() -> Dict[str, Any]:
    return {
        "emotion_state": make_default_emotional_state(),
        "micro_state": make_default_micro_state(),
        "direction_state": make_default_direction_state(),
        "eye_state": make_default_eye_state(),
        "face_controller_state": make_default_controller_state(),
        "torso_controller_state": make_default_torso_controller_state(),
    }


# =========================================================
# 2) STEP DE ORQUESTRAÇÃO
# =========================================================

def step_expression_test(
    state: Dict[str, Any],
    t_ms: int,
    user_emotion: Optional[str] = "affection",
    resonance_weight: float = 0.28,
    emotional_intensity: float = 0.55,
    speaking: bool = False,
    kiss_active: bool = False,
    speech_timeline: Optional[list] = None,
    kiss_timeline: Optional[list] = None,
) -> Dict[str, Any]:
    # -----------------------------------------------------
    # A) EMOÇÃO FACIAL
    # -----------------------------------------------------
    emotion_result = build_expression_from_user_emotion(
        current_state=state["emotion_state"],
        user_emotion=user_emotion,
        resonance_weight=resonance_weight,
    )
    state["emotion_state"] = emotion_result["state"]
    expression = emotion_result["expression"]

    # -----------------------------------------------------
    # B) DIREÇÃO DO ROSTO
    # -----------------------------------------------------
    state["direction_state"] = update_direction_from_user_emotion(
        direction_state=state["direction_state"],
        user_emotion=user_emotion,
        speed=0.10,
        speaking=speaking,
        listening=not speaking,
    )
    face_direction = state["direction_state"]["current"]

    # -----------------------------------------------------
    # C) DIREÇÃO DOS OLHOS
    # -----------------------------------------------------
    state["eye_state"] = update_eye_direction_from_user_emotion(
        eye_state=state["eye_state"],
        user_emotion=user_emotion,
        speed=0.18,
        speaking=speaking,
        listening=not speaking,
        use_vertical_eyelid_coupling=True,
    )
    eye_direction = state["eye_state"]["current"]

    # -----------------------------------------------------
    # D) MICROEXPRESSÃO + PISCADA
    # -----------------------------------------------------
    micro_result = apply_micro_expression(
        base_expr=expression,
        micro_state=state["micro_state"],
        emotional_intensity=emotional_intensity,
        speaking=speaking,
        listening=not speaking,
        now=t_ms / 1000.0,
    )
    state["micro_state"] = micro_result["micro_state"]
    micro_expression = micro_result["expression"]

    # -----------------------------------------------------
    # E) ROSTO FINAL
    # -----------------------------------------------------
    face_result = step_facial_controller(
        controller_state=state["face_controller_state"],
        t_ms=t_ms,
        expression=expression,
        micro_expression=micro_expression,
        direction=face_direction,
        eyes=eye_direction,
        speech_timeline=speech_timeline,
        kiss_timeline=kiss_timeline,
        micro_weight=1.0,
        speech_weight=1.0,
        kiss_weight=1.0,
        allow_articulation_mix=False,
        smoothing_speed=0.20,
    )
    state["face_controller_state"] = face_result["controller_state"]

    # -----------------------------------------------------
    # F) TRONCO / RESPIRAÇÃO
    # -----------------------------------------------------
    torso_result = step_torso_controller(
        controller_state=state["torso_controller_state"],
        t_ms=t_ms,
        emotion_name=_map_user_emotion_to_face_emotion_name(user_emotion),
        speaking=speaking,
        kiss_active=kiss_active,
        intensity=emotional_intensity,
        face_direction=face_direction,
        smoothing_speed=0.18,
    )
    state["torso_controller_state"] = torso_result["controller_state"]

    return {
        "state": state,
        "t_ms": t_ms,
        "user_emotion": user_emotion,
        "expression": expression,
        "micro_expression": micro_expression,
        "face_direction": face_direction,
        "eye_direction": eye_direction,
        "face_targets": face_result["face_targets"],
        "servo_targets": face_result["servo_targets"],
        "torso_pose": torso_result["torso_pose"],
        "blink_active": micro_result["blink_active"],
    }


# =========================================================
# 3) MAPEAMENTO AUXILIAR
# =========================================================

def _map_user_emotion_to_face_emotion_name(user_emotion: Optional[str]) -> str:
    """
    Ajuda a escolher um nome emocional simples para o torso.
    """
    if not user_emotion:
        return "neutral"

    mapping = {
        "happy": "happy",
        "affection": "affectionate",
        "sad": "sad",
        "angry": "concerned",
        "confused": "curious",
        "playful": "playful",
        "lonely": "affectionate",
        "neutral": "neutral",
    }
    return mapping.get(user_emotion, "neutral")


# =========================================================
# 4) IMPRESSÃO RESUMIDA
# =========================================================

def print_frame_summary(frame: Dict[str, Any]) -> None:
    face = frame["face_targets"]
    torso = frame["torso_pose"]

    print("=" * 80)
    print(
        f't={frame["t_ms"]:>5} ms | '
        f'user_emotion={frame["user_emotion"]} | '
        f'blink={frame["blink_active"]}'
    )

    print("FACE")
    print(
        f'  brow=({face["brow_left"]:.2f}, {face["brow_right"]:.2f}) | '
        f'eyelid={face["eyelid"]:.2f} | '
        f'cheek={face["cheek_raise"]:.2f}'
    )
    print(
        f'  head=(yaw={face["head_yaw"]:.2f}, pitch={face["head_pitch"]:.2f}, roll={face["head_roll"]:.2f})'
    )
    print(
        f'  eyes=(yaw={face["eye_yaw"]:.2f}, pitch={face["eye_pitch"]:.2f}) | '
        f'pupil={face["pupil_size"]:.2f}'
    )
    print(
        f'  mouth=(jaw={face["jaw_open"]:.2f}, round={face["lip_round"]:.2f}, '
        f'spread={face["lip_spread"]:.2f}, press={face["lip_press"]:.2f})'
    )
    print(
        f'  tongue=(tip_up={face["tongue_tip_up"]:.2f}, tip_fwd={face["tongue_tip_forward"]:.2f}, '
        f'visible={face["tongue_visible"]:.2f})'
    )

    print("TORSO")
    print(
        f'  chest={torso["chest_expand"]:.2f} | '
        f'shoulder_L={torso["shoulder_raise_left"]:.2f} | '
        f'shoulder_R={torso["shoulder_raise_right"]:.2f}'
    )
    print(
        f'  torso=(pitch={torso["torso_pitch"]:.2f}, roll={torso["torso_roll"]:.2f}, yaw={torso["torso_yaw"]:.2f})'
    )


# =========================================================
# 5) DEMOS
# =========================================================

def run_demo(
    user_emotion: str = "affection",
    duration_ms: int = 3000,
    step_ms: int = 200,
    speaking: bool = False,
    kiss_active: bool = False,
    speech_timeline: Optional[list] = None,
    kiss_timeline: Optional[list] = None,
) -> None:
    state = make_test_state()

    for t_ms in range(0, duration_ms + 1, step_ms):
        frame = step_expression_test(
            state=state,
            t_ms=t_ms,
            user_emotion=user_emotion,
            resonance_weight=0.28,
            emotional_intensity=0.55,
            speaking=speaking,
            kiss_active=kiss_active,
            speech_timeline=speech_timeline,
            kiss_timeline=kiss_timeline,
        )
        state = frame["state"]
        print_frame_summary(frame)


# =========================================================
# 6) EXEMPLO PRINCIPAL
# =========================================================

if __name__ == "__main__":
    print("\n########## DEMO 1: AFETO / ESCUTA ##########\n")
    run_demo(
        user_emotion="affection",
        duration_ms=2400,
        step_ms=200,
        speaking=False,
        kiss_active=False,
    )

    print("\n########## DEMO 2: TRISTEZA / ACOLHIMENTO ##########\n")
    run_demo(
        user_emotion="sad",
        duration_ms=2400,
        step_ms=200,
        speaking=False,
        kiss_active=False,
    )

    print("\n########## DEMO 3: FELIZ / FALANDO ##########\n")
    run_demo(
        user_emotion="happy",
        duration_ms=2400,
        step_ms=200,
        speaking=True,
        kiss_active=False,
        speech_timeline=[
            {
                "t_ms": 0,
                "duration_ms": 300,
                "pose": {
                    "jaw_open": 0.20,
                    "lip_round": 0.06,
                    "lip_spread": 0.38,
                    "lip_press": 0.04,
                    "tongue_tip_up": 0.12,
                    "tongue_tip_forward": 0.08,
                    "tongue_tip_lateral": 0.50,
                    "tongue_body_high": 0.46,
                    "tongue_body_front": 0.54,
                    "tongue_mid_arch": 0.40,
                    "tongue_visible": 0.08,
                },
            },
            {
                "t_ms": 300,
                "duration_ms": 300,
                "pose": {
                    "jaw_open": 0.32,
                    "lip_round": 0.16,
                    "lip_spread": 0.18,
                    "lip_press": 0.06,
                    "tongue_tip_up": 0.08,
                    "tongue_tip_forward": 0.04,
                    "tongue_tip_lateral": 0.50,
                    "tongue_body_high": 0.34,
                    "tongue_body_front": 0.28,
                    "tongue_mid_arch": 0.32,
                    "tongue_visible": 0.05,
                },
            },
        ],
    )