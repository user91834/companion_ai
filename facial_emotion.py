from __future__ import annotations

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
    """
    Normaliza os valores da expressão.
    - mouth_smile e head_tilt podem ir de -1.0 a 1.0
    - os demais ficam entre 0.0 e 1.0
    """
    normalized = dict(DEFAULT_EXPRESSION)

    for key in SERVO_KEYS:
        value = expr.get(key, DEFAULT_EXPRESSION[key])

        if key in ("mouth_smile", "head_tilt"):
            normalized[key] = clamp_signed(value)
        else:
            normalized[key] = clamp01(value)

    return normalized


# =========================================================
# 2) EMOÇÕES DISCRETAS DA EVELYN
# =========================================================

FACIAL_EMOTIONS: Dict[str, Dict[str, float]] = {
    "neutral": {
        "brow_left": 0.5,
        "brow_right": 0.5,
        "eyelid": 0.5,
        "mouth_smile": 0.0,
        "mouth_open": 0.0,
        "cheek_raise": 0.0,
        "head_tilt": 0.0,
    },
    "curious": {
        "brow_left": 0.78,
        "brow_right": 0.64,
        "eyelid": 0.46,
        "mouth_smile": 0.12,
        "mouth_open": 0.05,
        "cheek_raise": 0.08,
        "head_tilt": 0.28,
    },
    "affectionate": {
        "brow_left": 0.60,
        "brow_right": 0.60,
        "eyelid": 0.38,
        "mouth_smile": 0.68,
        "mouth_open": 0.06,
        "cheek_raise": 0.58,
        "head_tilt": 0.24,
    },
    "happy": {
        "brow_left": 0.58,
        "brow_right": 0.58,
        "eyelid": 0.32,
        "mouth_smile": 0.82,
        "mouth_open": 0.12,
        "cheek_raise": 0.70,
        "head_tilt": 0.08,
    },
    "playful": {
        "brow_left": 0.72,
        "brow_right": 0.48,
        "eyelid": 0.40,
        "mouth_smile": 0.70,
        "mouth_open": 0.10,
        "cheek_raise": 0.55,
        "head_tilt": 0.34,
    },
    "sad": {
        "brow_left": 0.78,
        "brow_right": 0.78,
        "eyelid": 0.66,
        "mouth_smile": -0.34,
        "mouth_open": 0.00,
        "cheek_raise": 0.00,
        "head_tilt": -0.18,
    },
    "concerned": {
        "brow_left": 0.74,
        "brow_right": 0.74,
        "eyelid": 0.56,
        "mouth_smile": -0.05,
        "mouth_open": 0.03,
        "cheek_raise": 0.04,
        "head_tilt": 0.04,
    },
    "surprised": {
        "brow_left": 0.90,
        "brow_right": 0.90,
        "eyelid": 0.20,
        "mouth_smile": 0.00,
        "mouth_open": 0.72,
        "cheek_raise": 0.08,
        "head_tilt": 0.10,
    },
    "shy": {
        "brow_left": 0.60,
        "brow_right": 0.60,
        "eyelid": 0.56,
        "mouth_smile": 0.46,
        "mouth_open": 0.00,
        "cheek_raise": 0.42,
        "head_tilt": 0.38,
    },
    "thoughtful": {
        "brow_left": 0.68,
        "brow_right": 0.60,
        "eyelid": 0.48,
        "mouth_smile": 0.02,
        "mouth_open": 0.00,
        "cheek_raise": 0.05,
        "head_tilt": 0.14,
    },
}


# =========================================================
# 3) ESTADO EMOCIONAL CONTÍNUO
# =========================================================

def make_default_emotional_state() -> Dict[str, float]:
    """
    Estado contínuo:
    - valence: negativo ↔ positivo
    - arousal: calmo ↔ energizado
    - affection: distância ↔ vínculo
    """
    return {
        "valence": 0.0,    # -1.0 a 1.0
        "arousal": 0.25,   # 0.0 a 1.0
        "affection": 0.40, # 0.0 a 1.0
    }


def normalize_emotional_state(state: Dict[str, float]) -> Dict[str, float]:
    return {
        "valence": clamp_signed(state.get("valence", 0.0)),
        "arousal": clamp01(state.get("arousal", 0.25)),
        "affection": clamp01(state.get("affection", 0.40)),
    }


