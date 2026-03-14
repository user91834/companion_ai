from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List, Literal


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
    modality: Literal["text", "audio"] = "text"
    delay_ms: int = 0
    sequence_id: Optional[str] = None
    audio_url: Optional[str] = None


class RelationshipStructureOut(BaseModel):
    current_mode: Literal[
        "friendship",
        "friends_with_benefits",
        "open_relationship",
        "monogamous_relationship",
    ] = "friendship"
    default_mode: Literal[
        "friendship",
        "friends_with_benefits",
        "open_relationship",
        "monogamous_relationship",
    ] = "friendship"
    available_modes: List[str] = Field(
        default_factory=lambda: [
            "friendship",
            "friends_with_benefits",
            "open_relationship",
            "monogamous_relationship",
        ]
    )
    last_mode_change_at: Optional[int] = None


class DeliveryPreferencesOut(BaseModel):
    inactive_delivery_mode: Literal["text", "audio", "both"] = "text"
    allow_background_audio: bool = False
    allow_lockscreen_audio: bool = False
    insistent_mode: bool = False
    quiet_hours_enabled: bool = True
    quiet_hours: Dict[str, str] = Field(
        default_factory=lambda: {
            "start": "23:00",
            "end": "07:00",
        }
    )
    respect_user_routine: bool = True


class UserProfileOut(BaseModel):
    display_name: Optional[str] = None
    login_name: Optional[str] = None
    traits: Dict[str, float] = Field(default_factory=dict)
    preferences_summary: Optional[str] = None
    important_facts_summary: Optional[str] = None


class RoutineBlockOut(BaseModel):
    start: str
    end: str
    label: str
    source: Optional[str] = "user_defined"
    confidence: float = 1.0


class RoutineProfileOut(BaseModel):
    timezone: str = "America/Sao_Paulo"
    weekly_schedule: Dict[str, List[RoutineBlockOut]] = Field(
        default_factory=lambda: {
            "monday": [],
            "tuesday": [],
            "wednesday": [],
            "thursday": [],
            "friday": [],
            "saturday": [],
            "sunday": [],
        }
    )
    exceptions: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_score: float = 0.0
    last_updated_at: Optional[int] = None


class TemporalContextOut(BaseModel):
    timezone: str = "America/Sao_Paulo"
    local_now_iso: Optional[str] = None
    local_date: Optional[str] = None
    local_time: Optional[str] = None
    weekday: Optional[str] = None
    is_daytime: bool = False
    is_night: bool = False
    part_of_day: Optional[str] = None
    relative_day_labels: Dict[str, str] = Field(
        default_factory=lambda: {
            "today": "",
            "yesterday": "",
            "day_before_yesterday": "",
            "tomorrow": "",
        }
    )
    last_computed_at: Optional[int] = None


class ChatResponseOut(BaseModel):
    ok: bool
    messages: List[AssistantMessageOut]
    emotion_snapshot: Optional[Dict[str, Any]] = None
    reply_plan: Optional[Dict[str, Any]] = None

    # novo núcleo de estado exposto
    relationship_structure: Optional[RelationshipStructureOut] = None
    delivery_preferences: Optional[DeliveryPreferencesOut] = None
    user_profile: Optional[UserProfileOut] = None
    routine_profile: Optional[RoutineProfileOut] = None
    temporal_context: Optional[TemporalContextOut] = None

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

class RelationshipModeIn(BaseModel):
    mode: Literal[
        "friendship",
        "friends_with_benefits",
        "open_relationship",
        "monogamous_relationship",
    ]