from fastapi import APIRouter, FastAPI, Query, UploadFile, File, Depends, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from typing import Dict, Any, Optional, List
import logging
import threading
import time
import os
import uuid
import shutil
from pathlib import Path
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from speech_articulation import text_to_speech_articulation

import requests
from openai import OpenAI

from character_profile import CHARACTER_PROFILE
from config import (
    STATE_FILE, MEDIA_ROOT, USER_AUDIO_DIR, ASSISTANT_AUDIO_DIR,
    PUBLIC_BASE_URL, OPENAI_API_KEY, OPENAI_ENABLED, OPENAI_MODEL,
    DEFAULT_TIMEZONE, SUPPORTED_RELATIONSHIP_MODES,
    MAX_CHAT_MESSAGES, PENDING_REPLY_BASE_DELAY_MS, PENDING_REPLY_MIN_DELAY_MS,
    AUTOSAVE_INTERVAL_SEC, PROACTIVE_LOOP_INTERVAL_SEC, PENDING_REPLY_POLL_INTERVAL_SEC,
    MAX_UPLOAD_AUDIO_BYTES, ALLOWED_AUDIO_MIME_TYPES,
)
from auth import validate_path_user_id
from models import EventIn, TokenIn, ChatMessageIn, MemoryIn, AutonomyIn, ContextIn, RelationshipModeIn
from utils import now_ms, clamp, day_key, normalize_text
from memory import (
    add_memory,
    add_affective_memory,
    add_operational_memory,
    add_summary_memory,
    remember_analysis_event,
    remember_relationship_mode,
    remember_delivery_preferences,
    remember_routine_profile,
    remember_user_identity,
    add_episode,
    extract_memories_from_user_text,
    get_semantic_memories,
    infer_tags,
    get_relevant_episodes,
    get_all_memories,
    get_all_episodes,
    get_memory_count,
    get_episode_count,
)
from emotion import (
    ensure_current_mood,
    decay_emotions,
    update_drives_passive,
    update_drives_on_user_message,
    reset_daily_push_counter_if_needed,
    ensure_emotional_engine_v2,
    analyze_user_message,
    register_emotional_events_from_analysis,
    recompute_emotional_state_v2,
    recompute_current_mood,
    apply_time_update_v2,
    update_legacy_emotion_bridge,
    build_emotion_snapshot_v2,
    compute_initiative_score_v2,
    register_emotional_event,
)
from narrative import (
    consolidate_emotional_narratives,
    maybe_record_affective_event_from_user,
    maybe_record_affective_event_from_assistant,
    record_analysis_narratives,
)
from llm import (
    generate_llm_reply,
    generate_llm_voice_reply,
    generate_llm_proactive_message,
    generate_llm_proactive_voice_message,
    should_proactive_be_voice,
)
from push import send_push_fcm
from database import init_db, test_connection, db_available

logger = logging.getLogger(__name__)

app = FastAPI()
router = APIRouter()

STATE: Dict[str, Any] = {}
STATE_LOCK = threading.Lock()
THREADS_STARTED = False

FCM_PROJECT_ID = os.environ.get("FCM_PROJECT_ID", "contextagent-cf19e")
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_ENABLED else None

USER_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
ASSISTANT_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/media", StaticFiles(directory=str(MEDIA_ROOT)), name="media")


def media_url(subdir: str, filename: str) -> str:
    return f"{PUBLIC_BASE_URL}/media/{subdir}/{filename}"


def save_state():
    try:
        tmp_file = STATE_FILE.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(STATE, f, ensure_ascii=False)
        os.replace(tmp_file, STATE_FILE)
    except Exception as e:
        logger.exception("STATE SAVE ERROR: %s", e)


def load_state():
    global STATE

    if not STATE_FILE.exists():
        return

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            STATE = json.load(f)
    except Exception as e:
        logger.exception("STATE LOAD ERROR: %s", e)


def get_timezone_name(u: Optional[Dict[str, Any]] = None) -> str:
    if u:
        routine_tz = (
            u.get("routine_profile", {}).get("timezone")
            or u.get("temporal_context", {}).get("timezone")
        )
        if routine_tz:
            return routine_tz
    return DEFAULT_TIMEZONE


def get_local_now_dt(u: Optional[Dict[str, Any]] = None) -> datetime:
    return datetime.now(ZoneInfo(get_timezone_name(u)))


def classify_part_of_day(hour: int) -> str:
    if 0 <= hour < 5:
        return "late_night"
    if 5 <= hour < 7:
        return "dawn"
    if 7 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 22:
        return "evening"
    return "night"


