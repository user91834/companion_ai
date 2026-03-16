# tests/test_memory.py
import pytest
from memory import (
    infer_tags,
    add_memory,
    get_all_memories,
    get_memory_count,
    get_semantic_memories,
    add_episode,
    get_all_episodes,
    get_episode_count,
)


def _minimal_user_state():
    return {
        "identity": {"user_id": "test-user"},
        "memories": [],
        "episodes": [],
    }


def test_infer_tags():
    tags = infer_tags("eu gosto de trabalhar com código e amor")
    assert len(tags) >= 1
    assert isinstance(tags, list)
    tags_en = infer_tags("I love you and miss you")
    assert "relationship" in tags_en or "general" in tags_en


def test_add_memory_in_memory():
    u = _minimal_user_state()
    add_memory(u, "The user likes pizza", kind="semantic")
    assert len(u["memories"]) == 1
    assert "pizza" in u["memories"][0]["text"]


def test_get_all_memories():
    u = _minimal_user_state()
    u["memories"] = [{"text": "A fact", "kind": "semantic", "ts_ms": 1}]
    items = get_all_memories(u)
    assert len(items) == 1
    assert items[0]["text"] == "A fact"


def test_get_memory_count():
    u = _minimal_user_state()
    u["memories"] = [{"text": "x", "kind": "semantic", "ts_ms": 1}] * 3
    assert get_memory_count(u) == 3


def test_get_semantic_memories():
    u = _minimal_user_state()
    u["memories"] = [
        {"text": "User likes pizza", "kind": "semantic", "tags": [], "ts_ms": 1},
        {"text": "User name is Bob", "kind": "semantic", "tags": [], "ts_ms": 2},
    ]
    results = get_semantic_memories(u, "pizza", limit=5)
    assert len(results) >= 1
    assert any("pizza" in m["text"] for m in results)


def test_add_episode_in_memory():
    u = _minimal_user_state()
    add_episode(
        u,
        episode_type="chat",
        summary="User said hello",
        details={},
        tags=["conversation"],
        importance=5,
    )
    assert len(u["episodes"]) == 1
    assert u["episodes"][0]["summary"] == "User said hello"


def test_get_episode_count():
    u = _minimal_user_state()
    u["episodes"] = [{"type": "chat", "summary": "x", "details": {}, "tags": [], "importance": 5, "ts_ms": 1}]
    assert get_episode_count(u) == 1
