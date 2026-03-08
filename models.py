from pydantic import BaseModel
from typing import Dict, Any, Optional


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