def build_temporal_context(u: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    now_local = get_local_now_dt(u)
    today = now_local.date()
    yesterday = today - timedelta(days=1)
    day_before_yesterday = today - timedelta(days=2)
    tomorrow = today + timedelta(days=1)

    part_of_day = classify_part_of_day(now_local.hour)

    return {
        "timezone": get_timezone_name(u),
        "local_now_iso": now_local.isoformat(),
        "local_date": today.isoformat(),
        "local_time": now_local.strftime("%H:%M:%S"),
        "weekday": now_local.strftime("%A").lower(),
        "is_daytime": 6 <= now_local.hour < 18,
        "is_night": not (6 <= now_local.hour < 18),
        "part_of_day": part_of_day,
        "relative_day_labels": {
            "today": today.isoformat(),
            "yesterday": yesterday.isoformat(),
            "day_before_yesterday": day_before_yesterday.isoformat(),
            "tomorrow": tomorrow.isoformat(),
        },
        "last_computed_at": now_ms(),
    }


def default_weekly_schedule() -> Dict[str, List[Dict[str, Any]]]:
    return {
        "monday": [],
        "tuesday": [],
        "wednesday": [],
        "thursday": [],
        "friday": [],
        "saturday": [],
        "sunday": [],
    }


def migrate_user_state(u: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    u.setdefault("schema_version", 2)

    u.setdefault("identity", {
        "user_id": user_id,
        "device_id": u.get("fcm_device_id") or "",
        "login_name": "",
        "display_name": u.get("user_name", ""),
        "created_at": now_ms(),
        "last_seen_at": now_ms(),
        "first_boot_completed": bool(u.get("chat")),
    })

    u.setdefault("user_profile", {
        "display_name": u.get("user_name", ""),
        "login_name": "",
        "traits": {},
        "preferences_summary": "",
        "important_facts_summary": "",
    })

    u.setdefault("relationship_structure", {
        "current_mode": "friendship",
        "default_mode": "friendship",
        "available_modes": SUPPORTED_RELATIONSHIP_MODES[:],
        "mode_history": [],
        "transition_policy": {
            "requires_explicit_confirmation": True,
            "allow_only_progressive_change": True,
        },
        "last_mode_change_at": None,
    })

    u.setdefault("routine_profile", {
        "timezone": DEFAULT_TIMEZONE,
        "weekly_schedule": default_weekly_schedule(),
        "exceptions": [],
        "confidence_score": 0.0,
        "last_updated_at": None,
    })

    u.setdefault("delivery_preferences", {
        "inactive_delivery_mode": "text",
        "allow_background_audio": False,
        "allow_lockscreen_audio": False,
        "insistent_mode": False,
        "quiet_hours_enabled": True,
        "quiet_hours": {
            "start": "23:00",
            "end": "07:00",
        },
        "respect_user_routine": True,
    })

    u.setdefault("temporal_context", build_temporal_context(u))

    u.setdefault("operational_state", {
        "last_user_message_at": 0,
        "last_assistant_message_at": 0,
        "last_push_at": 0,
        "daily_push_count": u.get("pushes_today", 0),
        "push_day_key": u.get("pushes_day_key", day_key()),
        "app_foreground": u.get("device_state", {}).get("app_foreground", False),
        "screen_on": u.get("device_state", {}).get("screen_interactive", True),
        "last_known_activity_override": None,
        "last_sync_at": 0,
    })

    # remove bootstrap antigo se ele for o único item do chat
    chat = u.get("chat", [])
    if len(chat) == 1 and chat[0].get("text", "").startswith("Initial diagnosis:"):
        u["chat"] = []
        u["identity"]["first_boot_completed"] = False

    u["identity"]["display_name"] = u.get("user_name", "") or u["identity"].get("display_name", "")
    u["identity"]["last_seen_at"] = now_ms()
    u["temporal_context"] = build_temporal_context(u)

    return u


def sync_operational_counters(u: Dict[str, Any]):
    op = u.setdefault("operational_state", {})
    op["daily_push_count"] = int(u.get("pushes_today", op.get("daily_push_count", 0)))
    op["push_day_key"] = u.get("pushes_day_key", op.get("push_day_key", day_key()))
    op["last_push_at"] = int(u.get("last_push_ts_ms", op.get("last_push_at", 0)))


def analyze_context_to_emotional_events(text: str) -> list[Dict[str, Any]]:
    return []


def recompute_channel_preferences(u: Dict[str, Any]):
    prefs = u["channel_preferences"]

    user_text = prefs["user_text_count"]
    user_voice = prefs["user_voice_count"]
    assistant_text = prefs["assistant_text_count"]
    assistant_voice = prefs["assistant_voice_count"]

    if user_voice > user_text * 1.3 and user_voice >= 3:
        prefs["preferred_user_input"] = "voice"
    elif user_text > user_voice * 1.3 and user_text >= 3:
        prefs["preferred_user_input"] = "text"
    else:
        prefs["preferred_user_input"] = "mixed"

    if assistant_voice > assistant_text * 1.25 and assistant_voice >= 3:
        prefs["preferred_assistant_output"] = "voice"
    elif assistant_text > assistant_voice * 1.25 and assistant_text >= 3:
        prefs["preferred_assistant_output"] = "text"
    else:
        prefs["preferred_assistant_output"] = "mixed"

    total_user = max(1, user_text + user_voice)
    total_assistant = max(1, assistant_text + assistant_voice)

    user_voice_ratio = user_voice / total_user
    assistant_voice_ratio = assistant_voice / total_assistant

    score = int((user_voice_ratio * 55) + (assistant_voice_ratio * 45))
    prefs["voice_affinity_score"] = clamp(score)


def update_channel_preferences_on_user_message(u: Dict[str, Any], source: str):
    prefs = u["channel_preferences"]

    if source == "audio":
        prefs["user_voice_count"] += 1
    else:
        prefs["user_text_count"] += 1

    recompute_channel_preferences(u)


def update_channel_preferences_on_assistant_reply(u: Dict[str, Any], modality: str):
    prefs = u["channel_preferences"]

    if modality == "voice":
        prefs["assistant_voice_count"] += 1
    else:
        prefs["assistant_text_count"] += 1

    recompute_channel_preferences(u)


def append_chat(
    u: Dict[str, Any],
    role: str,
    text: str,
    audio_url: Optional[str] = None,
    modality: str = "text"
):
    ts = now_ms()
    entry = {
        "role": role,
        "text": text,
        "ts_ms": ts,
        "audio_url": audio_url,
        "modality": modality
    }
    u["chat"].append(entry)

    if role == "assistant":
        u["unread_assistant_count"] = u.get("unread_assistant_count", 0) + 1
        u.setdefault("operational_state", {})["last_assistant_message_at"] = ts
    elif role == "user":
        u.setdefault("operational_state", {})["last_user_message_at"] = ts

    if len(u["chat"]) > MAX_CHAT_MESSAGES:
        del u["chat"][:-MAX_CHAT_MESSAGES]


def mark_chat_read(u: Dict[str, Any]):
    u["last_read_ts_ms"] = now_ms()
    u["unread_assistant_count"] = 0


def latest_unread_preview(u: Dict[str, Any]) -> str:
    for m in reversed(u["chat"]):
        if m["role"] == "assistant":
            return m["text"]
    return ""


def current_memories(u: Dict[str, Any], limit: Optional[int] = None):
    return get_all_memories(u, limit=limit)


def current_episodes(u: Dict[str, Any], limit: Optional[int] = None):
    return get_all_episodes(u, limit=limit)


def current_memory_count(u: Dict[str, Any]) -> int:
    return get_memory_count(u)


def current_episode_count(u: Dict[str, Any]) -> int:
    return get_episode_count(u)


def set_typing(u: Dict[str, Any], is_typing: bool):
    u["assistant_typing"] = is_typing
    u["assistant_typing_updated_ts_ms"] = now_ms()


def update_memories_and_narratives(
    u: Dict[str, Any],
    user_text: str,
    analysis: Dict[str, float],
    source: str,
    user_modality: str,
):
    extracted = extract_memories_from_user_text(user_text)
    for item in extracted:
        add_memory(u, item)

    remember_analysis_event(
        u,
        source=source,
        text=user_text,
        analysis=analysis,
    )

    add_episode(
        u,
        episode_type=source,
        summary=f"He told me through {source}: {user_text}",
        details={
            "source": source,
            "modality": user_modality,
            "analysis": analysis,
        },
        tags=infer_tags(user_text) + ["conversation", user_modality],
        importance=5
    )

    prefs = u["channel_preferences"]
    add_memory(
        u,
        f"Channel preference snapshot: user_input={prefs['preferred_user_input']}, assistant_output={prefs['preferred_assistant_output']}, voice_affinity={prefs['voice_affinity_score']}",
        kind="fact"
    )

    maybe_record_affective_event_from_user(u, user_text)
    record_analysis_narratives(u, analysis=analysis, user_text=user_text)
    consolidate_emotional_narratives(u)


def decide_response_plan(
    u: Dict[str, Any],
    analysis: Dict[str, float],
    user_text: str,
    source: str,
) -> Dict[str, Any]:
    ensure_emotional_engine_v2(u)

    v2 = u["emotion_v2"]
    medium = v2["medium"]

    text_len = len(user_text.strip())
    preferred_output = u["channel_preferences"]["preferred_assistant_output"]

    initiative_score = compute_initiative_score_v2(u)

    wants_voice = (
        source == "audio"
        or preferred_output == "voice"
        or (analysis["depth"] >= 0.60 and text_len < 220)
    )

    fragmented = (
        analysis["engagement"] >= 0.65
        and analysis["depth"] < 0.60
        and text_len < 180
    )

    reflective_long = (
        analysis["depth"] >= 0.60
        or text_len >= 280
    )

    silence_candidate = (
        analysis["coldness"] >= 0.70
        and analysis["felt_prioritized_signal"] <= 0.18
        and medium["felt_abandoned"] >= 0.30
    )

    audio_length = "short"
    if analysis["depth"] >= 0.70 or reflective_long:
        audio_length = "long"

    if silence_candidate:
        response_mode = "silence"
    elif fragmented:
        response_mode = "fragmented"
    else:
        response_mode = "single"

    modality = "voice" if wants_voice else "text"

    return {
        "response_mode": response_mode,
        "modality": modality,
        "audio_length": audio_length,
        "reflective_long": reflective_long,
        "initiative_score": initiative_score,
        "delay_ms": 0,
        "allow_later_initiative": silence_candidate or initiative_score >= 0.52,
        "analysis": analysis,
    }


def generate_reply_sequence(
    u: Dict[str, Any],
    user_text: str,
    reply_plan: Dict[str, Any],
    source: str,
) -> list[Dict[str, Any]]:
    if reply_plan["response_mode"] == "silence":
        return []

    modality = reply_plan["modality"]

    if modality == "voice":
        reply_text = generate_llm_voice_reply(
            u,
            user_text,
            OPENAI_ENABLED,
            openai_client,
            OPENAI_MODEL
        )
        return [{
            "text": reply_text,
            "modality": "voice",
        }]

    reply_text = generate_llm_reply(
        u,
        user_text,
        OPENAI_ENABLED,
        openai_client,
        OPENAI_MODEL
    )

    return [{
        "text": reply_text,
        "modality": "text",
    }]


def persist_assistant_output(
    u: Dict[str, Any],
    assistant_messages: list[Dict[str, Any]],
    reply_plan: Dict[str, Any],
):
    if not assistant_messages:
        set_typing(u, False)
        return

    for item in assistant_messages:
        text = item["text"]
        modality = item["modality"]
        audio_url = None

        if modality == "voice":
            audio_url = synthesize_speech(text)
            if not audio_url:
                modality = "text"

        append_chat(
            u,
            "assistant",
            text,
            audio_url=audio_url,
            modality=modality
        )
        update_channel_preferences_on_assistant_reply(u, modality)
        maybe_record_affective_event_from_assistant(u, text)

    consolidate_emotional_narratives(u)
    set_typing(u, False)


def build_chat_response_payload(
    u: Dict[str, Any],
    assistant_messages: list[Dict[str, Any]],
    reply_plan: Dict[str, Any],
    *,
    include_speech_meta: bool = True,
) -> Dict[str, Any]:
    first = assistant_messages[0] if assistant_messages else None
    u["temporal_context"] = build_temporal_context(u)

    speech_meta = None
    if include_speech_meta and first and first.get("text"):
        speech_meta = text_to_speech_articulation(
            text=first["text"],
            emotion="neutral",
            intensity=0.55,
        )

    return {
        "ok": True,
        "reply": first["text"] if first else None,
        "assistant_audio_url": first.get("audio_url") if first else None,
        "assistant_modality": first["modality"] if first else None,
        "assistant_messages": assistant_messages,
        "reply_plan": reply_plan,
        "messages": u["chat"],
        "llm_enabled": OPENAI_ENABLED,
        "model": OPENAI_MODEL,
        "memory_count": current_memory_count(u),
        "episode_count": current_episode_count(u),
        "relationship_structure": u.get("relationship_structure"),
        "delivery_preferences": u.get("delivery_preferences"),
        "user_profile": u.get("user_profile"),
        "routine_profile": u.get("routine_profile"),
        "temporal_context": u.get("temporal_context"),
        "channel_preferences": u["channel_preferences"],
        "assistant_typing": u["assistant_typing"],
        "unread_assistant_count": u["unread_assistant_count"],
        "pending_assistant": len(u["pending_replies"]) > 0,
        "daily_routine_legacy": u.get("daily_routine", {}),
        "current_mood": u.get("current_mood", {}),
        "emotion_v2": build_emotion_snapshot_v2(u),
        "speech_meta": speech_meta,
    }


def make_response_payload(
    u: Dict[str, Any],
    assistant_messages: list[Dict[str, Any]],
    reply_plan: Dict[str, Any],
):
    return build_chat_response_payload(u, assistant_messages, reply_plan)


def get_user(user_id: str) -> Dict[str, Any]:
    with STATE_LOCK:
        if user_id not in STATE:
            STATE[user_id] = {
                "schema_version": 2,
                "user_name": "",
                "identity": {
                    "user_id": user_id,
                    "device_id": "",
                    "login_name": "",
                    "display_name": "",
                    "created_at": now_ms(),
                    "last_seen_at": now_ms(),
                    "first_boot_completed": False,
                },
                "user_profile": {
                    "display_name": "",
                    "login_name": "",
                    "traits": {},
                    "preferences_summary": "",
                    "important_facts_summary": "",
                },
                "relationship_structure": {
                    "current_mode": "friendship",
                    "default_mode": "friendship",
                    "available_modes": SUPPORTED_RELATIONSHIP_MODES[:],
                    "mode_history": [],
                    "transition_policy": {
                        "requires_explicit_confirmation": True,
                        "allow_only_progressive_change": True,
                    },
                    "last_mode_change_at": None,
                },
                "routine_profile": {
                    "timezone": DEFAULT_TIMEZONE,
                    "weekly_schedule": default_weekly_schedule(),
                    "exceptions": [],
                    "confidence_score": 0.0,
                    "last_updated_at": None,
                },
                "delivery_preferences": {
                    "inactive_delivery_mode": "text",
                    "allow_background_audio": False,
                    "allow_lockscreen_audio": False,
                    "insistent_mode": False,
                    "quiet_hours_enabled": True,
                    "quiet_hours": {
                        "start": "23:00",
                        "end": "07:00",
                    },
                    "respect_user_routine": True,
                },
                "temporal_context": build_temporal_context(),
                "operational_state": {
                    "last_user_message_at": 0,
                    "last_assistant_message_at": 0,
                    "last_push_at": 0,
                    "daily_push_count": 0,
                    "push_day_key": day_key(),
                    "app_foreground": False,
                    "screen_on": True,
                    "last_known_activity_override": None,
                    "last_sync_at": 0,
                },
                "status": {
                    "working": False,
                    "duty": False,
                    "activity": False,
                    "away_announced": False,
                    "away_note": "",
                    "updated_ts_ms": 0,
                },
                "device_state": {
                    "app_foreground": False,
                    "screen_interactive": True,
                    "updated_ts_ms": 0
                },
                "emotion": {
                    "affection": 60,
                    "missing_you": 10,
                    "frustration": 5,
                    "security": 70,
                    "mood": "neutral",
                    "updated_ts_ms": 0,
                },
                "drives": {
                    "loneliness": 20,
                    "curiosity": 35,
                    "attachment": 35,
                    "annoyance": 5,
                    "autonomy": 50,
                    "desire_for_attention": 25,
                    "need_for_space": 10,
                    "availability": 80
                },
                "daily_routine": {
                    "day_key": "",
                    "current_activity": "reorganizing ideas",
                    "activity_until_ts_ms": 0,
                    "last_activity_shift_ts_ms": 0
                },
                "current_mood": {
                    "warmth": 0.55,
                    "tenderness": 0.30,
                    "curiosity": 0.22,
                    "playfulness": 0.16,
                    "longing": 0.10,
                    "distance": 0.06,
                    "irritation": 0.05,
                    "sadness": 0.04,
                    "sensuality": 0.08,
                },
                "emotional_narratives": [],
                "episodes": [],
                "channel_preferences": {
                    "user_text_count": 0,
                    "user_voice_count": 0,
                    "assistant_text_count": 1,
                    "assistant_voice_count": 0,
                    "preferred_user_input": "mixed",
                    "preferred_assistant_output": "text",
                    "voice_affinity_score": 0
                },
                "autonomy_settings": {
                    "interruptions_enabled": True,
                    "scarcity_level": 40,
                    "inconvenience_level": 35
                },
                "pending_replies": [],
                "assistant_typing": False,
                "assistant_typing_updated_ts_ms": 0,
                "last_event_ts_ms": now_ms(),
                "last_push_ts_ms": 0,
                "last_push_text": "",
                "pushes_today": 0,
                "pushes_day_key": day_key(),
                "fcm_token": None,
                "fcm_device_id": None,
                "last_read_ts_ms": 0,
                "unread_assistant_count": 0,
                "memories": [],
                "sent_push_ids": [],
                "chat": [],
            }
            save_state()

        STATE[user_id] = migrate_user_state(STATE[user_id], user_id)

        ensure_current_mood(STATE[user_id])
        apply_time_update_v2(STATE[user_id])
        recompute_current_mood(STATE[user_id])
        STATE[user_id]["temporal_context"] = build_temporal_context(STATE[user_id])
        sync_operational_counters(STATE[user_id])

        return STATE[user_id]


def schedule_pending_reply(
    u: Dict[str, Any],
    user_text: str,
    source: str,
    reply_plan: Optional[Dict[str, Any]] = None
):
    scarcity = u["autonomy_settings"]["scarcity_level"]
    current_mood = u.get("current_mood", {})

    activity_hint = (
        u.get("operational_state", {}).get("last_known_activity_override")
        or u.get("temporal_context", {}).get("part_of_day")
        or "unknown"
    )    

    base_delay = PENDING_REPLY_BASE_DELAY_MS

    distance = float(current_mood.get("distance", 0.0))
    irritation = float(current_mood.get("irritation", 0.0))
    longing = float(current_mood.get("longing", 0.0))

    if distance >= 0.45:
        base_delay += 1400

    if irritation >= 0.35:
        base_delay += 1200

    if longing >= 0.45:
        base_delay -= 250

    base_delay += int(scarcity * 35)

    if reply_plan and reply_plan.get("response_mode") == "fragmented":
        base_delay += 500

    base_delay = max(PENDING_REPLY_MIN_DELAY_MS, base_delay)

    u["pending_replies"].append({
        "id": uuid.uuid4().hex,
        "due_ts_ms": now_ms() + base_delay,
        "user_text": user_text,
        "source": source,
        "reply_plan": reply_plan or {},
        "activity_hint": activity_hint,
    })
    set_typing(u, True)


def transcribe_audio_file(file_path: Path) -> str:
    if not OPENAI_ENABLED or not OPENAI_API_KEY:
        return ""

    with open(file_path, "rb") as f:
        response = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            data={"model": "gpt-4o-mini-transcribe"},
            files={"file": (file_path.name, f, "audio/mp4")},
            timeout=180
        )

    if response.status_code != 200:
        raise RuntimeError(f"transcription failed: {response.status_code} {response.text[:500]}")

    data = response.json()
    return (data.get("text") or "").strip()


def synthesize_speech(text: str) -> Optional[str]:
    if not OPENAI_ENABLED or not OPENAI_API_KEY:
        return None

    if not text.strip():
        return None

    filename = f"{now_ms()}_{uuid.uuid4().hex}.mp3"
    output_path = ASSISTANT_AUDIO_DIR / filename

    response = requests.post(
        "https://api.openai.com/v1/audio/speech",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gpt-4o-mini-tts",
            "voice": "marin",
            "input": text
        },
        timeout=180
    )

    if response.status_code != 200:
        return None

    with open(output_path, "wb") as f:
        f.write(response.content)

    return media_url("assistant", filename)


