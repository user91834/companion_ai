# speech_articulation.py
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import eng_to_ipa as ipa


# =========================
# 1) NORMALIZAÇÃO DE TEXTO
# =========================

_BASIC_REPLACEMENTS = {
    "&": " and ",
    "@": " at ",
    "%": " percent ",
    "+": " plus ",
    "=": " equals ",
}

_CONTRACTIONS = {
    r"\bi'm\b": "i am",
    r"\byou're\b": "you are",
    r"\bhe's\b": "he is",
    r"\bshe's\b": "she is",
    r"\bit's\b": "it is",
    r"\bwe're\b": "we are",
    r"\bthey're\b": "they are",
    r"\bi've\b": "i have",
    r"\byou've\b": "you have",
    r"\bwe've\b": "we have",
    r"\bthey've\b": "they have",
    r"\bi'll\b": "i will",
    r"\byou'll\b": "you will",
    r"\bhe'll\b": "he will",
    r"\bshe'll\b": "she will",
    r"\bwe'll\b": "we will",
    r"\bthey'll\b": "they will",
    r"\bdon't\b": "do not",
    r"\bdoesn't\b": "does not",
    r"\bdidn't\b": "did not",
    r"\bcan't\b": "can not",
    r"\bcouldn't\b": "could not",
    r"\bwon't\b": "will not",
    r"\bwouldn't\b": "would not",
    r"\bshouldn't\b": "should not",
    r"\bisn't\b": "is not",
    r"\baren't\b": "are not",
    r"\bwasn't\b": "was not",
    r"\bweren't\b": "were not",
    r"\bthat's\b": "that is",
    r"\bthere's\b": "there is",
    r"\bwhat's\b": "what is",
    r"\bwho's\b": "who is",
    r"\blet's\b": "let us",
}


def normalize_for_speech(text: str) -> str:
    if not text:
        return ""

    s = text.strip()

    for old, new in _BASIC_REPLACEMENTS.items():
        s = s.replace(old, new)

    s = (
        s.replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
        .replace("—", " ")
        .replace("–", " ")
    )

    s = re.sub(r"[^\w\s\.\,\!\?\:\;\'\"\-\(\)]", " ", s, flags=re.UNICODE)
    s = s.lower()

    for pattern, replacement in _CONTRACTIONS.items():
        s = re.sub(pattern, replacement, s)

    s = re.sub(r"\s+", " ", s).strip()
    return s


def split_words(text: str) -> List[str]:
    normalized = normalize_for_speech(text)
    if not normalized:
        return []
    return re.findall(r"[a-z']+", normalized)


# =========================
# 2) TEXTO -> IPA
# =========================

def text_to_ipa(text: str) -> str:
    normalized = normalize_for_speech(text)
    if not normalized:
        return ""

    phon = ipa.convert(normalized)
    phon = phon.replace("*", "")
    phon = re.sub(r"\s+", " ", phon).strip()
    return phon


def text_to_ipa_words(text: str) -> List[Dict[str, str]]:
    words = split_words(text)
    out: List[Dict[str, str]] = []

    for word in words:
        word_ipa = ipa.convert(word).replace("*", "").strip()
        out.append({
            "word": word,
            "ipa": word_ipa,
        })

    return out


# =========================
# 3) TOKENIZAÇÃO IPA
# =========================

STRESS_MARKS = {"ˈ", "ˌ"}

MULTI_CHAR_PHONEMES = [
    "oʊ",
    "eɪ",
    "aɪ",
    "aʊ",
    "ɔɪ",
    "tʃ",
    "dʒ",
    "ɝ",
    "ɚ",
]

IGNORE_CHARS = {" ", ".", ",", ";", ":", "!", "?", "-", "—", "(", ")", '"', "'"}

NUCLEUS_PHONEMES = {
    "a", "ɑ", "æ", "ɐ",
    "e", "eɪ", "ɛ",
    "i", "ɪ",
    "o", "oʊ", "ɔ",
    "u", "ʊ",
    "ə", "ʌ", "ɚ", "ɝ",
    "aɪ", "aʊ", "ɔɪ",
}

