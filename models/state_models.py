from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class TravelPhase(Enum):
    """여행 계획 단계"""

    GREETING = "greeting"
    DESTINATION_SELECTION = "destination_selection"
    PREFERENCE_COLLECTION = "preference_collection"
    STYLE_SELECTION = "style_selection"
    DURATION_SELECTION = "duration_selection"
    DATE_SELECTION = "date_selection"
    BUDGET_SELECTION = "budget_selection"
    COMPANION_SELECTION = "companion_selection"
    DETAILED_PLANNING = "detailed_planning"
    PLAN_GENERATION = "plan_generation"
    ACTION_SELECTION = "action_selection"
    CALENDAR_MANAGEMENT = "calendar_management"
    SHARING = "sharing"


@dataclass
class Message:
    """대화 메시지"""

    role: str  # user, assistant, system
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Destination:
    """여행지 정보"""

    name: str
    region: str
    type: str  # coastal, historical, nature, cultural, etc.
    description: str
    popularity_score: float = 0.0
    image_url: Optional[str] = None
    source_url: Optional[str] = None


@dataclass
class UserPreferences:
    """사용자 선호사항"""

    destination: Optional[str] = None
    travel_style: Optional[str] = None  # 여행 스타일
    duration: Optional[Dict[str, int]] = None  # 여행 기간
    departure_date: Optional[str] = None  # 출발 날짜
    budget: Optional[str] = None  # budget, moderate, comfortable, luxury, unlimited
    companion_type: Optional[str] = None  # solo, couple, family, friends, group
    additional_requests: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "destination": self.destination,
            "travel_style": self.travel_style,
            "duration": self.duration,
            "departure_date": self.departure_date,
            "budget": self.budget,
            "companion_type": self.companion_type,
            "additional_requests": self.additional_requests,
        }


@dataclass
class Place:
    """장소 정보"""

    name: str
    address: str
    category: str
    description: str
    rating: Optional[float] = None
    price_range: Optional[str] = None
    opening_hours: Optional[str] = None
    contact: Optional[str] = None
    image_url: Optional[str] = None
    coordinates: Optional[Dict[str, float]] = None  # {"lat": 0.0, "lng": 0.0}


@dataclass
class ScheduleItem:
    """일정 항목"""

    time: str
    activity: str
    location: str
    duration: int  # minutes
    category: str
    notes: Optional[str] = None
    estimated_cost: Optional[int] = None


@dataclass
class DaySchedule:
    """하루 일정"""

    date: str
    day_number: int
    events: List[ScheduleItem] = field(default_factory=list)
    total_cost: int = 0
    travel_time: int = 0  # total travel time in minutes


@dataclass
class TravelPlan:
    """완성된 여행 계획"""

    id: str
    title: str
    destination: str
    user_preferences: UserPreferences
    schedule: List[DaySchedule] = field(default_factory=list)
    recommended_places: List[Place] = field(default_factory=list)
    total_budget: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "destination": self.destination,
            "user_preferences": self.user_preferences.to_dict(),
            "schedule": [
                {
                    "date": day.date,
                    "day_number": day.day_number,
                    "events": [
                        {
                            "time": event.time,
                            "activity": event.activity,
                            "location": event.location,
                            "duration": event.duration,
                            "category": event.category,
                            "notes": event.notes,
                            "estimated_cost": event.estimated_cost,
                        }
                        for event in day.events
                    ],
                    "total_cost": day.total_cost,
                    "travel_time": day.travel_time,
                }
                for day in self.schedule
            ],
            "recommended_places": [
                {
                    "name": place.name,
                    "address": place.address,
                    "category": place.category,
                    "description": place.description,
                    "rating": place.rating,
                    "price_range": place.price_range,
                }
                for place in self.recommended_places
            ],
            "total_budget": self.total_budget,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class AgentResponse:
    """에이전트 응답"""

    message: str
    options: Optional[List[Dict[str, Any]]] = None
    travel_plan: Optional[TravelPlan] = None
    places: Optional[List[Place]] = None
    next_phase: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    requires_user_input: bool = True


