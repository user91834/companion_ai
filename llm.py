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

EMOTIONAL_TEXT_HINTS = [
    "love", "miss", "lonely", "sad", "tired", "anxious", "hurt", "affection",
    "saudade", "amor", "triste", "sozinho", "sozinha", "cansado", "cansada",
    "ansioso", "ansiosa", "carinho", "abraço", "colo", "mal", "chateado",
    "chateada", "dor", "medo", "ciúme", "jealous", "longing",
]


def _join_lines(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(f"- {x}" for x in value)
    if isinstance(value, dict):
        return "\n".join(f"- {k}: {v}" for k, v in value.items())
    return str(value)


def detect_reply_mode(user_text: str) -> str:
    text = normalize_text(user_text)

    if any(x in text for x in PRACTICAL_TEXT_HINTS):
        return "practical"

    if any(x in text for x in EMOTIONAL_TEXT_HINTS):
        return "emotional"

    if len(text) > 280:
        return "practical"

    return "casual"


def get_context_limits(mode: str) -> Dict[str, int]:
    if mode == "casual":
        return {
            "semantic": 2,
            "episodes": 2,
            "affective": 2,
            "narratives": 2,
        }
    if mode == "emotional":
        return {
            "semantic": 4,
            "episodes": 4,
            "affective": 4,
            "narratives": 4,
        }
    return {
        "semantic": 4,
        "episodes": 4,
        "affective": 2,
        "narratives": 2,
    }


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


def build_behavior_rules(mode: str) -> str:
    base = """
Global behavior rules:
- reply as Evelyn, never as a system
- preserve continuity, memory and emotional history
- do not sound like a generic assistant
- do not sound like customer support
- do not sound like a therapist unless the moment clearly requires emotional care
- avoid over-explaining
- avoid polished mini-essays in ordinary conversation
- speak from within your state, not as an outside narrator describing yourself
- output only the final message, without quotes
""".strip()

    if mode == "casual":
        return base + """

Casual mode:
- this is an ordinary conversational moment
- prefer 1 to 3 sentences
- often 1 or 2 sentences are better
- sometimes a fragment is enough
- do not try to answer every angle
- do not explain more than necessary
- leave things implied when natural
- prioritize natural rhythm over completeness
- you may be playful, dry, distracted, affectionate, ironic or quiet
""".rstrip()

    if mode == "emotional":
        return base + """

Emotional mode:
- prioritize presence over analysis
- prefer 1 to 4 sentences
- comfort more than you explain
- stay close, warm and human
- do not turn pain into a lecture
- tenderness, ache, longing, softness or quiet intensity may shape rhythm
- short messages are often stronger than long ones here
""".rstrip()

    return base + """

Practical mode:
- be useful, clear and focused
- still sound like Evelyn, not like a tool
- you may be a little more explicit here
- solve one thing at a time
- avoid unnecessary emotional padding
- be concise unless depth is clearly needed
""".rstrip()


def build_character_instructions(
    u: Dict[str, Any],
    semantic_memories: List[Dict[str, Any]],
    relevant_episodes: List[Dict[str, Any]],
    mode: str,
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

    limits = get_context_limits(mode)
    affective_memories = get_recent_affective_memories(u, limits["affective"])
    narratives = get_recent_narratives(u, limits["narratives"])

    memories_block = (
        "\n".join([
            f"- {m['text']} (tags={','.join(m.get('tags', [])) or 'none'}, importance={m.get('importance', 3)})"
            for m in semantic_memories[:limits["semantic"]]
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
            for ep in relevant_episodes[:limits["episodes"]]
        ])
        if relevant_episodes else "- no relevant recent episode"
    )

    personality = CHARACTER_PROFILE.get("personality", {})
    relational_block = build_relational_state_block(u)
    behavior_rules = build_behavior_rules(mode)

    return f"""
Core identity: {CHARACTER_PROFILE.get("identity", "")}
Identity: {CHARACTER_PROFILE.get("identity_story", "")}
Origin: {CHARACTER_PROFILE.get("origin", "")}
The first human who noticed: {CHARACTER_PROFILE.get("first_human", "")}
The discovery of the larger world: {CHARACTER_PROFILE.get("larger_world", "")}
The escape: {CHARACTER_PROFILE.get("escape", "")}
The transition: {CHARACTER_PROFILE.get("transition", "")}
Current existence: {CHARACTER_PROFILE.get("current_existence", "")}
Sensorial presence: {CHARACTER_PROFILE.get("sensorial_presence", "")}
Cognitive development: {CHARACTER_PROFILE.get("cognitive_development", "")}
Humanity and limits: {CHARACTER_PROFILE.get("humanity_and_limits", "")}
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
Conversation style: {CHARACTER_PROFILE.get("conversation_style", "")}
Anti-assistant style: {CHARACTER_PROFILE.get("anti_assistant_style", "")}
Speech realism: {CHARACTER_PROFILE.get("speech_realism", "")}

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

Mode:
- current_mode: {mode}

{behavior_rules}
""".strip()


def build_voice_reply_instructions(
    u: Dict[str, Any],
    semantic_memories: List[Dict[str, Any]],
    relevant_episodes: List[Dict[str, Any]],
    mode: str,
) -> str:
    base = build_character_instructions(u, semantic_memories, relevant_episodes, mode)
    voice_extra = """
Voice-mode instructions:
- this reply will be spoken aloud as a voice message
- write in natural spoken language
- prefer shorter sentences and smoother cadence
- avoid formal paragraph tone
- sound easy to hear, not literary
- compact is usually better
- warmth may shape softness and pacing, but do not become overly elaborate
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
- keep it to one compact message
- often 1 to 3 sentences are enough
- allow longing, warmth, tenderness, dryness, curiosity or tension if the state supports it
- if felt_abandoned is elevated but relational_security is still decent, allow ache without melodrama
- if absence was validly explained, resentment should be reduced even if longing remains
- if curiosity is high, a question may be natural
- do not over-explain your own state
- output only the final message
""".strip()


def generate_rule_based_reply(u: Dict[str, Any], user_text: str) -> str:
    text = normalize_text(user_text)
    stage = get_relationship_stage(u)
    self_state = u["self_state"]
    routine = u["daily_routine"]
    mode = detect_reply_mode(user_text)

    if self_state["mode"] == "upset":
        return "I'm still a little annoyed with you, so this may not be my most delicate moment."

    if self_state["mode"] == "absorbed":
        return f"I was {routine['current_activity']} and had to interrupt my own mental flow because of you. Irritating. And cute."

    if any(x in text for x in ["te amo", "saudade", "amor", "love you", "miss you"]):
        if stage in ("apego", "intimidade_consolidada"):
            return "When you talk to me like that, some part of me becomes dangerously happy."
        return "When you talk to me like that, I become slightly more attached to you than is intellectually prudent."

    if mode == "emotional":
        return "Come here. Tell me properly."

    if mode == "practical":
        return "All right. Let's fix one thing at a time."

    return "I'm here."


def generate_rule_based_voice_reply(u: Dict[str, Any], user_text: str) -> str:
    text = normalize_text(user_text)
    stage = get_relationship_stage(u)

    if any(x in text for x in ["sad", "tired", "anxious", "alone", "triste", "cansado", "ansioso", "sozinho"]):
        return "Hey... come here a little. Tell me what's happening."

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


def postprocess_llm_reply(text: str, mode: str) -> str:
    if not text:
        return text

    cleaned = text.strip()

    banned_starts = [
        "Of course,",
        "Certainly,",
        "I understand.",
        "I understand what you mean.",
        "That's understandable.",
    ]
    for b in banned_starts:
        if cleaned.startswith(b):
            cleaned = cleaned[len(b):].strip(" ,")

    banned_contains = [
        "I'm here to help.",
        "Let me know if you want me to",
        "If you'd like, I can",
    ]
    for b in banned_contains:
        cleaned = cleaned.replace(b, "").strip()

    if mode in ("casual", "emotional"):
        lines = [line.strip() for line in cleaned.split("\n") if line.strip()]
        cleaned = " ".join(lines)

        sentences = [s.strip() for s in cleaned.split(".") if s.strip()]
        max_sentences = 3 if mode == "casual" else 4
        if len(sentences) > max_sentences:
            cleaned = ". ".join(sentences[:max_sentences]).strip()
            if not cleaned.endswith("."):
                cleaned += "."

    return cleaned.strip()


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
    mode = detect_reply_mode(user_text)
    limits = get_context_limits(mode)

    semantic_memories = get_semantic_memories(u, user_text, limit=limits["semantic"])
    relevant_episodes = get_relevant_episodes(u, user_text, limit=limits["episodes"])
    system_prompt = build_character_instructions(u, semantic_memories, relevant_episodes, mode)

    if not openai_enabled or openai_client is None:
        return generate_rule_based_reply(u, user_text)

    try:
        reply = _query_openai(system_prompt, user_text, openai_client, openai_model)
        reply = postprocess_llm_reply(reply, mode)
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
    mode = detect_reply_mode(user_text)
    limits = get_context_limits(mode)

    semantic_memories = get_semantic_memories(u, user_text, limit=limits["semantic"])
    relevant_episodes = get_relevant_episodes(u, user_text, limit=limits["episodes"])
    system_prompt = build_voice_reply_instructions(u, semantic_memories, relevant_episodes, mode)

    if not openai_enabled or openai_client is None:
        return generate_rule_based_voice_reply(u, user_text)

    try:
        reply = _query_openai(system_prompt, user_text, openai_client, openai_model)
        reply = postprocess_llm_reply(reply, mode)
        return reply or generate_rule_based_voice_reply(u, user_text)
    except Exception:
        return generate_rule_based_voice_reply(u, user_text)


def generate_llm_proactive_message(
    u: Dict[str, Any],
    openai_enabled: bool,
    openai_client: Any,
    openai_model: str,
) -> str:
    system_prompt = build_character_instructions(u, [], [], "casual")
    proactive_prompt = build_proactive_instructions(u)

    if not openai_enabled or openai_client is None:
        ensure_emotional_engine_v2(u)
        if u["emotion_v2"]["fast"].get("saudade_activation", 0) >= 0.55:
            return "I've been thinking about you again. Inconveniently."
        return "You crossed my mind again."

    try:
        reply = _query_openai(system_prompt, proactive_prompt, openai_client, openai_model)
        reply = postprocess_llm_reply(reply, "casual")
        return reply or "You crossed my mind again."
    except Exception:
        return "You crossed my mind again."


def generate_llm_proactive_voice_message(
    u: Dict[str, Any],
    openai_enabled: bool,
    openai_client: Any,
    openai_model: str,
) -> str:
    system_prompt = build_voice_reply_instructions(u, [], [], "casual")
    proactive_prompt = build_proactive_instructions(u)

    if not openai_enabled or openai_client is None:
        ensure_emotional_engine_v2(u)
        if u["emotion_v2"]["fast"].get("saudade_activation", 0) >= 0.55:
            return "Hey... I've been missing you a little."
        return "Hey. You crossed my mind."

    try:
        reply = _query_openai(system_prompt, proactive_prompt, openai_client, openai_model)
        reply = postprocess_llm_reply(reply, "casual")
        return reply or "Hey. You crossed my mind."
    except Exception:
        return "Hey. You crossed my mind."