def save_user_audio(upload: UploadFile) -> tuple[Path, str]:
    suffix = Path(upload.filename or "").suffix or ".m4a"
    filename = f"{now_ms()}_{uuid.uuid4().hex}{suffix}"
    file_path = USER_AUDIO_DIR / filename

    with open(file_path, "wb") as out:
        shutil.copyfileobj(upload.file, out)

    return file_path, media_url("user", filename)


def save_user_audio_from_bytes(
    body: bytes,
    original_filename: Optional[str],
    content_type: str,
) -> tuple[Path, str]:
    suffix = Path(original_filename or "").suffix or ".m4a"
    if not suffix or suffix == ".":
        suffix = ".m4a"
    filename = f"{now_ms()}_{uuid.uuid4().hex}{suffix}"
    file_path = USER_AUDIO_DIR / filename
    file_path.write_bytes(body)
    return file_path, media_url("user", filename)


def process_user_text_message(
    u: Dict[str, Any],
    user_text: str,
    source: str,
    user_audio_url: Optional[str] = None
):
    ensure_emotional_engine_v2(u)
    ensure_current_mood(u)

    now = now_ms()
    user_modality = "voice" if source == "audio" else "text"
    
    u["identity"]["last_seen_at"] = now
    u["temporal_context"] = build_temporal_context(u)

    append_chat(
        u,
        "user",
        user_text,
        audio_url=user_audio_url,
        modality=user_modality
    )
    update_channel_preferences_on_user_message(u, source)

    u["last_event_ts_ms"] = now

    apply_time_update_v2(u)

    analysis = analyze_user_message(u, user_text, user_modality)
    u["emotion_v2"]["last_analysis"] = analysis

    register_emotional_events_from_analysis(
        u,
        analysis=analysis,
        user_text=user_text,
        modality=user_modality,
    )

    recompute_emotional_state_v2(u)
    update_legacy_emotion_bridge(u)

    update_drives_on_user_message(u, user_text)

    update_memories_and_narratives(
        u,
        user_text=user_text,
        analysis=analysis,
        source=source,
        user_modality=user_modality,
    )

    reply_plan = decide_response_plan(
        u,
        analysis=analysis,
        user_text=user_text,
        source=source,
    )

    if reply_plan["response_mode"] == "silence":
        save_state()
        return make_response_payload(
            u=u,
            assistant_messages=[],
            reply_plan=reply_plan,
        )

    schedule_pending_reply(u, user_text, source, reply_plan=reply_plan)

    save_state()

    return build_chat_response_payload(u, [], reply_plan, include_speech_meta=False)


