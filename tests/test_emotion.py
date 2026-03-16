# tests/test_emotion.py
import pytest
from emotion import (
    ensure_emotional_engine_v2,
    ensure_current_mood,
    analyze_user_message,
    compute_initiative_score_v2,
    build_emotion_snapshot_v2,
    recompute_current_mood,
)


def _minimal_user_state():
    return {
        "identity": {"user_id": "test-user"},
        "user_profile": {"traits": {}},
        "relationship_structure": {"current_mode": "friendship"},
        "temporal_context": {"part_of_day": "afternoon", "local_date": "2025-01-15"},
        "last_event_ts_ms": 0,
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
            "availability": 80,
        },
        "chat": [],
    }


def test_ensure_emotional_engine_v2():
    u = _minimal_user_state()
    ensure_emotional_engine_v2(u)
    assert "emotion_v2" in u
    assert "stable" in u["emotion_v2"]
    assert "medium" in u["emotion_v2"]
    assert "fast" in u["emotion_v2"]


def test_ensure_current_mood():
    u = _minimal_user_state()
    ensure_current_mood(u)
    assert "current_mood" in u
    assert "warmth" in u["current_mood"]


def test_analyze_user_message():
    u = _minimal_user_state()
    ensure_emotional_engine_v2(u)
    analysis = analyze_user_message(u, "Hello, I missed you.", "text")
    assert "affection" in analysis
    assert "engagement" in analysis
    assert "depth" in analysis
    assert 0 <= analysis["affection"] <= 1
    assert 0 <= analysis["coldness"] <= 1


def test_compute_initiative_score_v2():
    u = _minimal_user_state()
    ensure_emotional_engine_v2(u)
    score = compute_initiative_score_v2(u)
    assert 0 <= score <= 1


def test_build_emotion_snapshot_v2():
    u = _minimal_user_state()
    ensure_emotional_engine_v2(u)
    snapshot = build_emotion_snapshot_v2(u)
    assert "stable" in snapshot
    assert "initiative_score" in snapshot
