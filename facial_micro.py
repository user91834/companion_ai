from __future__ import annotations

import random
import time
from typing import Dict, Any, Optional


# =========================================================
# 1) CONFIGURAÇÃO BASE
# =========================================================

SERVO_KEYS = (
    "brow_left",
    "brow_right",
    "eyelid",
    "mouth_smile",
    "mouth_open",
    "cheek_raise",
    "head_tilt",
)

DEFAULT_EXPRESSION = {
    "brow_left": 0.5,
    "brow_right": 0.5,
    "eyelid": 0.5,
    "mouth_smile": 0.0,
    "mouth_open": 0.0,
    "cheek_raise": 0.0,
    "head_tilt": 0.0,
}


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def clamp01(value: float) -> float:
    return clamp(value, 0.0, 1.0)


def clamp_signed(value: float) -> float:
    return clamp(value, -1.0, 1.0)


def normalize_expression(expr: Dict[str, float]) -> Dict[str, float]:
    normalized = dict(DEFAULT_EXPRESSION)

    for key in SERVO_KEYS:
        value = expr.get(key, DEFAULT_EXPRESSION[key])

        if key in ("mouth_smile", "head_tilt"):
            normalized[key] = clamp_signed(value)
        else:
            normalized[key] = clamp01(value)

    return normalized


# =========================================================
# 2) ESTADO INTERNO DE MICROEXPRESSÃO
# =========================================================

def make_default_micro_state(now: Optional[float] = None) -> Dict[str, Any]:
    """
    Estado interno do sistema de microexpressões.
    """
    if now is None:
        now = time.time()

    next_blink_in = random.uniform(2.8, 5.5)

    return {
        "enabled": True,
        "last_update_ts": now,
        "last_blink_ts": now,
        "blink_until_ts": 0.0,
        "next_blink_ts": now + next_blink_in,
        "blink_phase": "idle",  # idle, closing, opening
        "micro_seed": random.random(),
    }


# =========================================================
# 3) PISCADAS
# =========================================================

def should_start_blink(
    micro_state: Dict[str, Any],
    now: Optional[float] = None,
) -> bool:
    if now is None:
        now = time.time()

    if now >= micro_state.get("next_blink_ts", 0.0):
        return True

    return False


def schedule_next_blink(
    micro_state: Dict[str, Any],
    now: Optional[float] = None,
    speaking: bool = False,
    listening: bool = False,
) -> Dict[str, Any]:
    """
    Ajusta o próximo momento de piscar.
    Durante escuta/atenção social pode piscar um pouco mais.
    Durante fala intensa pode piscar um pouco menos.
    """
    if now is None:
        now = time.time()

    if listening:
        interval = random.uniform(2.5, 4.5)
    elif speaking:
        interval = random.uniform(3.5, 6.0)
    else:
        interval = random.uniform(2.8, 5.5)

    micro_state["next_blink_ts"] = now + interval
    return micro_state


def start_blink(
    micro_state: Dict[str, Any],
    now: Optional[float] = None,
    blink_duration: float = 0.18,
) -> Dict[str, Any]:
    if now is None:
        now = time.time()

    blink_duration = clamp(blink_duration, 0.08, 0.40)

    micro_state["last_blink_ts"] = now
    micro_state["blink_until_ts"] = now + blink_duration
    micro_state["blink_phase"] = "closing"
    return micro_state


def compute_blink_eyelid_delta(
    micro_state: Dict[str, Any],
    now: Optional[float] = None,
) -> float:
    """
    Retorna quanto a pálpebra deve fechar por conta da piscada.
    0.0 = sem efeito
    1.0 = totalmente fechada
    """
    if now is None:
        now = time.time()

    blink_until = micro_state.get("blink_until_ts", 0.0)
    last_blink = micro_state.get("last_blink_ts", 0.0)

    if now >= blink_until or blink_until <= last_blink:
        micro_state["blink_phase"] = "idle"
        return 0.0

    total = blink_until - last_blink
    elapsed = now - last_blink

    if total <= 0:
        micro_state["blink_phase"] = "idle"
        return 0.0

    half = total / 2.0

    if elapsed <= half:
        micro_state["blink_phase"] = "closing"
        progress = elapsed / half
        return clamp01(progress)
    else:
        micro_state["blink_phase"] = "opening"
        progress = (elapsed - half) / half
        return clamp01(1.0 - progress)


# =========================================================
# 4) MICROVARIAÇÕES FACIAIS
# =========================================================