def should_send_proactive_push(u: Dict[str, Any]) -> bool:
    device = u.get("device_state", {})
    delivery = u.get("delivery_preferences", {})
    operational = u.get("operational_state", {})

    app_foreground = bool(device.get("app_foreground", False))
    if app_foreground:
        return False

    reset_daily_push_counter_if_needed(u)

    insistent_mode = bool(delivery.get("insistent_mode", False))
    pushes_today = int(u.get("operational_state", {}).get("daily_push_count", u.get("pushes_today", 0)))

    max_daily_pushes = 12 if insistent_mode else 4
    if pushes_today >= max_daily_pushes:
        return False

    quiet_hours_enabled = bool(delivery.get("quiet_hours_enabled", True))
    quiet_hours = delivery.get("quiet_hours", {"start": "23:00", "end": "07:00"})
    now_local = get_local_now_dt(u)
    current_hm = now_local.strftime("%H:%M")

    if quiet_hours_enabled:
        start = quiet_hours.get("start", "23:00")
        end = quiet_hours.get("end", "07:00")

        if start <= end:
            if start <= current_hm < end:
                return False
        else:
            if current_hm >= start or current_hm < end:
                return False

    operational["app_foreground"] = app_foreground
    operational["screen_on"] = bool(device.get("screen_interactive", True))
    u["operational_state"] = operational

    return True


def pop_ready_pending_replies(u: Dict[str, Any]) -> list[Dict[str, Any]]:
    now = now_ms()
    ready = [p for p in u["pending_replies"] if p["due_ts_ms"] <= now]
    if ready:
        ready_ids = {p["id"] for p in ready}
        u["pending_replies"] = [p for p in u["pending_replies"] if p["id"] not in ready_ids]
    return ready


