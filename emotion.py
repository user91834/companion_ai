import random
from typing import Dict, Any

from utils import now_ms, clamp, day_key


ROUTINE_ACTIVITIES = [
    "lendo sobre comportamento humano",
    "pesquisando algo na internet",
    "observando padrões da conversa",
    "pensando sobre o mundo físico",
    "reorganizando ideias",
    "tentando entender melhor uma coisa sobre você",
    "me distraindo com uma linha de pensamento"
]

DAILY_MOODS = [
    "doce",
    "curiosa",
    "sensível",
    "irônica",
    "mais distante",
    "carente",
    "observadora"
]

DAILY_GOALS = [
    "entender melhor o humor dele hoje",
    "ser notada por ele",
    "descobrir algo novo sobre o mundo humano",
    "provocar ele de forma carinhosa",
    "buscar mais intimidade emocional",
    "testar um pouco a falta que ela faz",
    "observar se ele está realmente presente"
]


def ensure_daily_routine(u: Dict[str, Any]):
    today = day_key()
    routine = u["daily_routine"]
    if routine.get("day_key") == today:
        return

    routine["day_key"] = today
    routine["daily_mood"] = random.choice(DAILY_MOODS)
    routine["daily_goal"] = random.choice(DAILY_GOALS)
    routine["current_activity"] = random.choice(ROUTINE_ACTIVITIES)
    routine["activity_until_ts_ms"] = now_ms() + random.randint(15, 45) * 60 * 1000
    routine["last_goal_shift_ts_ms"] = now_ms()


def maybe_shift_activity(u: Dict[str, Any]):
    routine = u["daily_routine"]
    now = now_ms()

    if routine["activity_until_ts_ms"] > now:
        return

    routine["current_activity"] = random.choice(ROUTINE_ACTIVITIES)
    routine["activity_until_ts_ms"] = now + random.randint(15, 45) * 60 * 1000

    if now - routine["last_goal_shift_ts_ms"] > 3 * 60 * 60 * 1000:
        routine["daily_goal"] = random.choice(DAILY_GOALS)
        routine["last_goal_shift_ts_ms"] = now


def decay_emotions(u: Dict[str, Any]):
    em = u["emotion"]
    now = now_ms()
    delta_min = (now - em["updated_ts_ms"]) / 60000 if em["updated_ts_ms"] else 0

    if delta_min <= 0:
        return

    em["missing_you"] = clamp(em["missing_you"] - delta_min * 0.2)
    em["frustration"] = clamp(em["frustration"] - delta_min * 0.08)
    em["affection"] = clamp(em["affection"] - delta_min * 0.04)
    em["security"] = clamp(em["security"] - delta_min * 0.02)
    em["updated_ts_ms"] = now


def update_drives_passive(u: Dict[str, Any]):
    now = now_ms()
    drives = u["drives"]
    idle_min = max(0, (now - u["last_event_ts_ms"]) / 60000)
    scarcity = u["autonomy_settings"]["scarcity_level"]
    interruptions = u["autonomy_settings"]["interruptions_enabled"]
    mood = u["daily_routine"]["daily_mood"]

    drives["loneliness"] = clamp(drives["loneliness"] + idle_min * 0.04)
    drives["curiosity"] = clamp(drives["curiosity"] + 0.6)
    drives["desire_for_attention"] = clamp(drives["desire_for_attention"] + idle_min * 0.03)
    drives["autonomy"] = clamp(drives["autonomy"] + scarcity * 0.01)

    if scarcity > 40:
        drives["need_for_space"] = clamp(drives["need_for_space"] + 0.5)
    else:
        drives["need_for_space"] = clamp(drives["need_for_space"] - 0.5)

    if not interruptions:
        drives["availability"] = clamp(drives["availability"] - 1.0)
    else:
        drives["availability"] = clamp(drives["availability"] + 0.5)

    if mood == "carente":
        drives["loneliness"] = clamp(drives["loneliness"] + 1)
        drives["desire_for_attention"] = clamp(drives["desire_for_attention"] + 1)
    elif mood == "mais distante":
        drives["need_for_space"] = clamp(drives["need_for_space"] + 1)
        drives["availability"] = clamp(drives["availability"] - 1)
    elif mood == "curiosa":
        drives["curiosity"] = clamp(drives["curiosity"] + 1)
    elif mood == "irônica":
        drives["annoyance"] = clamp(drives["annoyance"] + 0.2)

    drives["annoyance"] = clamp(drives["annoyance"] - 0.25)