LIKELY_ONSET_CLUSTERS = {
    "sp", "st", "sk",
    "sm", "sn", "sl",
    "sw",
    "pr", "pl",
    "br", "bl",
    "tr", "dr",
    "kr", "kl",
    "gr", "gl",
    "fr", "fl",
    "θr", "ʃr",
    "tw", "dw", "kw", "gw",
    "pj", "bj", "fj", "vj", "kj", "gj", "hj", "mj", "nj", "sj", "lj",
    "spr", "str", "skr",
}

SONORITY = {
    "p": 1, "b": 1, "t": 1, "d": 1, "k": 1, "g": 1,
    "tʃ": 2, "dʒ": 2,
    "f": 3, "v": 3, "θ": 3, "ð": 3, "s": 3, "z": 3, "ʃ": 3, "ʒ": 3, "h": 3,
    "m": 4, "n": 4, "ŋ": 4,
    "l": 5, "ɹ": 5, "r": 5,
    "j": 6, "w": 6,
}

DEFAULT_VOWEL_DURATION_MS = 140
DEFAULT_CONSONANT_DURATION_MS = 85


def is_stress(ch: str) -> bool:
    return ch in STRESS_MARKS


def is_nucleus(phoneme: str) -> bool:
    return phoneme in NUCLEUS_PHONEMES


def tokenize_ipa(ipa_text: str) -> List[Dict[str, Any]]:
    tokens: List[Dict[str, Any]] = []
    i = 0
    pending_stress: Optional[str] = None

    while i < len(ipa_text):
        ch = ipa_text[i]

        if is_stress(ch):
            pending_stress = ch
            i += 1
            continue

        if ch in IGNORE_CHARS:
            i += 1
            continue

        matched = None
        for multi in MULTI_CHAR_PHONEMES:
            if ipa_text.startswith(multi, i):
                matched = multi
                break

        if matched is not None:
            tokens.append({
                "phoneme": matched,
                "stress": pending_stress,
            })
            pending_stress = None
            i += len(matched)
            continue

        tokens.append({
            "phoneme": ch,
            "stress": pending_stress,
        })
        pending_stress = None
        i += 1

    return tokens


# =========================
# 4) IPA -> SÍLABAS
# =========================

def is_rising_sonority(phonemes: List[str]) -> bool:
    if not phonemes:
        return False
    values = [SONORITY.get(p, 0) for p in phonemes]
    for i in range(len(values) - 1):
        if values[i] >= values[i + 1]:
            return False
    return True