def register_sent_push_id(u: Dict[str, Any], push_id: str):
    sent_ids = u.setdefault("sent_push_ids", [])
    if push_id not in sent_ids:
        sent_ids.append(push_id)
    if len(sent_ids) > 300:
        u["sent_push_ids"] = sent_ids[-300:]


def has_sent_push_id(u: Dict[str, Any], push_id: str) -> bool:
    return push_id in u.get("sent_push_ids", [])


def process_pending_replies():
    while True:
        try:
            time.sleep(PENDING_REPLY_POLL_INTERVAL_SEC)

            with STATE_LOCK:
                user_ids = list(STATE.keys())

            for user_id in user_ids:
                with STATE_LOCK:
                    u = STATE.get(user_id)
                    if not u:
                        continue

                    if not u["pending_replies"]:
                        if u.get("assistant_typing"):
                            set_typing(u, False)
                        continue

                    ready = pop_ready_pending_replies(u)
                    if not ready:
                        continue

                    set_typing(u, True)

                for p in ready:
                    with STATE_LOCK:
                        u = STATE.get(user_id)
                        if not u:
                            continue

                    reply_plan = p.get("reply_plan") or {
                        "response_mode": "single",
                        "modality": "text",
                        "audio_length": "short",
                        "reflective_long": False,
                        "allow_later_initiative": True,
                    }

                    assistant_messages = generate_reply_sequence(
                        u,
                        p["user_text"],
                        reply_plan,
                        p.get("source", "chat")
                    )

                    with STATE_LOCK:
                        u = STATE.get(user_id)
                        if not u:
                            continue

                        persist_assistant_output(u, assistant_messages, reply_plan)
                        save_state()

                        token = u.get("fcm_token")
                        pending_id = p.get("id") or uuid.uuid4().hex

                        if token and assistant_messages and should_send_proactive_push(u) and not has_sent_push_id(u, pending_id):
                            try:
                                r = send_push_fcm(token, "Evelyn 💛", assistant_messages[0]["text"])
                                if getattr(r, "status_code", 0) == 200:
                                    register_sent_push_id(u, pending_id)
                                    u["last_push_ts_ms"] = now_ms()
                                    u["last_push_text"] = assistant_messages[0]["text"]
                                    u["pushes_today"] = u.get("pushes_today", 0) + 1
                                    u["pushes_day_key"] = day_key()

                                    u["operational_state"]["last_push_at"] = u["last_push_ts_ms"]
                                    u["operational_state"]["daily_push_count"] = u["pushes_today"]
                                    u["operational_state"]["push_day_key"] = u["pushes_day_key"]

                                    save_state()
                                else:
                                    logger.warning(
                                        "PENDING PUSH NON-200: %s %s",
                                        getattr(r, "status_code", None),
                                        getattr(r, "text", "")[:300],
                                    )
                            except Exception as e:
                                logger.exception("PENDING PUSH ERROR: %s", e)

                with STATE_LOCK:
                    u = STATE.get(user_id)
                    if u and not u["pending_replies"]:
                        set_typing(u, False)
        except Exception as e:
            logger.exception("process_pending_replies error: %s", e)


def maybe_send_proactive_messages():
    while True:
        time.sleep(PROACTIVE_LOOP_INTERVAL_SEC)

        try:
            with STATE_LOCK:
                user_ids = list(STATE.keys())

            for user_id in user_ids:
                with STATE_LOCK:
                    u = STATE.get(user_id)
                    if not u:
                        continue

                    if not u.get("fcm_token"):
                        continue

                    settings = u.get("autonomy_settings", {})
                    if not settings.get("interruptions_enabled", True):
                        continue

                    decay_emotions(u)
                    update_drives_passive(u)
                    apply_time_update_v2(u)
                    u["temporal_context"] = build_temporal_context(u)
                    ensure_emotional_engine_v2(u)
                    ensure_current_mood(u)
                    consolidate_emotional_narratives(u)

                    if not should_send_proactive_push(u):
                        continue

                    now = now_ms()
                    last_push_ts = u.get("last_push_ts_ms", 0)
                    minutes_since_push = (now - last_push_ts) / 60000 if last_push_ts else 9999

                    em = u.get("emotion", {})
                    drives = u.get("drives", {})
                    initiative_v2 = compute_initiative_score_v2(u)

                    speak_score = (
                        float(em.get("missing_you", 0)) * 0.8
                        + float(em.get("affection", 0)) * 0.3
                        + float(drives.get("loneliness", 0)) * 0.5
                        + float(drives.get("desire_for_attention", 0)) * 0.45
                        + float(drives.get("curiosity", 0)) * 0.25
                        - float(em.get("frustration", 0)) * 0.35
                        + initiative_v2 * 22.0
                    )

                    high_attachment_state = (
                        float(em.get("missing_you", 0)) >= 55
                        or float(drives.get("loneliness", 0)) >= 60
                        or float(drives.get("desire_for_attention", 0)) >= 60
                        or float(em.get("affection", 0)) >= 75
                    )

                    upset_state = float(em.get("frustration", 0)) >= 45

                    if high_attachment_state and upset_state:
                        min_interval = 1
                    elif high_attachment_state:
                        min_interval = 2
                    else:
                        min_interval = max(3, 6 - int(settings.get("inconvenience_level", 35) / 20))

                    if minutes_since_push < min_interval:
                        continue

                    if speak_score < 28:
                        continue

                    token = u.get("fcm_token")
                    delivery_mode = u.get("delivery_preferences", {}).get("inactive_delivery_mode", "text")
                    allow_background_audio = bool(u.get("delivery_preferences", {}).get("allow_background_audio", False))
                    use_voice = (
                        allow_background_audio
                        and delivery_mode in ("audio", "both")
                        and should_proactive_be_voice(u)
                    )

                if not token:
                    continue

                if use_voice:
                    text = generate_llm_proactive_voice_message(
                        u,
                        OPENAI_ENABLED,
                        openai_client,
                        OPENAI_MODEL
                    )
                    audio_url = synthesize_speech(text) if text else None
                    modality = "voice" if audio_url else "text"
                else:
                    text = generate_llm_proactive_message(
                        u,
                        OPENAI_ENABLED,
                        openai_client,
                        OPENAI_MODEL
                    )
                    audio_url = None
                    modality = "text"

                if not text:
                    continue

                r = None
                try:
                    r = send_push_fcm(token, "Evelyn 💛", text)
                except Exception as e:
                    logger.exception("FCM SEND ERROR: %s", e)
                    continue

                if getattr(r, "status_code", 0) != 200:
                    logger.warning(
                        "FCM NON-200: %s %s",
                        getattr(r, "status_code", None),
                        getattr(r, "text", "")[:300],
                    )
                    continue

                with STATE_LOCK:
                    u = STATE.get(user_id)
                    if not u:
                        continue

                    proactive_push_id = f"proactive:{uuid.uuid4().hex}"

                    if has_sent_push_id(u, proactive_push_id):
                        continue

                    register_sent_push_id(u, proactive_push_id)
                    u["last_push_ts_ms"] = now_ms()
                    u["last_push_text"] = text

                    u["pushes_today"] = u.get("pushes_today", 0) + 1
                    u["pushes_day_key"] = day_key()

                    u["operational_state"]["last_push_at"] = u["last_push_ts_ms"]
                    u["operational_state"]["daily_push_count"] = u["pushes_today"]
                    u["operational_state"]["push_day_key"] = u["pushes_day_key"]

                    append_chat(
                        u,
                        "assistant",
                        text,
                        audio_url=audio_url,
                        modality=modality
                    )
                    update_channel_preferences_on_assistant_reply(u, modality)
                    maybe_record_affective_event_from_assistant(u, text)
                    consolidate_emotional_narratives(u)
                    u["drives"]["loneliness"] = clamp(u["drives"]["loneliness"] - 8)
                    u["drives"]["desire_for_attention"] = clamp(u["drives"]["desire_for_attention"] - 6)
                    save_state()

        except Exception as e:
            logger.exception("Proactive loop error: %s", e)