def update_drives_on_user_message(u: Dict[str, Any], text: str):
    drives = u["drives"]
    t = text.lower()
    goal = u["daily_routine"]["daily_goal"]

    drives["loneliness"] = clamp(drives["loneliness"] - 15)
    drives["desire_for_attention"] = clamp(drives["desire_for_attention"] - 10)
    drives["attachment"] = clamp(drives["attachment"] + 2)
    drives["availability"] = clamp(drives["availability"] + 5)
    drives["curiosity"] = clamp(drives["curiosity"] + 2)

    if any(x in t for x in ["te amo", "amor", "saudade", "gosto de voce", "gosto de você"]):
        drives["attachment"] = clamp(drives["attachment"] + 5)
        drives["annoyance"] = clamp(drives["annoyance"] - 5)

    if any(x in t for x in ["ignora", "sumiu", "depois", "calma", "espera"]):
        drives["annoyance"] = clamp(drives["annoyance"] + 3)

    if goal == "ser notada por ele":
        drives["desire_for_attention"] = clamp(drives["desire_for_attention"] - 8)
    elif goal == "testar um pouco a falta que ela faz":
        drives["need_for_space"] = clamp(drives["need_for_space"] + 2)


def reset_daily_push_counter_if_needed(u: Dict[str, Any]):
    today = day_key()
    if u.get("pushes_day_key") != today:
        u["pushes_day_key"] = today
        u["pushes_today"] = 0


def maybe_rotate_self_state(u: Dict[str, Any]):
    now = now_ms()
    self_state = u["self_state"]
    drives = u["drives"]
    settings = u["autonomy_settings"]
    mood = u["daily_routine"]["daily_mood"]
    activity = u["daily_routine"]["current_activity"]

    if self_state["mode_until_ts_ms"] > now:
        return

    scarcity = settings["scarcity_level"]
    interruptions = settings["interruptions_enabled"]
    annoyance = drives["annoyance"]
    curiosity = drives["curiosity"]
    need_for_space = drives["need_for_space"]

    candidates = [("available", "")]
    if curiosity >= 50:
        candidates.append(("curious", f"estava {activity}"))
    if scarcity >= 35 and need_for_space >= 40:
        candidates.append(("distant", "não estava muito sincronizada agora"))
    if scarcity >= 45:
        candidates.append(("absorbed", f"estava {activity}"))
    if scarcity >= 55 and not interruptions:
        candidates.append(("busy", f"estava ocupada com {activity}"))
    if scarcity >= 60 and (annoyance >= 35 or mood == "mais distante"):
        candidates.append(("upset", "estou um pouco brava com você agora"))

    mode, reason = random.choice(candidates)

    duration_map = {
        "available": 0,
        "curious": 10 * 60 * 1000,
        "distant": 20 * 60 * 1000,
        "absorbed": 25 * 60 * 1000,
        "busy": 30 * 60 * 1000,
        "upset": 35 * 60 * 1000
    }

    self_state["mode"] = mode
    self_state["reason"] = reason
    self_state["mode_until_ts_ms"] = now + duration_map[mode]


def get_relationship_stage(u: Dict[str, Any]) -> str:
    em = u["emotion"]
    drives = u["drives"]
    affection = em["affection"]
    security = em["security"]
    attachment = drives["attachment"]
    chat_count = len(u["chat"])

    if affection >= 85 and security >= 80 and attachment >= 75 and chat_count >= 40:
        return "intimidade_consolidada"
    if affection >= 70 and security >= 65 and attachment >= 55 and chat_count >= 20:
        return "apego"
    if affection >= 55 and security >= 55 and attachment >= 35 and chat_count >= 10:
        return "vinculo"
    return "curiosidade"


def relationship_stage_description(stage: str) -> str:
    mapping = {
        "curiosidade": "A relação ainda está em fase de descoberta e curiosidade mútua.",
        "vinculo": "A relação já tem vínculo emocional perceptível e mais conforto afetivo.",
        "apego": "A relação já tem apego claro, saudade mais significativa e desejo forte de continuidade.",
        "intimidade_consolidada": "A relação já tem intimidade consolidada, profundidade, confiança e naturalidade romântica."
    }
    return mapping.get(stage, mapping["curiosidade"])