@dataclass
class TravelPlanningState:
    """여행 계획 전체 상태"""

    # 기본 정보
    session_id: str
    user_id: Optional[str] = None

    # 대화 상태
    current_phase: TravelPhase = TravelPhase.GREETING
    conversation_history: List[Message] = field(default_factory=list)

    # 사용자 선호사항
    user_preferences: UserPreferences = field(default_factory=UserPreferences)

    # 검색 결과 및 선택사항
    available_destinations: List[Destination] = field(default_factory=list)
    destination_details: Optional[Dict[str, Any]] = None
    selected_places: List[Place] = field(default_factory=list)

    # 생성된 계획
    travel_plan: Optional[TravelPlan] = None

    # 카카오톡 인증 관련
    pending_auth_code: Optional[str] = None

    # 입력 대기 상태
    waiting_for_date_input: bool = False

    # 메타데이터
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def is_ready_for_planning(self) -> bool:
        """여행 계획 생성 준비 완료 여부 확인"""
        required_fields = [
            self.user_preferences.destination,
            self.user_preferences.travel_style,
            self.user_preferences.duration,
            self.user_preferences.departure_date,
            self.user_preferences.companion_type,
        ]
        return all(field is not None for field in required_fields)

    def get_missing_preferences(self) -> List[str]:
        """누락된 필수 정보 목록 반환"""
        from models.state_models import TRAVEL_STYLES

        missing = []

        if not self.user_preferences.destination:
            missing.append("destination")
        if (
            not self.user_preferences.travel_style
            or self.user_preferences.travel_style not in TRAVEL_STYLES
        ):
            missing.append("travel_style")
        if not self.user_preferences.duration:
            missing.append("duration")
        if not self.user_preferences.departure_date:
            missing.append("departure_date")
        if not self.user_preferences.companion_type:
            missing.append("companion_type")

        return missing

    def update_phase(self, new_phase: TravelPhase):
        """단계 업데이트"""
        self.current_phase = new_phase
        self.updated_at = datetime.now()

    def add_message(self, role: str, content: str, metadata: Dict[str, Any] = None):
        """대화 히스토리에 메시지 추가"""
        message = Message(
            role=role,
            content=content,
            timestamp=datetime.now(),
            metadata=metadata or {},
        )
        self.conversation_history.append(message)
        self.updated_at = datetime.now()

    def get_conversation_context(self, last_n: int = 10) -> List[Message]:
        """최근 대화 컨텍스트 반환"""
        return self.conversation_history[-last_n:] if self.conversation_history else []


# 상수 정의
TRAVEL_STYLES = {
    "culture": {
        "name": "문화/역사 탐방",
        "icon": "🏛️",
        "desc": "박물관, 유적지, 전통 문화 체험",
    },
    "nature": {
        "name": "자연/힐링",
        "icon": "🌊",
        "desc": "바다, 산, 공원에서의 휴식과 치유",
    },
    "food": {
        "name": "맛집 투어",
        "icon": "🍽️",
        "desc": "현지 맛집과 특색 있는 음식 탐방",
    },
    "shopping": {
        "name": "쇼핑/도시",
        "icon": "🛍️",
        "desc": "쇼핑몰, 시장, 도심 명소 탐방",
    },
    "activity": {
        "name": "액티비티/모험",
        "icon": "🎡",
        "desc": "테마파크, 익스트림 스포츠, 체험 활동",
    },
    "photo": {
        "name": "인스타/감성",
        "icon": "📸",
        "desc": "예쁜 카페, 포토존, 감성 장소",
    },
}

BUDGET_RANGES = {
    "budget": {"name": "가성비 여행", "range": "~10만원", "icon": "💸"},
    "moderate": {"name": "적당한 여행", "range": "10-30만원", "icon": "💳"},
    "comfortable": {"name": "여유로운 여행", "range": "30-50만원", "icon": "💎"},
    "luxury": {"name": "럭셔리 여행", "range": "50만원+", "icon": "👑"},
    "unlimited": {"name": "예산 무관", "range": "예산 무관", "icon": "🤷"},
}

COMPANION_TYPES = {
    "solo": {"name": "혼자", "icon": "🙋"},
    "couple": {"name": "연인/배우자", "icon": "💑"},
    "family": {"name": "가족", "icon": "👨‍👩‍👧‍👦"},
    "friends": {"name": "친구들", "icon": "👫"},
    "group": {"name": "단체", "icon": "👥"},
}