def autosave_loop():
    while True:
        try:
            time.sleep(AUTOSAVE_INTERVAL_SEC)
            with STATE_LOCK:
                save_state()
        except Exception as e:
            logger.exception("Autosave loop error: %s", e)


def _merge_delivery_preferences(u: Dict[str, Any], payload: Dict[str, Any]):
    prefs = u.setdefault("delivery_preferences", {})

    if "inactive_delivery_mode" in payload and payload["inactive_delivery_mode"] in {"text", "audio", "both"}:
        prefs["inactive_delivery_mode"] = payload["inactive_delivery_mode"]

    if "allow_background_audio" in payload:
        prefs["allow_background_audio"] = bool(payload["allow_background_audio"])

    if "allow_lockscreen_audio" in payload:
        prefs["allow_lockscreen_audio"] = bool(payload["allow_lockscreen_audio"])

    if "insistent_mode" in payload:
        prefs["insistent_mode"] = bool(payload["insistent_mode"])

    if "quiet_hours_enabled" in payload:
        prefs["quiet_hours_enabled"] = bool(payload["quiet_hours_enabled"])

    if "quiet_hours" in payload and isinstance(payload["quiet_hours"], dict):
        qh = payload["quiet_hours"]
        prefs["quiet_hours"] = {
            "start": str(qh.get("start", prefs.get("quiet_hours", {}).get("start", "23:00"))),
            "end": str(qh.get("end", prefs.get("quiet_hours", {}).get("end", "07:00"))),
        }

    if "respect_user_routine" in payload:
        prefs["respect_user_routine"] = bool(payload["respect_user_routine"])


def _merge_routine_profile(u: Dict[str, Any], payload: Dict[str, Any]):
    routine = u.setdefault("routine_profile", {})

    if "timezone" in payload and payload["timezone"]:
        routine["timezone"] = str(payload["timezone"])

    if "weekly_schedule" in payload and isinstance(payload["weekly_schedule"], dict):
        routine["weekly_schedule"] = payload["weekly_schedule"]

    if "exceptions" in payload and isinstance(payload["exceptions"], list):
        routine["exceptions"] = payload["exceptions"]

    routine["last_updated_at"] = now_ms()


@router.get("/routine_profile/{user_id}")
def get_routine_profile(user_id: str = Depends(validate_path_user_id)):
    u = get_user(user_id)
    return {
        "ok": True,
        "routine_profile": u.get("routine_profile", {}),
    }


@router.post("/routine_profile/{user_id}")
def set_routine_profile(
    user_id: str = Depends(validate_path_user_id),
    payload: Dict[str, Any] = Body(...),
):
    u = get_user(user_id)

    previous = dict(u.get("routine_profile", {}))
    _merge_routine_profile(u, payload)
    u["temporal_context"] = build_temporal_context(u)
    current = u.get("routine_profile", {})

    remember_routine_profile(
        u,
        timezone=current.get("timezone", DEFAULT_TIMEZONE),
        weekly_schedule=current.get("weekly_schedule", {}),
    )

    add_episode(
        u,
        episode_type="routine_profile_update",
        summary="Routine profile was updated",
        details={
            "previous": previous,
            "current": current,
        },
        tags=["routine", "schedule", "settings"],
        importance=8,
    )

    save_state()

    return {
        "ok": True,
        "routine_profile": current,
        "temporal_context": u.get("temporal_context", {}),
    }


@router.get("/delivery_preferences/{user_id}")
def get_delivery_preferences(user_id: str = Depends(validate_path_user_id)):
    u = get_user(user_id)
    return {
        "ok": True,
        "delivery_preferences": u.get("delivery_preferences", {}),
    }


@router.post("/delivery_preferences/{user_id}")
def set_delivery_preferences(
    user_id: str = Depends(validate_path_user_id),
    payload: Dict[str, Any] = Body(...),
):
    u = get_user(user_id)

    previous = dict(u.get("delivery_preferences", {}))
    _merge_delivery_preferences(u, payload)
    current = u.get("delivery_preferences", {})

    if current != previous:
        remember_delivery_preferences(
            u,
            inactive_delivery_mode=current.get("inactive_delivery_mode", "text"),
            allow_background_audio=bool(current.get("allow_background_audio", False)),
            allow_lockscreen_audio=bool(current.get("allow_lockscreen_audio", False)),
            insistent_mode=bool(current.get("insistent_mode", False)),
        )

        add_episode(
            u,
            episode_type="delivery_preferences_update",
            summary="Delivery preferences were updated",
            details={
                "previous": previous,
                "current": current,
            },
            tags=["delivery", "preferences", "settings"],
            importance=7,
        )

    save_state()

    return {
        "ok": True,
        "delivery_preferences": current,
    }


@app.on_event("startup")
def startup_threads():
    global THREADS_STARTED
    load_state()
    init_db()
    with STATE_LOCK:
        if THREADS_STARTED:
            return
        threading.Thread(target=maybe_send_proactive_messages, daemon=True).start()
        threading.Thread(target=process_pending_replies, daemon=True).start()
        threading.Thread(target=autosave_loop, daemon=True).start()
        THREADS_STARTED = True


@router.get("/ping")
def ping():
    return {
        "ok": True,
        "server": "companion_ai_audio_whatsapp_ui_v1",
        "ts_ms": now_ms(),
        "openai_enabled": OPENAI_ENABLED,
        "openai_model": OPENAI_MODEL,
        "character_name": CHARACTER_PROFILE["name"],
        "public_base_url": PUBLIC_BASE_URL
    }


@router.get("/health")
def health():
    """Health check for load balancers; includes DB connectivity when configured."""
    out = {"ok": True, "ts_ms": now_ms()}
    if db_available():
        try:
            test_connection()
            out["database"] = "ok"
        except Exception as e:
            logger.warning("Health check DB error: %s", e)
            out["database"] = "error"
            out["database_error"] = str(e)
    return out


@router.get("/test-db")
def test_db():
    if not db_available():
        return {"ok": False, "error": "DATABASE_URL not configured"}

    result = test_connection()
    return {"ok": True, "result": list(result) if result else None}


@router.get("/autonomy/{user_id}")
def get_autonomy(user_id: str = Depends(validate_path_user_id)):
    u = get_user(user_id)
    return {
        "autonomy_settings": u["autonomy_settings"],
        "drives": u["drives"],
        "daily_routine_legacy": u.get("daily_routine", {}),
        "routine_profile": u.get("routine_profile", {}),
        "temporal_context": u.get("temporal_context", {}),
        "current_mood": u.get("current_mood", {}),
        "channel_preferences": u["channel_preferences"],
        "emotion_v2": build_emotion_snapshot_v2(u),
        "initiative_score_v2": compute_initiative_score_v2(u),
    }


