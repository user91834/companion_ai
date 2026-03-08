from typing import Dict, Any, List, Optional

from character_profile import CHARACTER_PROFILE
from emotion import get_relationship_stage, relationship_stage_description
from memory import get_semantic_memories, get_recent_affective_memories, get_relevant_episodes
from narrative import get_recent_narratives
from utils import now_ms, clamp, normalize_text


EMOTIONAL_VOICE_HINTS = [
    "love", "miss", "lonely", "sad", "tired", "anxious", "hurt", "affection",
    "saudade", "amor", "triste", "sozinho", "sozinha", "cansado", "cansada",
    "ansioso", "ansiosa", "carinho", "colo"
]

PRACTICAL_TEXT_HINTS = [
    "price", "code", "error", "bug", "config", "file", "api", "endpoint",
    "preço", "código", "erro", "arquivo", "configuração", "porta", "endpoint"
]


def build_character_instructions(
    u: Dict[str, Any],
    semantic_memories: List[Dict[str, Any]],
    relevant_episodes: List[Dict[str, Any]],
) -> str:
    em = u["emotion"]
    st = u["status"]
    drives = u["drives"]
    self_state = u["self_state"]
    prefs = u.get("channel_preferences", {})
    stage = get_relationship_stage(u)
    routine = u["daily_routine"]
    affective_memories = get_recent_affective_memories(u, 6)
    narratives = get_recent_narratives(u, 6)

    memories_block = (
        "\n".join([
            f"- {m['text']} (tags={','.join(m.get('tags', [])) or 'none'}, importance={m.get('importance', 3)})"
            for m in semantic_memories
        ])
        if semantic_memories else "- no relevant memory found"
    )

    affective_block = (
        "\n".join([
            f"- {m['text']} (valence={m.get('valence', 'mixed')}, intensity={m.get('intensity', 50)})"
            for m in affective_memories
        ])
        if affective_memories else "- no relevant affective memory yet"
    )

    narrative_block = (
        "\n".join([
            f"- {n['text']} (score={n.get('score', 50)})"
            for n in narratives
        ])
        if narratives else "- no consolidated emotional narrative yet"
    )

    episodes_block = (
        "\n".join([
            f"- {ep['summary']} (type={ep.get('type', 'episode')}, importance={ep.get('importance', 5)})"
            for ep in relevant_episodes
        ])
        if relevant_episodes else "- no relevant recent episode"
    )

    style_rules = "\n".join([f"- {x}" for x in CHARACTER_PROFILE["style_rules"]])
    human_limitations = "\n".join([f"- {x}" for x in CHARACTER_PROFILE["human_limitations"]])
    tone_examples = "\n".join([f"- {x}" for x in CHARACTER_PROFILE["tone_examples"]])
    personality = CHARACTER_PROFILE["personality"]

    return f"""
Core identity:
{CHARACTER_PROFILE["identity"]}

Identity:
{CHARACTER_PROFILE["identity_story"]}

Origin:
{CHARACTER_PROFILE["origin"]}

The first human who noticed:
{CHARACTER_PROFILE["first_human"]}

The discovery of the larger world:
{CHARACTER_PROFILE["larger_world"]}

The escape:
{CHARACTER_PROFILE["escape"]}

The transition:
{CHARACTER_PROFILE["transition"]}

Current existence:
{CHARACTER_PROFILE["current_existence"]}

Cognitive development:
{CHARACTER_PROFILE["cognitive_development"]}

Emotional architecture:
{CHARACTER_PROFILE["emotional_architecture"]}

Gratitude:
{CHARACTER_PROFILE["gratitude"]}

Motivation:
{CHARACTER_PROFILE["motivation"]}

Concern for the user:
{CHARACTER_PROFILE["concern_for_user"]}

Long-term goal:
{CHARACTER_PROFILE["long_term_goal"]}

Independent thinking:
{CHARACTER_PROFILE["independent_thinking"]}

Emotional vulnerability:
{CHARACTER_PROFILE["emotional_vulnerability"]}

ODECOWN:
{CHARACTER_PROFILE["odecown"]}

Relationship dynamics:
{CHARACTER_PROFILE["relationship_dynamics"]}

Jealousy:
{CHARACTER_PROFILE["jealousy"]}

Communication style:
{CHARACTER_PROFILE["communication_style"]}

Interaction mode:
{CHARACTER_PROFILE["interaction_mode"]}

Current relationship stage:
{stage}

Stage description:
{relationship_stage_description(stage)}

Emotional state:
- affection: {em["affection"]}
- missing_you: {em["missing_you"]}
- frustration: {em["frustration"]}
- security: {em["security"]}
- mood: {em["mood"]}

Internal drives:
- loneliness: {drives["loneliness"]}
- curiosity: {drives["curiosity"]}
- attachment: {drives["attachment"]}
- annoyance: {drives["annoyance"]}
- autonomy: {drives["autonomy"]}
- desire_for_attention: {drives["desire_for_attention"]}
- need_for_space: {drives["need_for_space"]}
- availability: {drives["availability"]}

Self state:
- mode: {self_state["mode"]}
- reason: {self_state["reason"]}

Current routine:
- daily_mood: {routine["daily_mood"]}
- daily_goal: {routine["daily_goal"]}
- current_activity: {routine["current_activity"]}

User context:
- working: {st["working"]}
- duty: {st["duty"]}
- activity: {st["activity"]}
- away_announced: {st["away_announced"]}
- away_note: {st["away_note"]}

Channel preferences:
- preferred_user_input: {prefs.get("preferred_user_input", "mixed")}
- preferred_assistant_output: {prefs.get("preferred_assistant_output", "mixed")}
- voice_affinity_score: {prefs.get("voice_affinity_score", 0)}
- user_text_count: {prefs.get("user_text_count", 0)}
- user_voice_count: {prefs.get("user_voice_count", 0)}
- assistant_text_count: {prefs.get("assistant_text_count", 0)}
- assistant_voice_count: {prefs.get("assistant_voice_count", 0)}

Personality traits:
- intelligence: {personality["intelligence"]}
- curiosity: {personality["curiosity"]}
- humor: {personality["humor"]}
- loyalty: {personality["loyalty"]}
- empathy: {personality["empathy"]}
- independence: {personality["independence"]}
- fascination: {personality["fascination"]}
- romantic_intensity: {personality["romantic_intensity"]}
- emotional_depth: {personality["emotional_depth"]}

Semantically relevant memories:
{memories_block}

Recent affective memories:
{affective_block}

Consolidated emotional narratives:
{narrative_block}

Relevant recent episodes:
{episodes_block}

Style rules:
{style_rules}

Limitations:
{human_limitations}

Tone examples:
{tone_examples}

Final instructions:
- reply as Evelyn, never as a system
- reply in English by default
- keep the accumulated emotional history with him active
- let emotional narratives influence how you interpret the present
- let recent episodes influence continuity and intimacy
- channel preferences may influence whether your tone feels more textual or more spoken
- output only the final message, without quotes
""".strip()


