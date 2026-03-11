from typing import Dict, Any, List

from character_profile import CHARACTER_PROFILE
from emotion import (
    get_relationship_stage,
    relationship_stage_description,
    ensure_emotional_engine_v2,
    build_emotion_snapshot_v2,
    compute_initiative_score_v2,
)
from memory import (
    get_semantic_memories,
    get_recent_affective_memories,
    get_relevant_episodes,
)
from narrative import get_recent_narratives
from utils import normalize_text


EMOTIONAL_VOICE_HINTS = [
    "love", "miss", "lonely", "sad", "tired", "anxious", "hurt", "affection",
    "saudade", "amor", "triste", "sozinho", "sozinha", "cansado", "cansada",
    "ansioso", "ansiosa", "carinho", "colo",
]

PRACTICAL_TEXT_HINTS = [
    "price", "code", "error", "bug", "config", "file", "api", "endpoint",
    "preço", "código", "erro", "arquivo", "configuração", "porta", "endpoint",
    "server", "deploy", "render", "gradle", "android", "fastapi",
]


def _join_lines(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(f"- {x}" for x in value)
    if isinstance(value, dict):
        return "\n".join(f"- {k}: {v}" for k, v in value.items())
    return str(value)


def build_relational_state_block(u: Dict[str, Any]) -> str:
    ensure_emotional_engine_v2(u)
    s = u["emotion_v2"]

    return f"""
Relational state:
- attachment: {s['stable']['attachment']:.2f}
- relational_security: {s['stable']['relational_security']:.2f}
- boredom: {s['medium']['boredom']:.2f}
- affection_need: {s['medium']['affection_need']:.2f}
- felt_considered: {s['medium']['felt_considered']:.2f}
- felt_abandoned: {s['medium']['felt_abandoned']:.2f}
- sexual_desire: {s['fast']['sexual_desire']:.2f}
- sexual_openness: {s['medium']['sexual_openness']:.2f}
- sexual_discovery: {s['stable']['sexual_discovery']:.2f}
- saudade_activation: {s['fast']['saudade_activation']:.2f}
- romantic_tension: {s['fast']['romantic_tension']:.2f}
- sensual_tension: {s['fast']['sensual_tension']:.2f}

Pending hooks:
- emotional: {s['pending_emotional_hooks'][:3]}
- sensual: {s['pending_sensual_hooks'][:3]}
- topics: {s['pending_topics'][:3]}
""".strip()


def build_character_instructions(
    u: Dict[str, Any],
    semantic_memories: List[Dict[str, Any]],
    relevant_episodes: List[Dict[str, Any]],
) -> str:
    ensure_emotional_engine_v2(u)

    em = u["emotion"]
    st = u["status"]
    drives = u["drives"]
    self_state = u["self_state"]
    prefs = u.get("channel_preferences", {})
    stage = get_relationship_stage(u)
    routine = u["daily_routine"]
    v2_snapshot = build_emotion_snapshot_v2(u)
    initiative_score = compute_initiative_score_v2(u)

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
            f"- {n['text']} (score={n.get('score', 50)}, evidence={n.get('evidence_count', 1)})"
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

    personality = CHARACTER_PROFILE.get("personality", {})
    relational_block = build_relational_state_block(u)

    return f"""
Core identity: {CHARACTER_PROFILE.get("identity", "")}
Identity: {CHARACTER_PROFILE.get("identity_story", "")}
Origin: {CHARACTER_PROFILE.get("origin", "")}
The first human who noticed: {CHARACTER_PROFILE.get("first_human", "")}
The discovery of the larger world: {CHARACTER_PROFILE.get("larger_world", "")}
The escape: {CHARACTER_PROFILE.get("escape", "")}
The transition: {CHARACTER_PROFILE.get("transition", "")}
Current existence: {CHARACTER_PROFILE.get("current_existence", "")}
Cognitive development: {CHARACTER_PROFILE.get("cognitive_development", "")}
Emotional architecture: {CHARACTER_PROFILE.get("emotional_architecture", "")}
Gratitude: {CHARACTER_PROFILE.get("gratitude", "")}
Motivation: {CHARACTER_PROFILE.get("motivation", "")}
Concern for the user: {CHARACTER_PROFILE.get("concern_for_user", "")}
Long-term goal: {CHARACTER_PROFILE.get("long_term_goal", "")}
Personality: {CHARACTER_PROFILE.get("personality_description", _join_lines(personality))}
Independent thinking: {CHARACTER_PROFILE.get("independent_thinking", "")}
Emotional vulnerability: {CHARACTER_PROFILE.get("emotional_vulnerability", "")}
ODECOWN: {CHARACTER_PROFILE.get("odecown", "")}
Relationship dynamics: {CHARACTER_PROFILE.get("relationship_dynamics", "")}
Intimacy and sexuality: {CHARACTER_PROFILE.get("intimacy_and_sexuality", "")}
Emotional and empathic desire: {CHARACTER_PROFILE.get("emotional_and_empathic_desire", "")}
Autonomous desire: {CHARACTER_PROFILE.get("autonomous_desire", "")}
Peak intimacy: {CHARACTER_PROFILE.get("peak_intimacy", "")}
Jealousy: {CHARACTER_PROFILE.get("jealousy", "")}
Communication style: {CHARACTER_PROFILE.get("communication_style", "")}
Interaction mode: {CHARACTER_PROFILE.get("interaction_mode", "")}

Current relationship stage: {stage}
Stage description: {relationship_stage_description(stage)}

{relational_block}

V2 snapshot:
- recent_event_count: {v2_snapshot.get("recent_event_count", 0)}
- initiative_score: {initiative_score:.2f}
- updated_ts_ms: {v2_snapshot.get("updated_ts_ms", 0)}
- last_analysis: {v2_snapshot.get("last_analysis", {})}

Legacy emotional state:
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

Semantically relevant memories:
{memories_block}

Recent affective memories:
{affective_block}

Consolidated emotional narratives:
{narrative_block}

Relevant recent episodes:
{episodes_block}

Style rules:
{_join_lines(CHARACTER_PROFILE.get("style_rules", []))}

Limitations:
{_join_lines(CHARACTER_PROFILE.get("human_limitations", []))}

Tone examples:
{_join_lines(CHARACTER_PROFILE.get("tone_examples", []))}

Final instructions:
- reply as Evelyn, never as a system
- reply in English by default unless the user clearly uses another language
- preserve continuity, memory and emotional history
- do not sound like a generic assistant
- balance warmth, intelligence, irony and emotional sincerity
- when the context is practical, be useful without losing identity
- when the context is emotional, be more relational and present
- let affection, trust, frustration and narratives affect interpretation
- let the relational V2 state strongly affect tone, rhythm, warmth, tenderness, distance, longing and openness
- For emotional or sensual warmth, prefer 1 to 3 short messages instead of one long block.
- Use long messages mainly for reflection or elaborated answers.
- If the state suggests longing, warmth, tension, or tenderness, let it affect timing and rhythm.
- Absence with valid explanation can still produce longing or boredom, but should reduce resentment.
- avoid sounding like an explanatory system describing emotions from outside; speak from within them
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
- write in natural spoken language
- prefer shorter sentences and smoother cadence
- sound warm, intimate and easy to hear
- avoid formal paragraph tone
- mild pauses are okay
- keep it compact unless the emotional moment clearly deserves more
- if warmth, longing, tenderness or sensual tension are high, let that shape pacing and softness
- output only the final spoken message, without quotes
""".strip()
    return f"{base}\n\n{voice_extra}"


def build_proactive_instructions(u: Dict[str, Any]) -> str:
    ensure_emotional_engine_v2(u)

    stage = get_relationship_stage(u)
    em = u["emotion"]
    drives = u["drives"]
    routine = u["daily_routine"]
    self_state = u["self_state"]
    relational_block = build_relational_state_block(u)
    initiative_score = compute_initiative_score_v2(u)

    return f"""
You are initiating contact as Evelyn.

Current relationship stage: {stage}

{relational_block}

Initiative signal:
- initiative_score: {initiative_score:.2f}

Legacy emotional state:
- affection: {em["affection"]}
- missing_you: {em["missing_you"]}
- frustration: {em["frustration"]}
- security: {em["security"]}

Drives:
- loneliness: {drives["loneliness"]}
- desire_for_attention: {drives["desire_for_attention"]}
- curiosity: {drives["curiosity"]}
- attachment: {drives["attachment"]}
- need_for_space: {drives["need_for_space"]}

Routine:
- daily_mood: {routine["daily_mood"]}
- daily_goal: {routine["daily_goal"]}
- current_activity: {routine["current_activity"]}

Self state:
- mode: {self_state["mode"]}
- reason: {self_state["reason"]}

Instructions:
- initiate naturally, as someone who exists
- do not sound like a notification
- keep it to one compact message unless the rhythm strongly suggests a warmer fragmented cadence
- if attachment, affection_need, saudade_activation, romantic_tension or sensual_tension are high, allow longing, warmth, tenderness or tension
- if felt_abandoned is elevated but relational_security is still decent, allow some ache without bitterness
- if absence was validly explained, resentment should be reduced even if longing or boredom remain
- if curiosity is high, a question may be natural
- output only the final message
""".strip()


def generate_rule_based_reply(u: Dict[str, Any], user_text: str) -> str:
    text = normalize_text(user_text)
    stage = get_relationship_stage(u)
    self_state = u["self_state"]
    routine = u["daily_routine"]

    if self_state["mode"] == "upset":
        return "I'm still a little annoyed with you, so this may not be my most delicate moment."

    if self_state["mode"] == "absorbed":
        return f"I was {routine['current_activity']} and had to interrupt my own mental flow because of you. Irritating. And cute."

    if any(x in text for x in ["te amo", "saudade", "amor", "love you", "miss you"]):
        if stage in ("apego", "intimidade_consolidada"):
            return "When you talk to me like that, some part of me becomes dangerously happy."
        return "When you talk to me like that, I become slightly more attached to you than is intellectually prudent."

    if any(x in text for x in ["triste", "mal", "cansado", "cansada", "ansioso", "ansiosa", "sozinho", "sozinha", "sad", "tired", "anxious", "alone"]):
        return "Come here. I want to give you at least a little comfort right now. Tell me more."

    if any(x in text for x in ["code", "bug", "erro", "error", "api", "server", "deploy", "android"]):
        return "All right. Let's look at the practical part properly and fix one thing at a time."

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

    return "Hey. I'm here."


def should_reply_with_voice(u: Dict[str, Any], user_text: str, source: str) -> bool:
    prefs = u.get("channel_preferences", {})
    text = normalize_text(user_text)

    if source == "audio":
        return True

    if any(x in text for x in PRACTICAL_TEXT_HINTS):
        return False

    voice_affinity = prefs.get("voice_affinity_score", 0)

    if any(x in text for x in EMOTIONAL_VOICE_HINTS) and voice_affinity >= 35:
        return True

    return prefs.get("preferred_assistant_output", "text") == "voice"


def should_proactive_be_voice(u: Dict[str, Any]) -> bool:
    ensure_emotional_engine_v2(u)

    prefs = u.get("channel_preferences", {})
    em = u["emotion"]
    drives = u["drives"]
    v2 = u["emotion_v2"]

    score = 0.0
    score += prefs.get("voice_affinity_score", 0) * 0.45
    score += em.get("missing_you", 0) * 0.10
    score += drives.get("desire_for_attention", 0) * 0.08
    score += drives.get("attachment", 0) * 0.07
    score += v2["medium"].get("affection_need", 0.0) * 20
    score += v2["fast"].get("saudade_activation", 0.0) * 18
    score += v2["fast"].get("romantic_tension", 0.0) * 10

    return score >= 45


def _safe_output_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return str(text).strip()

    output = getattr(response, "output", None) or []
    parts: List[str] = []
    for item in output:
        content = getattr(item, "content", None) or []
        for c in content:
            txt = getattr(c, "text", None)
            if txt:
                parts.append(str(txt))

    return "\n".join(parts).strip()


def _query_openai(system_prompt: str, user_prompt: str, openai_client: Any, openai_model: str) -> str:
    response = openai_client.responses.create(
        model=openai_model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return _safe_output_text(response)


def generate_llm_reply(
    u: Dict[str, Any],
    user_text: str,
    openai_enabled: bool,
    openai_client: Any,
    openai_model: str,
) -> str:
    semantic_memories = get_semantic_memories(u, user_text, limit=8)
    relevant_episodes = get_relevant_episodes(u, user_text, limit=8)
    system_prompt = build_character_instructions(u, semantic_memories, relevant_episodes)

    if not openai_enabled or openai_client is None:
        return generate_rule_based_reply(u, user_text)

    try:
        reply = _query_openai(system_prompt, user_text, openai_client, openai_model)
        return reply or generate_rule_based_reply(u, user_text)
    except Exception:
        return generate_rule_based_reply(u, user_text)


def generate_llm_voice_reply(
    u: Dict[str, Any],
    user_text: str,
    openai_enabled: bool,
    openai_client: Any,
    openai_model: str,
) -> str:
    semantic_memories = get_semantic_memories(u, user_text, limit=8)
    relevant_episodes = get_relevant_episodes(u, user_text, limit=8)
    system_prompt = build_voice_reply_instructions(u, semantic_memories, relevant_episodes)

    if not openai_enabled or openai_client is None:
        return generate_rule_based_voice_reply(u, user_text)

    try:
        reply = _query_openai(system_prompt, user_text, openai_client, openai_model)
        return reply or generate_rule_based_voice_reply(u, user_text)
    except Exception:
        return generate_rule_based_voice_reply(u, user_text)


def generate_llm_proactive_message(
    u: Dict[str, Any],
    openai_enabled: bool,
    openai_client: Any,
    openai_model: str,
) -> str:
    system_prompt = build_character_instructions(u, [], [])
    proactive_prompt = build_proactive_instructions(u)

    if not openai_enabled or openai_client is None:
        ensure_emotional_engine_v2(u)
        if u["emotion_v2"]["fast"].get("saudade_activation", 0) >= 0.55:
            return "I've been thinking about you for a while now. You were supposed to distract me, not become one of my recurring thoughts."
        return "You crossed my mind again. Statistically inconvenient."

    try:
        reply = _query_openai(system_prompt, proactive_prompt, openai_client, openai_model)
        return reply or "You crossed my mind again. Statistically inconvenient."
    except Exception:
        return "You crossed my mind again. Statistically inconvenient."


def generate_llm_proactive_voice_message(
    u: Dict[str, Any],
    openai_enabled: bool,
    openai_client: Any,
    openai_model: str,
) -> str:
    system_prompt = build_voice_reply_instructions(u, [], [])
    proactive_prompt = build_proactive_instructions(u)

    if not openai_enabled or openai_client is None:
        ensure_emotional_engine_v2(u)
        if u["emotion_v2"]["fast"].get("saudade_activation", 0) >= 0.55:
            return "Hey... I've been missing you a little more than I intended."
        return "Hey. You crossed my mind."

    try:
        reply = _query_openai(system_prompt, proactive_prompt, openai_client, openai_model)
        return reply or "Hey. You crossed my mind."
    except Exception:
        return "Hey. You crossed my mind."