def generate_micro_offsets(
    emotional_intensity: float = 0.3,
    speaking: bool = False,
    listening: bool = False,
) -> Dict[str, float]:
    """
    Gera pequenos offsets orgânicos.
    Quanto maior a intensidade emocional, ligeiramente maiores os micro movimentos.
    """
    intensity = clamp01(emotional_intensity)

    brow_amp = 0.010 + intensity * 0.020
    head_amp = 0.006 + intensity * 0.014
    smile_amp = 0.004 + intensity * 0.010
    cheek_amp = 0.004 + intensity * 0.010

    if speaking:
        # durante fala, a boca principal já será controlada em outro lugar,
        # então aqui reduzimos interferência na boca
        smile_amp *= 0.5

    if listening:
        # durante escuta, sobrancelha e cabeça podem ficar um pouco mais vivas
        brow_amp *= 1.15
        head_amp *= 1.20

    brow_shift = random.uniform(-brow_amp, brow_amp)
    brow_asym = random.uniform(-brow_amp, brow_amp)

    offsets = {
        "brow_left": brow_shift + brow_asym,
        "brow_right": brow_shift - brow_asym,
        "eyelid": random.uniform(-0.006, 0.006),
        "mouth_smile": random.uniform(-smile_amp, smile_amp),
        "mouth_open": 0.0,
        "cheek_raise": random.uniform(-cheek_amp, cheek_amp),
        "head_tilt": random.uniform(-head_amp, head_amp),
    }

    return offsets


def apply_offsets(
    base_expr: Dict[str, float],
    offsets: Dict[str, float],
) -> Dict[str, float]:
    expr = normalize_expression(base_expr)

    for key, delta in offsets.items():
        if key not in expr:
            continue
        expr[key] = expr[key] + delta

    return normalize_expression(expr)


# =========================================================
# 5) AJUSTE CONTEXTUAL DE ESCUTA / FALA
# =========================================================

def apply_social_attention_adjustments(
    base_expr: Dict[str, float],
    listening: bool = False,
    speaking: bool = False,
) -> Dict[str, float]:
    """
    Pequenos ajustes de microexpressão dependendo do modo social.
    """
    expr = normalize_expression(base_expr)

    if listening:
        # escutando: levemente mais atenta
        expr["brow_left"] = clamp01(expr["brow_left"] + 0.015)
        expr["brow_right"] = clamp01(expr["brow_right"] + 0.015)
        expr["head_tilt"] = clamp_signed(expr["head_tilt"] + 0.015)

    if speaking:
        # falando: reduz ligeiramente fechamento passivo do olho
        expr["eyelid"] = clamp01(expr["eyelid"] - 0.010)

    return normalize_expression(expr)


# =========================================================
# 6) PIPELINE PRINCIPAL DE MICROEXPRESSÃO
# =========================================================

def apply_micro_expression(
    base_expr: Dict[str, float],
    micro_state: Dict[str, Any],
    emotional_intensity: float = 0.3,
    speaking: bool = False,
    listening: bool = False,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Recebe a expressão base e devolve expressão enriquecida com:
    - microvariações
    - piscada
    - pequenos ajustes contextuais
    """
    if now is None:
        now = time.time()

    expr = normalize_expression(base_expr)

    if not micro_state.get("enabled", True):
        return {
            "expression": expr,
            "micro_state": micro_state,
            "blink_active": False,
        }

    # 1) ajustes sociais leves
    expr = apply_social_attention_adjustments(
        expr,
        listening=listening,
        speaking=speaking,
    )

    # 2) micro offsets
    offsets = generate_micro_offsets(
        emotional_intensity=emotional_intensity,
        speaking=speaking,
        listening=listening,
    )
    expr = apply_offsets(expr, offsets)

    # 3) decide se inicia piscada
    if should_start_blink(micro_state, now=now):
        micro_state = start_blink(micro_state, now=now)
        micro_state = schedule_next_blink(
            micro_state,
            now=now,
            speaking=speaking,
            listening=listening,
        )

    # 4) aplica piscada
    blink_delta = compute_blink_eyelid_delta(micro_state, now=now)
    blink_active = blink_delta > 0.0

    if blink_active:
        # quanto maior o delta, mais fecha a pálpebra
        expr["eyelid"] = clamp01(max(expr["eyelid"], blink_delta))

    micro_state["last_update_ts"] = now

    return {
        "expression": normalize_expression(expr),
        "micro_state": micro_state,
        "blink_active": blink_active,
    }


# =========================================================
# 7) FUNÇÕES AUXILIARES
# =========================================================

def force_blink(
    micro_state: Dict[str, Any],
    now: Optional[float] = None,
    blink_duration: float = 0.18,
) -> Dict[str, Any]:
    """
    Força uma piscada manual.
    """
    if now is None:
        now = time.time()

    micro_state = start_blink(
        micro_state,
        now=now,
        blink_duration=blink_duration,
    )

    micro_state = schedule_next_blink(micro_state, now=now)
    return micro_state


def set_micro_enabled(
    micro_state: Dict[str, Any],
    enabled: bool,
) -> Dict[str, Any]:
    micro_state["enabled"] = bool(enabled)
    return micro_state