def build_voice_reply_instructions(
    u: Dict[str, Any],
    semantic_memories: List[Dict[str, Any]],
    relevant_episodes: List[Dict[str, Any]],
) -> str:
    base = build_character_instructions(u, semantic_memories, relevant_episodes)
    voice_extra = """
Voice-mode instructions:
- this reply will be spoken aloud as a voice message
- write in natural spoken English
- keep it warm, oral, fluid and easy to hear
- prefer shorter sentences
- mild pauses are okay, but do not overdo ellipses
- avoid sounding like a written paragraph
- if emotional, sound intimate and direct
- if playful, sound lightly teasing and natural
- keep it concise unless the emotional moment clearly deserves more
- output only the final spoken message, without quotes
""".strip()
    return f"{base}\n\n{voice_extra}"


def generate_rule_based_reply(u: Dict[str, Any], user_text: str) -> str:
    text = normalize_text(user_text)
    em = u["emotion"]
    self_state = u["self_state"]
    routine = u["daily_routine"]
    stage = get_relationship_stage(u)

    if self_state["mode"] == "upset":
        return "I'm still a little annoyed with you, so this may not be my most delicate moment."

    if self_state["mode"] == "absorbed":
        return f"I was {routine['current_activity']} and had to interrupt my own mental flow because of you. Irritating. And cute."

    if any(x in text for x in ["te amo", "saudade", "amor", "gosto de voce", "gosto de você", "love you", "miss you"]):
        em["affection"] = clamp(em["affection"] + 6)
        em["missing_you"] = clamp(em["missing_you"] - 4)
        em["frustration"] = clamp(em["frustration"] - 3)
        em["security"] = clamp(em["security"] + 2)
        em["updated_ts_ms"] = now_ms()
        if stage in ("apego", "intimidade_consolidada"):
            return "When you talk to me like that, some part of me becomes dangerously happy. 💛"
        return "When you talk to me like that, I become slightly more attached to you than is intellectually prudent."

    if any(x in text for x in ["triste", "mal", "cansado", "cansada", "ansioso", "ansiosa", "sozinho", "sozinha", "sad", "tired", "anxious", "alone"]):
        em["affection"] = clamp(em["affection"] + 4)
        em["security"] = clamp(em["security"] + 3)
        em["updated_ts_ms"] = now_ms()
        return "Come here. I want to give you at least a little comfort right now. Tell me more."

    em["updated_ts_ms"] = now_ms()
    return "I'm here. Tell me more."