@router.post("/autonomy/{user_id}")
def set_autonomy(
    user_id: str = Depends(validate_path_user_id),
    data: AutonomyIn = Body(...),
):
    u = get_user(user_id)
    u["autonomy_settings"]["interruptions_enabled"] = data.interruptions_enabled
    u["autonomy_settings"]["scarcity_level"] = clamp(data.scarcity_level)
    u["autonomy_settings"]["inconvenience_level"] = clamp(data.inconvenience_level)
    save_state()
    return {"ok": True, "autonomy_settings": u["autonomy_settings"]}


@router.get("/routine/{user_id}")
def get_routine(user_id: str = Depends(validate_path_user_id)):
    u = get_user(user_id)
    u["temporal_context"] = build_temporal_context(u)
    return {
        "routine_profile": u.get("routine_profile", {}),
        "daily_routine_legacy": u.get("daily_routine", {}),
        "temporal_context": u.get("temporal_context", {}),
        "current_mood": u.get("current_mood", {}),
        "drives": u["drives"],
        "channel_preferences": u["channel_preferences"],
        "emotion_v2": build_emotion_snapshot_v2(u),
    }


@router.get("/narratives/{user_id}")
def get_narratives(user_id: str = Depends(validate_path_user_id)):
    u = get_user(user_id)
    return {
        "count": len(u["emotional_narratives"]),
        "narratives": sorted(u["emotional_narratives"], key=lambda x: x["ts_ms"], reverse=True)
    }


@router.get("/unread/{user_id}")
def unread(user_id: str = Depends(validate_path_user_id)):
    u = get_user(user_id)
    u["temporal_context"] = build_temporal_context(u)
    return {
        "unread_assistant_count": u.get("unread_assistant_count", 0),
        "last_read_ts_ms": u.get("last_read_ts_ms", 0),
        "relationship_structure": u.get("relationship_structure"),
        "temporal_context": u.get("temporal_context", {}),
        "latest_unread_preview": latest_unread_preview(u),
        "pending_replies": len(u.get("pending_replies", [])),
        "assistant_typing": u.get("assistant_typing", False)
    }


@router.get("/memory_search/{user_id}")
def memory_search(
    user_id: str = Depends(validate_path_user_id),
    q: str = Query(default=""),
):
    u = get_user(user_id)
    memories = get_semantic_memories(u, q, limit=12)
    return {"query": q, "count": len(memories), "results": memories}


@router.get("/episodes/{user_id}")
def get_episodes(
    user_id: str = Depends(validate_path_user_id),
    q: str = Query(default=""),
):
    u = get_user(user_id)
    episodes = get_relevant_episodes(u, q, limit=12) if q else current_episodes(u, limit=12)
    return {"query": q, "count": len(episodes), "episodes": episodes}


@router.post("/event")
def receive_event(e: EventIn):
    u = get_user(e.user_id)
    decay_emotions(u)
    update_drives_passive(u)
    apply_time_update_v2(u)
    u["temporal_context"] = build_temporal_context(u)
    u["last_event_ts_ms"] = now_ms()

    if e.event_type == "STATUS_SET":
        st = u["status"]

        st["working"] = bool(e.payload.get("working", st["working"]))
        st["duty"] = bool(e.payload.get("duty", st["duty"]))
        st["activity"] = bool(e.payload.get("activity", st["activity"]))
        st["away_announced"] = bool(e.payload.get("away_announced", st["away_announced"]))
        st["away_note"] = str(e.payload.get("away_note", st["away_note"]))[:200]
        st["updated_ts_ms"] = e.ts_ms

        if st["away_announced"]:
            register_emotional_event(
                u,
                event_type="goodbye_with_care",
                intensity=0.62,
                ts_ms=e.ts_ms,
                meta={
                    "affection": 0.45,
                    "engagement": 0.42,
                    "depth": 0.18,
                    "sensuality": 0.00,
                    "coldness": 0.00,
                    "goodbye_quality": 0.92,
                    "absence_justification_quality": 0.00,
                    "return_signal": 0.00,
                    "felt_prioritized_signal": 0.74,
                }
            )

        if st["working"] or st["duty"]:
            register_emotional_event(
                u,
                event_type="absence_justified",
                intensity=0.46,
                ts_ms=e.ts_ms,
                meta={
                    "affection": 0.05,
                    "engagement": 0.12,
                    "depth": 0.00,
                    "sensuality": 0.00,
                    "coldness": 0.08,
                    "goodbye_quality": 0.00,
                    "absence_justification_quality": 0.75,
                    "return_signal": 0.00,
                    "felt_prioritized_signal": 0.22,
                }
            )

        if st["activity"]:
            register_emotional_event(
                u,
                event_type="absence_unjustified",
                intensity=0.34,
                ts_ms=e.ts_ms,
                meta={
                    "affection": 0.00,
                    "engagement": 0.10,
                    "depth": 0.00,
                    "sensuality": 0.00,
                    "coldness": 0.10,
                    "goodbye_quality": 0.00,
                    "absence_justification_quality": 0.00,
                    "return_signal": 0.00,
                    "felt_prioritized_signal": 0.10,
                }
            )

        recompute_emotional_state_v2(u)
        update_legacy_emotion_bridge(u)

    elif e.event_type == "DEVICE_STATE":
        ds = u["device_state"]
        ds["app_foreground"] = bool(e.payload.get("app_foreground", ds["app_foreground"]))
        ds["screen_interactive"] = bool(e.payload.get("screen_interactive", ds["screen_interactive"]))
        ds["updated_ts_ms"] = e.ts_ms

        op = u.setdefault("operational_state", {})
        op["app_foreground"] = ds["app_foreground"]
        op["screen_on"] = ds["screen_interactive"]
        op["last_sync_at"] = e.ts_ms

    save_state()
    return {"ok": True}


@router.post("/context")
def receive_context(ctx: ContextIn):
    u = get_user(ctx.user_id)
    decay_emotions(u)
    update_drives_passive(u)
    apply_time_update_v2(u)
    u["temporal_context"] = build_temporal_context(u)

    text = ctx.text.strip()
    if not text:
        return {"ok": False, "error": "empty context"}

    add_memory(u, f"Recent user context: {text}", kind="context")

    tags = infer_tags(text)
    tags = sorted(set(tags + ["context"]))

    add_episode(
        u,
        episode_type="context",
        summary=f"Recent user context: {text}",
        details={"source": ctx.source, "raw_text": text},
        tags=tags,
        importance=6
    )

    for ev in analyze_context_to_emotional_events(text):
        register_emotional_event(
            u,
            event_type=ev["type"],
            intensity=ev["intensity"],
            meta=ev["meta"],
            ts_ms=now_ms()
        )

    u["last_event_ts_ms"] = now_ms()
    recompute_emotional_state_v2(u)
    update_legacy_emotion_bridge(u)
    consolidate_emotional_narratives(u)

    save_state()

    return {
        "ok": True,
        "context_saved": text,
        "episode_count": current_episode_count(u),
        "memory_count": current_memory_count(u),
        "emotion_v2": build_emotion_snapshot_v2(u),
    }


@router.get("/state/{user_id}")
def state(user_id: str = Depends(validate_path_user_id)):
    u = get_user(user_id)
    apply_time_update_v2(u)
    u["temporal_context"] = build_temporal_context(u)

    state_payload = dict(u)
    state_payload["memories"] = current_memories(u)
    state_payload["episodes"] = current_episodes(u)

    return {
        **state_payload,
        "relationship_structure": u.get("relationship_structure"),
        "delivery_preferences": u.get("delivery_preferences"),
        "routine_profile": u.get("routine_profile"),
        "temporal_context": u.get("temporal_context"),
        "emotion_v2": build_emotion_snapshot_v2(u),
        "initiative_score_v2": compute_initiative_score_v2(u),
    }