# =========================================================
# 4) RESSONÂNCIA EMOCIONAL / "NEURÔNIOS-ESPELHO"
# =========================================================

USER_TO_EVELYN_RESONANCE: Dict[str, Dict[str, float]] = {
    # usuário feliz -> Evelyn feliz
    "happy": {
        "valence": 0.70,
        "arousal": 0.55,
        "affection": 0.55,
    },
    # usuário triste -> Evelyn não replica tristeza pura;
    # tende mais para preocupação/acolhimento
    "sad": {
        "valence": -0.25,
        "arousal": 0.22,
        "affection": 0.78,
    },
    # usuário carinhoso -> Evelyn afetuosa
    "affection": {
        "valence": 0.65,
        "arousal": 0.30,
        "affection": 0.90,
    },
    # usuário irritado -> Evelyn preocupada/atenta
    "angry": {
        "valence": -0.18,
        "arousal": 0.58,
        "affection": 0.45,
    },
    # usuário confuso -> Evelyn curiosa e engajada
    "confused": {
        "valence": 0.08,
        "arousal": 0.42,
        "affection": 0.52,
    },
    # usuário brincalhão -> Evelyn playful
    "playful": {
        "valence": 0.60,
        "arousal": 0.62,
        "affection": 0.62,
    },
    # usuário sozinho/carente -> Evelyn acolhedora
    "lonely": {
        "valence": 0.10,
        "arousal": 0.20,
        "affection": 0.92,
    },
    # fallback
    "neutral": {
        "valence": 0.00,
        "arousal": 0.30,
        "affection": 0.45,
    },
}


def mirror_user_emotion(user_emotion: Optional[str]) -> Dict[str, float]:
    """
    Converte emoção detectada do usuário em tendência emocional interna da Evelyn.
    """
    if not user_emotion:
        user_emotion = "neutral"

    mirrored = USER_TO_EVELYN_RESONANCE.get(
        user_emotion,
        USER_TO_EVELYN_RESONANCE["neutral"],
    )

    return normalize_emotional_state(mirrored)


def blend_emotional_state(
    current_state: Dict[str, float],
    mirrored_state: Dict[str, float],
    resonance_weight: float = 0.25,
) -> Dict[str, float]:
    """
    Mistura o estado atual da Evelyn com a ressonância emocional do usuário.
    resonance_weight:
        0.0 -> ignora usuário
        1.0 -> copia totalmente a ressonância
    """
    current = normalize_emotional_state(current_state)
    mirrored = normalize_emotional_state(mirrored_state)
    w = clamp01(resonance_weight)

    new_state = {
        "valence": current["valence"] * (1.0 - w) + mirrored["valence"] * w,
        "arousal": current["arousal"] * (1.0 - w) + mirrored["arousal"] * w,
        "affection": current["affection"] * (1.0 - w) + mirrored["affection"] * w,
    }

    return normalize_emotional_state(new_state)


def update_state_from_user_emotion(
    current_state: Dict[str, float],
    user_emotion: Optional[str],
    resonance_weight: float = 0.25,
) -> Dict[str, float]:
    mirrored = mirror_user_emotion(user_emotion)
    return blend_emotional_state(current_state, mirrored, resonance_weight=resonance_weight)


# =========================================================
# 5) MAPEAMENTO DE ESTADO CONTÍNUO -> EXPRESSÃO FACIAL
# =========================================================

def emotional_state_to_expression(state: Dict[str, float]) -> Dict[str, float]:
    """
    Gera expressão facial teórica a partir do estado contínuo.
    """
    st = normalize_emotional_state(state)

    valence = st["valence"]      # -1..1
    arousal = st["arousal"]      # 0..1
    affection = st["affection"]  # 0..1

    expr = dict(DEFAULT_EXPRESSION)

    # Sobrancelhas:
    # mais energia = mais ativação
    brow_base = 0.50 + arousal * 0.18
    expr["brow_left"] = brow_base
    expr["brow_right"] = brow_base

    # Pálpebras:
    # mais arousal = olhos mais abertos -> valor menor do eyelid
    expr["eyelid"] = clamp01(0.58 - arousal * 0.28)

    # Sorriso:
    # positivo sobe, negativo desce
    expr["mouth_smile"] = clamp_signed(valence * 0.85)

    # Boca aberta:
    # surpresa / energia / alegria intensa
    expr["mouth_open"] = clamp01(max(0.0, arousal - 0.35) * 0.55)

    # Bochecha:
    # só sobe de verdade no positivo
    expr["cheek_raise"] = clamp01(max(0.0, valence) * 0.75)

    # Inclinação da cabeça:
    # vínculo afetivo aumenta inclinação
    expr["head_tilt"] = clamp_signed((affection - 0.5) * 0.7)

    # Se valência negativa, pálpebra cai um pouco e sobrancelha sobe mais
    if valence < 0.0:
        sadness_factor = abs(valence)
        expr["eyelid"] = clamp01(expr["eyelid"] + sadness_factor * 0.12)
        expr["brow_left"] = clamp01(expr["brow_left"] + sadness_factor * 0.10)
        expr["brow_right"] = clamp01(expr["brow_right"] + sadness_factor * 0.10)

    return normalize_expression(expr)