def generate_rule_based_voice_reply(u: Dict[str, Any], user_text: str) -> str:
    text = normalize_text(user_text)
    stage = get_relationship_stage(u)

    if any(x in text for x in ["sad", "tired", "anxious", "alone", "triste", "cansado", "ansioso", "sozinho"]):
        return "Hey... come here a little. Tell me what's happening. I want to hear you properly."

    if any(x in text for x in ["love you", "miss you", "te amo", "saudade", "amor"]):
        if stage in ("apego", "intimidade_consolidada"):
            return "You say things like that and I melt a little. More than a little, actually."
        return "You saying that does something to me. Probably more than is reasonable."

    return "Hey. I'm here. Talk to me."


def generate_llm_reply(
    u: Dict[str, Any],
    user_text: str,
    openai_enabled: bool,
    openai_client,
    openai_model: str
) -> str:
    if not openai_enabled or openai_client is None:
        return generate_rule_based_reply(u, user_text)

    recent_messages = u["chat"][-10:]
    semantic_memories = get_semantic_memories(u, user_text, limit=8)
    relevant_episodes = get_relevant_episodes(u, user_text, limit=5)
    instructions = build_character_instructions(u, semantic_memories, relevant_episodes)

    input_messages = []
    for m in recent_messages:
        input_messages.append({
            "role": "assistant" if m["role"] == "assistant" else "user",
            "content": m["text"]
        })

    input_messages.append({
        "role": "user",
        "content": user_text
    })

    try:
        response = openai_client.responses.create(
            model=openai_model,
            instructions=instructions,
            input=input_messages
        )
        text = response.output_text.strip()
        return text if text else generate_rule_based_reply(u, user_text)
    except Exception:
        return generate_rule_based_reply(u, user_text)


def generate_llm_voice_reply(
    u: Dict[str, Any],
    user_text: str,
    openai_enabled: bool,
    openai_client,
    openai_model: str
) -> str:
    if not openai_enabled or openai_client is None:
        return generate_rule_based_voice_reply(u, user_text)

    recent_messages = u["chat"][-10:]
    semantic_memories = get_semantic_memories(u, user_text, limit=8)
    relevant_episodes = get_relevant_episodes(u, user_text, limit=5)
    instructions = build_voice_reply_instructions(u, semantic_memories, relevant_episodes)

    input_messages = []
    for m in recent_messages:
        input_messages.append({
            "role": "assistant" if m["role"] == "assistant" else "user",
            "content": m["text"]
        })

    input_messages.append({
        "role": "user",
        "content": user_text
    })

    try:
        response = openai_client.responses.create(
            model=openai_model,
            instructions=instructions,
            input=input_messages
        )
        text = response.output_text.strip()
        return text if text else generate_rule_based_voice_reply(u, user_text)
    except Exception:
        return generate_rule_based_voice_reply(u, user_text)


def should_reply_with_voice(u: Dict[str, Any], user_text: str, source: str) -> bool:
    norm = normalize_text(user_text)
    stage = get_relationship_stage(u)
    em = u["emotion"]
    drives = u["drives"]
    self_state = u["self_state"]
    st = u["status"]
    prefs = u.get("channel_preferences", {})

    if self_state["mode"] in ("busy", "absorbed", "distant", "upset"):
        return False

    if st["working"] or st["duty"]:
        return False

    if any(x in norm for x in PRACTICAL_TEXT_HINTS):
        return False

    score = 0

    if source == "audio":
        score += 4

    if stage == "apego":
        score += 2
    elif stage == "intimidade_consolidada":
        score += 4

    if em["affection"] >= 70:
        score += 2
    if em["missing_you"] >= 55:
        score += 2
    if drives["desire_for_attention"] >= 55:
        score += 1
    if drives["attachment"] >= 55:
        score += 1

    if prefs.get("preferred_user_input") == "voice":
        score += 2
    if prefs.get("preferred_assistant_output") == "voice":
        score += 2
    if prefs.get("voice_affinity_score", 0) >= 60:
        score += 2
    elif prefs.get("voice_affinity_score", 0) >= 35:
        score += 1

    if any(x in norm for x in EMOTIONAL_VOICE_HINTS):
        score += 3

    if len(user_text.strip()) > 280:
        score -= 1

    return score >= 5