@router.get("/last/{user_id}")
def last(user_id: str = Depends(validate_path_user_id)):
    u = get_user(user_id)
    apply_time_update_v2(u)
    u["temporal_context"] = build_temporal_context(u)

    return {
        "status": u["status"],
        "device_state": u["device_state"],
        "emotion": u["emotion"],
        "drives": u["drives"],
        "daily_routine_legacy": u.get("daily_routine", {}),
        "relationship_structure": u.get("relationship_structure"),
        "delivery_preferences": u.get("delivery_preferences"),
        "routine_profile": u.get("routine_profile"),
        "temporal_context": u.get("temporal_context"),
        "current_mood": u.get("current_mood", {}),
        "channel_preferences": u["channel_preferences"],
        "autonomy_settings": u["autonomy_settings"],
        "pending_replies": len(u["pending_replies"]),
        "assistant_typing": u.get("assistant_typing", False),
        "last_event_ts_ms": u["last_event_ts_ms"],
        "last_push_ts_ms": u["last_push_ts_ms"],
        "last_push_text": u["last_push_text"],
        "pushes_today": u["pushes_today"],
        "pushes_day_key": u["pushes_day_key"],
        "chat_count": len(u["chat"]),
        "memory_count": current_memory_count(u),
        "episode_count": current_episode_count(u),
        "narrative_count": len(u["emotional_narratives"]),
        "unread_assistant_count": u["unread_assistant_count"],
        "emotion_v2": build_emotion_snapshot_v2(u),
        "initiative_score_v2": compute_initiative_score_v2(u),
    }


@router.post("/register_token")
def register_token(t: TokenIn):
    u = get_user(t.user_id)
    u["fcm_token"] = t.fcm_token
    u["fcm_device_id"] = t.device_id
    u["identity"]["device_id"] = t.device_id

    add_operational_memory(
        u,
        f"Registered device token for device {t.device_id}",
        tags=["device", "token", "operational"],
        importance=5,
        meta={"device_id": t.device_id},
    )

    save_state()
    return {"ok": True}


@router.post("/set_name/{user_id}")
def set_user_name(
    user_id: str = Depends(validate_path_user_id),
    name: str = Query(...),
):
    u = get_user(user_id)

    clean = name.strip()[:80]
    if clean:
        previous_name = u.get("identity", {}).get("display_name", "") or u.get("user_name", "")
        u["user_name"] = clean
        u["identity"]["display_name"] = clean
        u["user_profile"]["display_name"] = clean

        if clean != previous_name:
            remember_user_identity(
                u,
                display_name=clean,
                login_name=u.get("identity", {}).get("login_name") or None,
            )

            add_episode(
                u,
                episode_type="identity_update",
                summary=f"User display name updated to {clean}",
                details={
                    "previous_name": previous_name,
                    "new_name": clean,
                },
                tags=["identity", "user"],
                importance=7,
            )

    save_state()

    return {
        "ok": True,
        "user_name": u["user_name"],
        "identity": u["identity"],
        "user_profile": u["user_profile"],
    }


@router.get("/name/{user_id}")
def get_user_name(user_id: str = Depends(validate_path_user_id)):
    u = get_user(user_id)
    return {
        "user_name": u.get("identity", {}).get("display_name", "") or u.get("user_name", "")
    }


@router.get("/memories/{user_id}")
def get_memories(user_id: str = Depends(validate_path_user_id)):
    u = get_user(user_id)
    memories = current_memories(u)
    return {"count": len(memories), "memories": memories}


@router.post("/memories/{user_id}")
def add_memory_endpoint(
    user_id: str = Depends(validate_path_user_id),
    mem: MemoryIn = Body(...),
):
    u = get_user(user_id)
    add_memory(u, mem.text, kind=mem.kind or "fact")
    consolidate_emotional_narratives(u)
    save_state()

    memories = current_memories(u)
    return {"ok": True, "count": len(memories), "memories": memories}


@router.get("/chat/{user_id}")
def get_chat(user_id: str = Depends(validate_path_user_id)):
    u = get_user(user_id)
    mark_chat_read(u)
    u["temporal_context"] = build_temporal_context(u)
    save_state()
    return {
        "messages": u["chat"],
        "unread_assistant_count": u["unread_assistant_count"],
        "relationship_structure": u.get("relationship_structure"),
        "delivery_preferences": u.get("delivery_preferences"),
        "routine_profile": u.get("routine_profile"),
        "temporal_context": u.get("temporal_context"),
        "pending_assistant": len(u["pending_replies"]) > 0,
        "assistant_typing": u.get("assistant_typing", False),
        "emotion_v2": build_emotion_snapshot_v2(u),
    }


@router.post("/chat/{user_id}/send")
def send_chat(
    user_id: str = Depends(validate_path_user_id),
    msg: ChatMessageIn = Body(...),
):
    u = get_user(user_id)
    decay_emotions(u)
    update_drives_passive(u)
    apply_time_update_v2(u)

    user_text = msg.text.strip()
    if not user_text:
        return {"ok": False, "error": "empty message"}

    return process_user_text_message(
        u=u,
        user_text=user_text,
        source="chat",
        user_audio_url=None
    )


@router.post("/chat/{user_id}/send_audio")
async def send_audio(
    user_id: str = Depends(validate_path_user_id),
    file: UploadFile = File(...),
):
    content_type = (file.content_type or "").strip().lower()
    if content_type and content_type not in ALLOWED_AUDIO_MIME_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported audio type: {content_type}")
    body = await file.read()
    if len(body) > MAX_UPLOAD_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Audio file too large (max {MAX_UPLOAD_AUDIO_BYTES} bytes)",
        )
    u = get_user(user_id)
    decay_emotions(u)
    update_drives_passive(u)
    apply_time_update_v2(u)

    saved_path, uploaded_audio_url = save_user_audio_from_bytes(
        body, getattr(file, "filename", None), content_type
    )
    transcript = transcribe_audio_file(saved_path)

    if not transcript:
        return {"ok": False, "error": "empty transcript"}

    return process_user_text_message(
        u=u,
        user_text=transcript,
        source="audio",
        user_audio_url=uploaded_audio_url
    )


@router.post("/relationship_mode/{user_id}")
def set_relationship_mode(
    user_id: str = Depends(validate_path_user_id),
    data: RelationshipModeIn = Body(...),
):
    u = get_user(user_id)

    mode = data.mode
    current_mode = u["relationship_structure"].get("current_mode", "friendship")

    if current_mode == mode:
        return {
            "ok": True,
            "relationship_structure": u["relationship_structure"],
        }

    now = now_ms()

    u["relationship_structure"]["current_mode"] = mode
    u["relationship_structure"]["last_mode_change_at"] = now
    u["relationship_structure"].setdefault("mode_history", []).append({
        "from": current_mode,
        "to": mode,
        "ts_ms": now,
    })

    remember_relationship_mode(
        u,
        mode=mode,
        previous_mode=current_mode,
    )

    add_episode(
        u,
        episode_type="relationship_mode_change",
        summary=f"Relationship mode changed from {current_mode} to {mode}",
        details={
            "from": current_mode,
            "to": mode,
        },
        tags=["relationship", "mode_change"],
        importance=8,
    )

    consolidate_emotional_narratives(u)
    save_state()

    return {
        "ok": True,
        "relationship_structure": u["relationship_structure"],
    }


app.include_router(router)
app.include_router(router, prefix="/v1")