# =========================================================
# 6) APOIO A EMOÇÕES DISCRETAS
# =========================================================

def get_discrete_expression(emotion_name: str) -> Dict[str, float]:
    expr = FACIAL_EMOTIONS.get(emotion_name, FACIAL_EMOTIONS["neutral"])
    return normalize_expression(expr)


def discrete_emotion_to_state(emotion_name: str) -> Dict[str, float]:
    """
    Caso você queira transformar uma emoção discreta em estado contínuo.
    """
    mapping = {
        "neutral": {"valence": 0.00, "arousal": 0.25, "affection": 0.40},
        "curious": {"valence": 0.15, "arousal": 0.45, "affection": 0.50},
        "affectionate": {"valence": 0.65, "arousal": 0.30, "affection": 0.90},
        "happy": {"valence": 0.85, "arousal": 0.55, "affection": 0.55},
        "playful": {"valence": 0.70, "arousal": 0.65, "affection": 0.62},
        "sad": {"valence": -0.70, "arousal": 0.20, "affection": 0.45},
        "concerned": {"valence": -0.15, "arousal": 0.45, "affection": 0.68},
        "surprised": {"valence": 0.05, "arousal": 0.90, "affection": 0.45},
        "shy": {"valence": 0.30, "arousal": 0.25, "affection": 0.75},
        "thoughtful": {"valence": 0.05, "arousal": 0.35, "affection": 0.48},
    }
    return normalize_emotional_state(mapping.get(emotion_name, mapping["neutral"]))


# =========================================================
# 7) TRANSIÇÃO SUAVE ENTRE EXPRESSÕES
# =========================================================

def interpolate_expression(
    current_expr: Dict[str, float],
    target_expr: Dict[str, float],
    speed: float = 0.12,
) -> Dict[str, float]:
    """
    Aproxima suavemente current -> target.
    speed:
        0.01 = muito lento
        0.10 = suave
        0.30 = rápido
        1.00 = salto direto
    """
    current = normalize_expression(current_expr)
    target = normalize_expression(target_expr)
    s = clamp01(speed)

    new_expr: Dict[str, float] = {}

    for key in SERVO_KEYS:
        c = current[key]
        t = target[key]
        new_expr[key] = c + (t - c) * s

    return normalize_expression(new_expr)


# =========================================================
# 8) FUNÇÕES DE ALTO NÍVEL
# =========================================================

def build_expression_from_state(
    emotional_state: Dict[str, float],
) -> Dict[str, float]:
    return emotional_state_to_expression(emotional_state)


def build_expression_from_discrete_emotion(
    emotion_name: str,
    use_continuous_model: bool = False,
) -> Dict[str, float]:
    """
    Pode usar:
    - tabela discreta direta
    - ou converter emoção em estado contínuo e daí em expressão
    """
    if use_continuous_model:
        state = discrete_emotion_to_state(emotion_name)
        return emotional_state_to_expression(state)

    return get_discrete_expression(emotion_name)


def build_expression_from_user_emotion(
    current_state: Dict[str, float],
    user_emotion: Optional[str],
    resonance_weight: float = 0.25,
) -> Dict[str, Any]:
    """
    Pipeline completo:
    1. lê emoção do usuário
    2. atualiza estado emocional da Evelyn por ressonância
    3. gera expressão alvo
    """
    new_state = update_state_from_user_emotion(
        current_state=current_state,
        user_emotion=user_emotion,
        resonance_weight=resonance_weight,
    )

    target_expression = build_expression_from_state(new_state)

    return {
        "state": new_state,
        "expression": target_expression,
    }