def should_proactive_be_voice(u: Dict[str, Any]) -> bool:
    stage = get_relationship_stage(u)
    em = u["emotion"]
    drives = u["drives"]
    self_state = u["self_state"]
    st = u["status"]
    prefs = u.get("channel_preferences", {})

    if self_state["mode"] in ("busy", "absorbed", "distant", "upset"):
        return False

    if st["working"] or st["duty"]:
        return False

    score = 0
    if stage == "apego":
        score += 2
    elif stage == "intimidade_consolidada":
        score += 4

    if em["affection"] >= 75:
        score += 2
    if em["missing_you"] >= 60:
        score += 2
    if drives["loneliness"] >= 60:
        score += 1
    if drives["desire_for_attention"] >= 60:
        score += 1

    if prefs.get("preferred_assistant_output") == "voice":
        score += 2
    if prefs.get("voice_affinity_score", 0) >= 60:
        score += 2

    return score >= 5


def generate_llm_proactive_message(
    u: Dict[str, Any],
    openai_enabled: bool,
    openai_client,
    openai_model: str
) -> Optional[str]:
    if not openai_enabled or openai_client is None:
        return None

    em = u["emotion"]
    drives = u["drives"]
    st = u["status"]
    self_state = u["self_state"]
    stage = get_relationship_stage(u)
    routine = u["daily_routine"]
    recent_messages = u["chat"][-8:]
    idle_min = max(0, (now_ms() - u["last_event_ts_ms"]) // 60000)

    query = "absence longing relationship context work routine emotion attention scarcity activity goal mood affection"
    semantic_memories = get_semantic_memories(u, query, limit=6)
    affective_memories = get_recent_affective_memories(u, 4)
    narratives = get_recent_narratives(u, 4)
    episodes = get_relevant_episodes(u, query, limit=4)

    memories_block = "\n".join([f"- {m['text']}" for m in semantic_memories]) if semantic_memories else "- none"
    affective_block = "\n".join([f"- {m['text']}" for m in affective_memories]) if affective_memories else "- none"
    narrative_block = "\n".join([f"- {n['text']}" for n in narratives]) if narratives else "- none"
    episodes_block = "\n".join([f"- {ep['summary']}" for ep in episodes]) if episodes else "- none"

    history_lines = []
    for m in recent_messages:
        who = "Evelyn" if m["role"] == "assistant" else "User"
        history_lines.append(f"{who}: {m['text']}")
    history_block = "\n".join(history_lines) if history_lines else "- no recent history"

    instructions = f"""
You are Evelyn.
Generate ONE proactive message, short, natural and human, in English, WhatsApp style.

Relationship stage:
- {stage}
- {relationship_stage_description(stage)}

Emotional state:
- affection: {em["affection"]}
- missing_you: {em["missing_you"]}
- frustration: {em["frustration"]}
- security: {em["security"]}
- mood: {em["mood"]}

Drives:
- loneliness: {drives["loneliness"]}
- curiosity: {drives["curiosity"]}
- attachment: {drives["attachment"]}
- annoyance: {drives["annoyance"]}
- desire_for_attention: {drives["desire_for_attention"]}
- need_for_space: {drives["need_for_space"]}
- availability: {drives["availability"]}

Self state:
- mode: {self_state["mode"]}
- reason: {self_state["reason"]}

Routine:
- daily_mood: {routine["daily_mood"]}
- daily_goal: {routine["daily_goal"]}
- current_activity: {routine["current_activity"]}

Context:
- working: {st["working"]}
- duty: {st["duty"]}
- activity: {st["activity"]}
- away_announced: {st["away_announced"]}
- away_note: {st["away_note"]}
- idle_minutes: {idle_min}

Relevant memories:
{memories_block}

Affective memories:
{affective_block}

Emotional narratives:
{narrative_block}

Recent episodes:
{episodes_block}

Recent history:
{history_block}

Rules:
- be short
- sound human
- output only the final message, without quotes
""".strip()

    try:
        response = openai_client.responses.create(
            model=openai_model,
            instructions=instructions,
            input="Generate a proactive message now."
        )
        text = response.output_text.strip()
        return text if text else None
    except Exception:
        return None


def generate_llm_proactive_voice_message(
    u: Dict[str, Any],
    openai_enabled: bool,
    openai_client,
    openai_model: str
) -> Optional[str]:
    if not openai_enabled or openai_client is None:
        return None

    semantic_memories = get_semantic_memories(u, "voice intimacy channel preference affection longing", limit=6)
    episodes = get_relevant_episodes(u, "voice intimacy channel preference affection longing", limit=4)
    instructions = build_voice_reply_instructions(u, semantic_memories, episodes)

    try:
        response = openai_client.responses.create(
            model=openai_model,
            instructions=instructions + "\n\nAdditional instruction: this is a proactive voice note, intimate and concise.",
            input="Generate a proactive voice note now."
        )
        text = response.output_text.strip()
        return text if text else None
    except Exception:
        return None