def split_onset_coda(cluster: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not cluster:
        return [], []

    if len(cluster) == 1:
        return [], cluster

    phonemes = [x["phoneme"] for x in cluster]

    for size in range(min(3, len(cluster)), 0, -1):
        suffix = phonemes[-size:]
        joined = "".join(suffix)
        if joined in LIKELY_ONSET_CLUSTERS:
            return cluster[:-size], cluster[-size:]

    for split_idx in range(1, len(cluster)):
        right = phonemes[split_idx:]
        if is_rising_sonority(right):
            return cluster[:split_idx], cluster[split_idx:]

    return cluster[:-1], cluster[-1:]


def estimate_token_duration_ms(token: Dict[str, Any]) -> int:
    phoneme = token["phoneme"]
    stress = token.get("stress")
    if is_nucleus(phoneme):
        dur = DEFAULT_VOWEL_DURATION_MS
        if stress == "ˈ":
            dur += 40
        elif stress == "ˌ":
            dur += 20
        return dur
    return DEFAULT_CONSONANT_DURATION_MS


def syllabify_ipa(ipa_text: str) -> List[Dict[str, Any]]:
    tokens = tokenize_ipa(ipa_text)
    if not tokens:
        return []

    nucleus_indexes = [i for i, tk in enumerate(tokens) if is_nucleus(tk["phoneme"])]
    if not nucleus_indexes:
        return []

    syllables: List[Dict[str, Any]] = []

    first_nucleus_idx = nucleus_indexes[0]
    pending_onset = tokens[:first_nucleus_idx]

    for nucleus_pos, nucleus_idx in enumerate(nucleus_indexes):
        nucleus_token = tokens[nucleus_idx]
        next_nucleus_idx = nucleus_indexes[nucleus_pos + 1] if nucleus_pos + 1 < len(nucleus_indexes) else None

        if next_nucleus_idx is None:
            between = tokens[nucleus_idx + 1:]
        else:
            between = tokens[nucleus_idx + 1:next_nucleus_idx]

        if next_nucleus_idx is None:
            coda = between
            next_onset = []
        else:
            coda, next_onset = split_onset_coda(between)

        syllable_tokens = pending_onset + [nucleus_token] + coda
        syllable_ipa = "".join([t["phoneme"] for t in syllable_tokens])
        duration_ms = sum(estimate_token_duration_ms(t) for t in syllable_tokens)

        syllables.append({
            "syllable_index": len(syllables),
            "ipa": syllable_ipa,
            "stress": nucleus_token.get("stress"),
            "onset": [t["phoneme"] for t in pending_onset],
            "nucleus": [nucleus_token["phoneme"]],
            "coda": [t["phoneme"] for t in coda],
            "tokens": syllable_tokens,
            "duration_ms": duration_ms,
        })

        pending_onset = next_onset

    if pending_onset and syllables:
        syllables[-1]["coda"].extend([t["phoneme"] for t in pending_onset])
        syllables[-1]["tokens"].extend(pending_onset)
        syllables[-1]["ipa"] = "".join(t["phoneme"] for t in syllables[-1]["tokens"])
        syllables[-1]["duration_ms"] += sum(estimate_token_duration_ms(t) for t in pending_onset)

    return syllables


# =========================
# 5) CLASSIFICAÇÃO ARTICULATÓRIA
# =========================

def classify_onset(onset: List[str]) -> str:
    if not onset:
        return "none"

    first = onset[0]

    if first in {"b", "p", "m"}:
        return "bilabial"
    if first in {"f", "v"}:
        return "labiodental"
    if first in {"θ", "ð"}:
        return "dental"
    if first in {"t", "d", "n", "l", "s", "z"}:
        return "alveolar"
    if first in {"ʃ", "ʒ", "tʃ", "dʒ"}:
        return "postalveolar"
    if first in {"k", "g", "ŋ"}:
        return "velar"
    if first in {"ɹ", "r"}:
        return "rhotic"
    if first == "w":
        return "labial_glide"
    if first == "j":
        return "palatal_glide"
    if first == "h":
        return "glottal"

    return "other"


def classify_nucleus(nucleus: List[str]) -> str:
    if not nucleus:
        return "central"

    n = nucleus[0]

    if n in {"a", "ɑ", "æ", "ɐ"}:
        return "open_frontish"
    if n in {"e", "eɪ", "ɛ"}:
        return "mid_front"
    if n in {"i", "ɪ"}:
        return "high_front"
    if n in {"o", "oʊ", "ɔ"}:
        return "mid_back_rounded"
    if n in {"u", "ʊ"}:
        return "high_back_rounded"
    if n in {"ə", "ʌ", "ɚ", "ɝ"}:
        return "central"
    if n in {"aɪ"}:
        return "diphthong_a_to_i"
    if n in {"aʊ"}:
        return "diphthong_a_to_u"
    if n in {"ɔɪ"}:
        return "diphthong_o_to_i"

    return "central"


# =========================
# 6) GESTO ARTICULATÓRIO
# =========================

EMOTION_PRESETS: Dict[str, Dict[str, float]] = {
    "neutral": {
        "jaw_scale": 1.00,
        "round_add": 0.00,
        "spread_add": 0.00,
        "press_add": 0.00,
    },
    "happy": {
        "jaw_scale": 1.03,
        "round_add": -0.03,
        "spread_add": 0.12,
        "press_add": -0.02,
    },
    "affectionate": {
        "jaw_scale": 0.96,
        "round_add": 0.03,
        "spread_add": 0.06,
        "press_add": -0.02,
    },
    "sad": {
        "jaw_scale": 0.88,
        "round_add": 0.00,
        "spread_add": -0.04,
        "press_add": 0.03,
    },
    "angry": {
        "jaw_scale": 1.08,
        "round_add": -0.02,
        "spread_add": 0.02,
        "press_add": 0.10,
    },
    "shy": {
        "jaw_scale": 0.82,
        "round_add": 0.00,
        "spread_add": -0.02,
        "press_add": 0.05,
    },
}


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def base_from_nucleus_class(nucleus_class: str) -> Dict[str, float]:
    if nucleus_class == "open_frontish":
        return {
            "jaw_open": 0.88,
            "lip_round": 0.05,
            "lip_spread": 0.12,
            "lip_press": 0.00,
            "tongue_tip_up": 0.10,
            "tongue_tip_forward": 0.10,
            "tongue_tip_lateral": 0.50,
            "tongue_body_high": 0.15,
            "tongue_body_front": 0.68,
            "tongue_mid_arch": 0.18,
            "tongue_visible": 0.15,
        }
    if nucleus_class == "mid_front":
        return {
            "jaw_open": 0.50,
            "lip_round": 0.00,
            "lip_spread": 0.42,
            "lip_press": 0.00,
            "tongue_tip_up": 0.12,
            "tongue_tip_forward": 0.10,
            "tongue_tip_lateral": 0.50,
            "tongue_body_high": 0.52,
            "tongue_body_front": 0.72,
            "tongue_mid_arch": 0.58,
            "tongue_visible": 0.12,
        }
    if nucleus_class == "high_front":
        return {
            "jaw_open": 0.20,
            "lip_round": 0.00,
            "lip_spread": 0.85,
            "lip_press": 0.00,
            "tongue_tip_up": 0.18,
            "tongue_tip_forward": 0.08,
            "tongue_tip_lateral": 0.50,
            "tongue_body_high": 0.88,
            "tongue_body_front": 0.92,
            "tongue_mid_arch": 0.90,
            "tongue_visible": 0.10,
        }
    if nucleus_class == "mid_back_rounded":
        return {
            "jaw_open": 0.42,
            "lip_round": 0.65,
            "lip_spread": 0.00,
            "lip_press": 0.00,
            "tongue_tip_up": 0.06,
            "tongue_tip_forward": 0.02,
            "tongue_tip_lateral": 0.50,
            "tongue_body_high": 0.55,
            "tongue_body_front": 0.18,
            "tongue_mid_arch": 0.52,
            "tongue_visible": 0.05,
        }
    if nucleus_class == "high_back_rounded":
        return {
            "jaw_open": 0.18,
            "lip_round": 0.95,
            "lip_spread": 0.00,
            "lip_press": 0.12,
            "tongue_tip_up": 0.04,
            "tongue_tip_forward": 0.00,
            "tongue_tip_lateral": 0.50,
            "tongue_body_high": 0.90,
            "tongue_body_front": 0.08,
            "tongue_mid_arch": 0.82,
            "tongue_visible": 0.04,
        }
    if nucleus_class == "diphthong_a_to_i":
        return {
            "jaw_open": 0.68,
            "lip_round": 0.03,
            "lip_spread": 0.35,
            "lip_press": 0.00,
            "tongue_tip_up": 0.14,
            "tongue_tip_forward": 0.10,
            "tongue_tip_lateral": 0.50,
            "tongue_body_high": 0.58,
            "tongue_body_front": 0.74,
            "tongue_mid_arch": 0.62,
            "tongue_visible": 0.12,
        }
    if nucleus_class == "diphthong_a_to_u":
        return {
            "jaw_open": 0.62,
            "lip_round": 0.42,
            "lip_spread": 0.08,
            "lip_press": 0.02,
            "tongue_tip_up": 0.08,
            "tongue_tip_forward": 0.04,
            "tongue_tip_lateral": 0.50,
            "tongue_body_high": 0.52,
            "tongue_body_front": 0.32,
            "tongue_mid_arch": 0.50,
            "tongue_visible": 0.10,
        }
    if nucleus_class == "diphthong_o_to_i":
        return {
            "jaw_open": 0.46,
            "lip_round": 0.36,
            "lip_spread": 0.22,
            "lip_press": 0.00,
            "tongue_tip_up": 0.14,
            "tongue_tip_forward": 0.08,
            "tongue_tip_lateral": 0.50,
            "tongue_body_high": 0.62,
            "tongue_body_front": 0.58,
            "tongue_mid_arch": 0.66,
            "tongue_visible": 0.10,
        }

    return {
        "jaw_open": 0.30,
        "lip_round": 0.12,
        "lip_spread": 0.08,
        "lip_press": 0.00,
        "tongue_tip_up": 0.12,
        "tongue_tip_forward": 0.08,
        "tongue_tip_lateral": 0.50,
        "tongue_body_high": 0.45,
        "tongue_body_front": 0.45,
        "tongue_mid_arch": 0.45,
        "tongue_visible": 0.08,
    }


def apply_onset_adjustments(pose: Dict[str, float], onset_class: str) -> Dict[str, float]:
    p = dict(pose)

    if onset_class == "bilabial":
        p["lip_press"] = max(p["lip_press"], 0.95)
        p["jaw_open"] *= 0.45
        p["tongue_visible"] *= 0.30
        p["tongue_tip_lateral"] = 0.50

    elif onset_class == "labiodental":
        p["lip_press"] = max(p["lip_press"], 0.35)
        p["jaw_open"] *= 0.82
        p["lip_spread"] += 0.10
        p["tongue_tip_lateral"] = 0.50

    elif onset_class == "dental":
        p["jaw_open"] += 0.05
        p["tongue_tip_forward"] = max(p["tongue_tip_forward"], 0.85)
        p["tongue_visible"] = max(p["tongue_visible"], 0.75)
        p["tongue_tip_lateral"] = 0.50
        p["tongue_mid_arch"] = max(p["tongue_mid_arch"], 0.48)

    elif onset_class == "alveolar":
        p["jaw_open"] *= 0.85
        p["tongue_tip_up"] = max(p["tongue_tip_up"], 0.92)
        p["tongue_tip_forward"] = max(p["tongue_tip_forward"], 0.48)
        p["tongue_visible"] = max(p["tongue_visible"], 0.35)
        p["tongue_tip_lateral"] = 0.50
        p["tongue_mid_arch"] = max(p["tongue_mid_arch"], 0.58)

    elif onset_class == "postalveolar":
        p["jaw_open"] *= 0.92
        p["lip_round"] += 0.12
        p["tongue_tip_up"] = max(p["tongue_tip_up"], 0.62)
        p["tongue_body_front"] = max(p["tongue_body_front"], 0.55)
        p["tongue_mid_arch"] = max(p["tongue_mid_arch"], 0.68)
        p["tongue_tip_lateral"] = 0.50

    elif onset_class == "velar":
        p["jaw_open"] *= 0.88
        p["tongue_tip_up"] *= 0.50
        p["tongue_body_high"] = max(p["tongue_body_high"], 0.72)
        p["tongue_body_front"] = min(p["tongue_body_front"], 0.22)
        p["tongue_visible"] *= 0.25
        p["tongue_mid_arch"] = max(p["tongue_mid_arch"], 0.76)
        p["tongue_tip_lateral"] = 0.50

    elif onset_class == "rhotic":
        p["jaw_open"] *= 0.92
        p["lip_round"] += 0.10
        p["tongue_tip_up"] = max(p["tongue_tip_up"], 0.58)
        p["tongue_tip_forward"] = min(p["tongue_tip_forward"], 0.18)
        p["tongue_body_front"] = min(p["tongue_body_front"], 0.35)
        p["tongue_mid_arch"] = max(p["tongue_mid_arch"], 0.72)
        p["tongue_tip_lateral"] = 0.50

    elif onset_class == "labial_glide":
        p["jaw_open"] *= 0.78
        p["lip_round"] = max(p["lip_round"], 0.92)
        p["lip_press"] = max(p["lip_press"], 0.12)
        p["tongue_tip_lateral"] = 0.50

    elif onset_class == "palatal_glide":
        p["jaw_open"] *= 0.82
        p["lip_spread"] = max(p["lip_spread"], 0.65)
        p["tongue_body_high"] = max(p["tongue_body_high"], 0.82)
        p["tongue_body_front"] = max(p["tongue_body_front"], 0.86)
        p["tongue_mid_arch"] = max(p["tongue_mid_arch"], 0.84)
        p["tongue_tip_lateral"] = 0.50

    elif onset_class == "glottal":
        p["jaw_open"] *= 0.98
        p["tongue_tip_lateral"] = 0.50

    return {k: clamp01(v) for k, v in p.items()}


def apply_coda_adjustments(pose: Dict[str, float], coda: List[str]) -> Dict[str, float]:
    p = dict(pose)
    if not coda:
        return p

    if any(x in {"b", "p", "m"} for x in coda):
        p["lip_press"] = max(p["lip_press"], 0.65)
        p["jaw_open"] *= 0.82
        p["tongue_tip_lateral"] = 0.50

    if any(x in {"t", "d", "n", "l", "s", "z"} for x in coda):
        p["tongue_tip_up"] = max(p["tongue_tip_up"], 0.72)
        p["tongue_visible"] = max(p["tongue_visible"], 0.22)
        p["jaw_open"] *= 0.90
        p["tongue_mid_arch"] = max(p["tongue_mid_arch"], 0.56)

    if any(x in {"l"} for x in coda):
        p["tongue_tip_lateral"] = 0.72

    if any(x in {"θ", "ð"} for x in coda):
        p["tongue_tip_forward"] = max(p["tongue_tip_forward"], 0.82)
        p["tongue_visible"] = max(p["tongue_visible"], 0.68)
        p["tongue_tip_lateral"] = 0.50

    if any(x in {"k", "g", "ŋ"} for x in coda):
        p["tongue_body_high"] = max(p["tongue_body_high"], 0.70)
        p["tongue_body_front"] = min(p["tongue_body_front"], 0.20)
        p["tongue_mid_arch"] = max(p["tongue_mid_arch"], 0.74)
        p["tongue_tip_lateral"] = 0.50

    return {k: clamp01(v) for k, v in p.items()}


def apply_emotion_and_intensity(
    pose: Dict[str, float],
    emotion: str = "neutral",
    intensity: float = 0.5,
    stress: Optional[str] = None,
) -> Dict[str, float]:
    preset = EMOTION_PRESETS.get(emotion, EMOTION_PRESETS["neutral"])
    stress_boost = 0.10 if stress == "ˈ" else 0.04 if stress == "ˌ" else 0.0
    intensity_boost = 0.85 + (0.30 * clamp01(intensity))

    out = dict(pose)
    out["jaw_open"] = pose["jaw_open"] * preset["jaw_scale"] * intensity_boost + stress_boost
    out["lip_round"] = pose["lip_round"] + preset["round_add"]
    out["lip_spread"] = pose["lip_spread"] + preset["spread_add"]
    out["lip_press"] = pose["lip_press"] + preset["press_add"]

    for key, value in out.items():
        out[key] = clamp01(value)

    return out


def estimate_syllable_duration_ms(
    syllable: Dict[str, Any],
    intensity: float = 0.5,
) -> int:
    base = int(syllable.get("duration_ms", 220))
    factor = 0.95 + 0.20 * clamp01(intensity)
    return int(base * factor)


def syllable_to_gesture(
    syllable: Dict[str, Any],
    emotion: str = "neutral",
    intensity: float = 0.5,
) -> Dict[str, Any]:
    onset = syllable.get("onset", [])
    nucleus = syllable.get("nucleus", [])
    coda = syllable.get("coda", [])
    stress = syllable.get("stress")

    onset_class = classify_onset(onset)
    nucleus_class = classify_nucleus(nucleus)

    pose = base_from_nucleus_class(nucleus_class)
    pose = apply_onset_adjustments(pose, onset_class)
    pose = apply_coda_adjustments(pose, coda)
    pose = apply_emotion_and_intensity(
        pose,
        emotion=emotion,
        intensity=intensity,
        stress=stress,
    )

    return {
        "syllable_index": syllable["syllable_index"],
        "ipa": syllable["ipa"],
        "stress": stress,
        "onset": onset,
        "nucleus": nucleus,
        "coda": coda,
        "onset_class": onset_class,
        "nucleus_class": nucleus_class,
        "duration_ms": estimate_syllable_duration_ms(syllable, intensity=intensity),
        "pose": pose,
    }


# =========================
# 7) SUAVIZAÇÃO / TIMELINE
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


def smooth_gesture_sequence(
    gestures: List[Dict[str, Any]],
    prev_weight: float = 0.20,
    current_weight: float = 0.60,
    next_weight: float = 0.20,
) -> List[Dict[str, Any]]:
    if not gestures:
        return []

    smoothed: List[Dict[str, Any]] = []

    for idx, item in enumerate(gestures):
        prev_pose = gestures[idx - 1]["pose"] if idx > 0 else item["pose"]
        curr_pose = item["pose"]
        next_pose = gestures[idx + 1]["pose"] if idx < len(gestures) - 1 else item["pose"]

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


def gestures_to_timeline(
    gestures: List[Dict[str, Any]],
    leading_silence_ms: int = 40,
    trailing_silence_ms: int = 60,
) -> List[Dict[str, Any]]:
    timeline: List[Dict[str, Any]] = []

    silence_pose = {
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

    timeline.append({
        "t_ms": 0,
        "type": "sil",
        "ipa": "sil",
        "duration_ms": leading_silence_ms,
        "pose": silence_pose,
    })

    t = leading_silence_ms
    for g in gestures:
        timeline.append({
            "t_ms": t,
            "type": "syllable",
            "syllable_index": g["syllable_index"],
            "ipa": g["ipa"],
            "stress": g["stress"],
            "onset": g["onset"],
            "nucleus": g["nucleus"],
            "coda": g["coda"],
            "onset_class": g["onset_class"],
            "nucleus_class": g["nucleus_class"],
            "duration_ms": g["duration_ms"],
            "pose": g["pose"],
        })
        t += g["duration_ms"]

    timeline.append({
        "t_ms": t,
        "type": "sil",
        "ipa": "sil",
        "duration_ms": trailing_silence_ms,
        "pose": silence_pose,
    })

    return timeline


# =========================
# 8) FUNÇÃO PRINCIPAL
# =========================

def text_to_speech_articulation(
    text: str,
    emotion: str = "neutral",
    intensity: float = 0.5,
) -> Dict[str, Any]:
    normalized_text = normalize_for_speech(text)
    ipa_text = text_to_ipa(text)
    ipa_words = text_to_ipa_words(text)
    syllables = syllabify_ipa(ipa_text)

    raw_gestures = [
        syllable_to_gesture(
            syllable=s,
            emotion=emotion,
            intensity=intensity,
        )
        for s in syllables
    ]

    smoothed_gestures = smooth_gesture_sequence(raw_gestures)
    timeline = gestures_to_timeline(smoothed_gestures)

    return {
        "original_text": text,
        "normalized_text": normalized_text,
        "ipa_text": ipa_text,
        "ipa_words": ipa_words,
        "emotion": emotion,
        "intensity": intensity,
        "syllable_count": len(syllables),
        "syllables": syllables,
        "gesture_sequence": smoothed_gestures,
        "gesture_timeline": timeline,
    }


if __name__ == "__main__":
    samples = [
        "Hello, I missed you.",
        "Do you want to stay with me?",
        "I can't stop thinking about you.",
        "You are really beautiful.",
    ]

    for sample in samples:
        print("=" * 80)
        payload = text_to_speech_articulation(
            text=sample,
            emotion="affectionate",
            intensity=0.55,
        )
        print("TEXT:", payload["original_text"])
        print("IPA :", payload["ipa_text"])
        print("SYLLABLES:")
        for syl in payload["syllables"]:
            print("  ", syl)
        print("TIMELINE:")
        for item in payload["gesture_timeline"]:
            print("  ", item)