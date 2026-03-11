from pydantic import BaseModel
from typing import Dict, Any, Optional, List


class EventIn(BaseModel):
    user_id: str
    device_id: str
    ts_ms: int
    event_type: str
    payload: Dict[str, Any]


class TokenIn(BaseModel):
    user_id: str
    device_id: str
    fcm_token: str


class ChatMessageIn(BaseModel):
    text: str


class AssistantMessageOut(BaseModel):
    text: str
    modality: str  # text | audio
    delay_ms: int = 0
    sequence_id: Optional[str] = None
    audio_url: Optional[str] = None


class ChatResponseOut(BaseModel):
    ok: bool
    messages: List[AssistantMessageOut]
    emotion_snapshot: Optional[Dict[str, Any]] = None
    reply_plan: Optional[Dict[str, Any]] = None
    relationship_stage: Optional[str] = None
    assistant_typing: Optional[bool] = None
    pending_assistant: Optional[bool] = None


class MemoryIn(BaseModel):
    text: str
    kind: Optional[str] = "fact"


class AutonomyIn(BaseModel):
    interruptions_enabled: bool
    scarcity_level: int
    inconvenience_level: int


class ContextIn(BaseModel):
    user_id: str
    device_id: str
    ts_ms: int
    text: str
    source: Optional[str] = "manual"