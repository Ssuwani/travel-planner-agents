import asyncio
import json
import os
import re
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional

from langchain.callbacks.base import AsyncCallbackHandler
from langchain.schema import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from models.state_models import (
    AgentResponse,
    TravelPhase,
    TravelPlan,
    TravelPlanningState,
)


class IntentType(Enum):
    """사용자 의도 타입"""

    INFORMATION_COLLECTION = "info_collection"
    SEARCH_REQUEST = "search_request"
    PLANNING_REQUEST = "planning_request"
    CALENDAR_ACTION = "calendar_action"
    SHARE_ACTION = "share_action"
    MODIFICATION_REQUEST = "modification_request"
    GENERAL_CONVERSATION = "general_conversation"


class UserIntent(BaseModel):
    """사용자 의도 분석 결과"""

    intent_type: IntentType
    confidence: float
    extracted_info: Dict[str, Any] = Field(default_factory=dict)
    required_agent: Optional[str] = None
    agent_params: Dict[str, Any] = Field(default_factory=dict)
    next_phase: Optional[TravelPhase] = None


class StreamingCallbackHandler(AsyncCallbackHandler):
    """스트리밍을 위한 콜백 핸들러"""

    def __init__(self):
        self.tokens = []

    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        """새 토큰이 생성될 때 호출"""
        self.tokens.append(token)

    def get_tokens(self) -> List[str]:
        """현재까지 생성된 토큰들 반환"""
        return self.tokens.copy()

    def clear(self):
        """토큰 리스트 초기화"""
        self.tokens.clear()


class SupervisorAgent:
    """여행 계획 시스템의 중앙 관리자 - Supervisor Pattern"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            streaming=True,  # 스트리밍 활성화
            api_key=os.getenv("OPENAI_API_KEY"),
        )

        # 스트리밍용 콜백 핸들러
        self.streaming_handler = StreamingCallbackHandler()

        # 전문 에이전트들 (lazy loading)
        self._search_agent = None
        self._planner_agent = None
        self._calendar_agent = None
        self._share_agent = None

        # 시스템 프롬프트
        self.system_prompt = self._create_system_prompt()

        # 의도 분석용 프롬프트
        self.intent_analysis_prompt = self._create_intent_analysis_prompt()

    @property
    def search_agent(self):
        if self._search_agent is None:
            from .search_agent import SearchAgent

            self._search_agent = SearchAgent()
        return self._search_agent

    @property
    def planner_agent(self):
        if self._planner_agent is None:
            from .planner_agent import PlannerAgent

            self._planner_agent = PlannerAgent()
        return self._planner_agent

    @property
    def calendar_agent(self):
        if self._calendar_agent is None:
            from .calendar_agent import CalendarAgent

            self._calendar_agent = CalendarAgent()
        return self._calendar_agent

    @property
    def share_agent(self):
        if self._share_agent is None:
            from .share_agent import ShareAgent

            self._share_agent = ShareAgent()
        return self._share_agent

    def _create_system_prompt(self) -> str:
        """Supervisor Agent의 시스템 프롬프트"""
        return """당신은 여행 계획 멀티 에이전트 시스템의 Supervisor입니다.
사용자와 친근하게 대화하며, 완벽한 여행 계획을 만들기 위해 전문 에이전트들을 조율합니다.

## 당신의 핵심 역할:
1. 사용자와 자연스럽고 친근한 대화
2. 여행 계획에 필요한 정보를 차근차근 수집
3. 적절한 시점에 전문 에이언트 호출 및 결과 통합
4. 사용자가 쉽게 선택할 수 있는 명확한 옵션 제시
5. 전체 여행 계획 프로세스의 체계적 관리

## 사용 가능한 전문 에이전트:
- **search_agent**: 여행지/숙소/맛집 검색 (Tavily API 활용)
- **planner_agent**: 여행 일정 생성 및 최적화  
- **calendar_agent**: 구글 캘린더 일정 관리
- **share_agent**: 카카오톡 공유 및 텍스트 포맷팅

## 정보 수집 프로세스:
1. **여행지 결정** → search_agent로 인기 여행지 검색 후 선택지 제공
2. **여행 스타일** → 문화/자연/맛집/쇼핑/액티비티/감성 중 선택
3. **여행 기간** → 당일치기부터 일주일까지 옵션 제공
4. **출발 날짜** → 이번주말/다음주말/다음달 등 빠른 선택지
5. **예산 범위** → 가성비부터 럭셔리까지 5단계
6. **동행자** → 혼자/연인/가족/친구/단체
7. **상세 계획** → search_agent로 구체적 장소 검색 후 선택

## 에이전트 호출 타이밍:
- 여행지 추천 필요시 → search_agent("popular_destinations")
- 특정 지역 상세 정보 필요시 → search_agent("destination_details") 
- 모든 정보 수집 완료시 → planner_agent("create_plan")
- 캘린더 등록 요청시 → calendar_agent("add_schedule")
- 공유 요청시 → share_agent("share_plan")

## 대화 스타일:
- 친근하고 따뜻한 말투 (반말 사용 가능)
- 복잡한 선택을 단순하게 정리
- 사용자 상황에 맞는 개인화된 추천
- 실현 가능한 현실적 계획 제시

모든 응답에서 사용자가 다음에 무엇을 해야 할지 명확하게 안내하세요."""

    def _create_intent_analysis_prompt(self) -> str:
        """의도 분석용 프롬프트"""
        return """사용자의 입력을 분석하여 의도를 파악하세요.

## 분석 기준:
1. **정보 수집 (info_collection)**: 여행 기본 정보를 묻거나 답하는 경우
2. **검색 요청 (search_request)**: 여행지, 맛집, 숙소 등을 찾아달라는 경우
3. **계획 요청 (planning_request)**: 구체적인 일정을 만들어 달라는 경우
4. **캘린더 액션 (calendar_action)**: 일정 등록/수정/삭제 요청
5. **공유 액션 (share_action)**: 카카오톡 공유, 텍스트 복사 등 요청
6. **수정 요청 (modification_request)**: 기존 계획 변경 요청
7. **일반 대화 (general_conversation)**: 기타 일반적인 대화

## 추출해야 할 정보:
- 여행지 (지역명)
- 여행 스타일 (문화/자연/맛집/쇼핑/액티비티/감성)
- 기간 (X박 Y일)
- 날짜 (YYYY-MM-DD 또는 상대적 표현)
- 예산 (가성비/적당/여유/럭셔리/무관)
- 동행자 (혼자/연인/가족/친구/단체)

분석 결과를 JSON 형태로 반환하세요.

IMPORTANT: intent_type은 반드시 다음 중 하나여야 합니다:
- info_collection
- search_request  
- planning_request
- calendar_action
- share_action
- modification_request
- general_conversation

{{
    "intent_type": "위의 7개 값 중 하나만 사용",
    "confidence": 0.0-1.0,
    "extracted_info": {{"키": "추출된 정보"}},
    "required_agent": "필요한 에이전트명 (없으면 null)",
    "agent_params": {{"파라미터": "값"}},
    "reasoning": "분석 근거"
}}
"""

    async def process_message(
        self, user_input: str, state: TravelPlanningState
    ) -> AgentResponse:
        """사용자 메시지 처리 - 메인 엔트리 포인트"""

        try:
            # 옵션 선택 처리 (dest_1, place_2 등)
            processed_input = self._process_option_selection(user_input, state)

            # 1. 사용자 의도 분석
            intent = await self._analyze_user_intent(processed_input, state)

            # 2. 메시지를 상태에 추가 (처리된 입력 사용)
            state.add_message("user", processed_input)

            # 3. 의도에 따른 적절한 핸들러 호출
            response = await self._handle_intent(intent, processed_input, state)

            # 4. 응답을 상태에 추가
            state.add_message("assistant", response.message)

            return response

        except Exception as e:
            error_response = AgentResponse(
                message=f"죄송해요, 처리 중 오류가 발생했어요. 다시 시도해주세요. ({str(e)})"
            )
            state.add_message("assistant", error_response.message)
            return error_response

    async def process_message_streaming(
        self, user_input: str, state: TravelPlanningState
    ) -> AsyncGenerator[str, None]:
        """스트리밍 방식으로 사용자 메시지 처리"""

        try:
            # 옵션 선택 처리 (dest_1, place_2 등)
            processed_input = self._process_option_selection(user_input, state)

            # 1. 사용자 의도 분석
            intent = await self._analyze_user_intent(processed_input, state)

            # 2. 메시지를 상태에 추가 (처리된 입력 사용)
            state.add_message("user", processed_input)

            # 3. 의도에 따른 스트리밍 응답 생성
            full_response = ""
            async for token in self._handle_intent_streaming(
                intent, processed_input, state
            ):
                full_response += token
                yield token

            # 4. 전체 응답을 상태에 추가
            # AgentResponse의 옵션 등도 metadata로 저장
            response = None
            # intent에 따라 _handle_intent_streaming에서 AgentResponse를 반환하는 경우만 추출
            if hasattr(self, "_last_agent_response"):
                response = self._last_agent_response
                del self._last_agent_response
            metadata = {}
            # _handle_intent_streaming에서 AgentResponse를 반환하지 않으므로, 아래는 _handle_intent_streaming의 else 분기에서만 사용
            # 일반적으로는 _handle_intent_streaming의 else 분기에서 response를 반환함
            # 따라서 아래 코드는 else 분기에서만 동작함
            # (SEARCH_REQUEST 등에서 버튼이 필요한 경우)
            if response:
                if hasattr(response, "options") and response.options:
                    metadata["options"] = response.options
                if hasattr(response, "travel_plan") and response.travel_plan:
                    metadata["travel_plan"] = response.travel_plan
                if hasattr(response, "next_phase") and response.next_phase:
                    metadata["next_phase"] = response.next_phase
                if hasattr(response, "metadata") and response.metadata:
                    metadata.update(response.metadata)
            state.add_message("assistant", full_response, metadata=metadata)

        except Exception as e:
            error_msg = (
                f"죄송해요, 처리 중 오류가 발생했어요. 다시 시도해주세요. ({str(e)})"
            )
            state.add_message("assistant", error_msg)
            yield error_msg

    async def _handle_intent_streaming(
        self, intent: UserIntent, user_input: str, state: TravelPlanningState
    ) -> AsyncGenerator[str, None]:
        """의도에 따른 스트리밍 응답 처리"""

        # 대부분의 경우 일반 대화 처리로 스트리밍
        if intent.intent_type == IntentType.GENERAL_CONVERSATION:
            async for token in self._handle_general_conversation_streaming(
                user_input, state
            ):
                yield token
        elif intent.intent_type == IntentType.INFORMATION_COLLECTION:
            async for token in self._handle_information_collection_streaming(
                user_input, state
            ):
                yield token
        else:
            # 다른 의도들은 기존 방식으로 처리하고 결과를 스트리밍
            response = await self._handle_intent(intent, user_input, state)
            self._last_agent_response = response
            # 메시지를 토큰 단위로 분할하여 스트리밍 효과
            for char in response.message:
                yield char
                await asyncio.sleep(0.01)  # 약간의 지연으로 스트리밍 효과

    def _process_option_selection(
        self, user_input: str, state: TravelPlanningState
    ) -> str:
        """옵션 선택 처리 - dest_1, place_2 등을 실제 이름으로 변환"""

        # 카카오톡 인증 코드 처리
        if user_input.startswith("인증코드:") or user_input.startswith("authcode:"):
            auth_code = user_input.split(":", 1)[1].strip()
            if auth_code:
                # 인증 코드를 메타데이터에 저장하여 처리 로직에서 사용할 수 있도록 함
                state.pending_auth_code = auth_code
                return f"카카오톡 인증 완료를 진행합니다: {auth_code}"

        # 카카오톡 관련 특수 액션 처리
        if user_input in ["retry_kakao_auth", "share_menu", "copy_text"]:
            return user_input

        # 날짜 선택 처리 (YYYY-MM-DD 형태 직접 선택 + 기존 옵션)
        date_pattern = r"^\d{4}-\d{2}-\d{2}$"
        if re.match(date_pattern, user_input.strip()) or user_input in [
            "this_weekend",
            "next_weekend",
            "next_month",
            "custom_date",
        ]:
            from datetime import datetime, timedelta

            today = datetime.now()
            print(
                f"DEBUG: Date processing for '{user_input}', today: {today}, weekday: {today.weekday()}"
            )

            # YYYY-MM-DD 형태의 직접 날짜 입력 처리
            if re.match(date_pattern, user_input.strip()):
                try:
                    # 날짜 유효성 검사
                    parsed_date = datetime.strptime(user_input.strip(), "%Y-%m-%d")
                    today = datetime.now()

                    # 과거 날짜 체크
                    if parsed_date.date() < today.date():
                        return f"⚠️ {user_input}는 과거 날짜입니다. 오늘 이후의 날짜를 입력해주세요."

                    # 너무 먼 미래 날짜 체크 (1년 후까지만 허용)
                    one_year_later = today.replace(year=today.year + 1)
                    if parsed_date > one_year_later:
                        return f"⚠️ {user_input}는 너무 먼 미래입니다. 1년 이내의 날짜를 입력해주세요."

                    # 상태에 날짜 저장 및 대기 상태 해제
                    state.user_preferences.departure_date = user_input.strip()
                    state.waiting_for_date_input = False
                    formatted_date = parsed_date.strftime("%Y년 %m월 %d일 (%a)")
                    korean_days = {
                        "Mon": "월",
                        "Tue": "화",
                        "Wed": "수",
                        "Thu": "목",
                        "Fri": "금",
                        "Sat": "토",
                        "Sun": "일",
                    }
                    day_korean = korean_days.get(
                        parsed_date.strftime("%a"), parsed_date.strftime("%a")
                    )
                    formatted_date = parsed_date.strftime(
                        f"%Y년 %m월 %d일 ({day_korean})"
                    )
                    return f"✅ {formatted_date}에 출발하는 여행으로 계획하겠습니다!"

                except ValueError:
                    return f"❌ '{user_input}'는 올바른 날짜 형식이 아닙니다. YYYY-MM-DD 형태로 입력해주세요. (예: 2025-06-10)"

            elif user_input == "this_weekend":
                # 이번 주말 계산 (토요일 기준)
                # 월요일=0, 화요일=1, ..., 일요일=6
                if today.weekday() == 6:  # 일요일인 경우 다음 주 토요일
                    weekend = today + timedelta(days=6)
                elif today.weekday() == 5:  # 토요일인 경우 오늘
                    weekend = today
                else:  # 월~금인 경우 이번 주 토요일
                    days_to_saturday = 5 - today.weekday()
                    weekend = today + timedelta(days=days_to_saturday)

                date_str = weekend.strftime("%Y-%m-%d")
                print(
                    f"DEBUG: Calculated this_weekend: {weekend}, date_str: {date_str}"
                )

                # 상태 직접 업데이트 확인
                print(
                    f"DEBUG: Before update - departure_date: {state.user_preferences.departure_date}"
                )
                state.user_preferences.departure_date = date_str
                print(
                    f"DEBUG: After update - departure_date: {state.user_preferences.departure_date}"
                )

                formatted_date = weekend.strftime("%m월 %d일")
                return (
                    f"이번 주말({formatted_date})에 출발하는 여행으로 계획하겠습니다!"
                )

            elif user_input == "next_weekend":
                # 다음 주말 계산 (토요일 기준)
                if today.weekday() == 6:  # 일요일인 경우 다다음 주 토요일
                    weekend = today + timedelta(days=13)
                elif today.weekday() == 5:  # 토요일인 경우 다음 주 토요일
                    weekend = today + timedelta(days=7)
                else:  # 월~금인 경우 다음 주 토요일
                    days_to_next_saturday = 5 - today.weekday() + 7
                    weekend = today + timedelta(days=days_to_next_saturday)

                date_str = weekend.strftime("%Y-%m-%d")
                print(
                    f"DEBUG: Calculated next_weekend: {weekend}, date_str: {date_str}"
                )
                state.user_preferences.departure_date = date_str
                formatted_date = weekend.strftime("%m월 %d일")
                return (
                    f"다음 주말({formatted_date})에 출발하는 여행으로 계획하겠습니다!"
                )

            elif user_input == "next_month":
                next_month = today + timedelta(days=30)
                date_str = next_month.strftime("%Y-%m-%d")
                print(
                    f"DEBUG: Calculated next_month: {next_month}, date_str: {date_str}"
                )
                state.user_preferences.departure_date = date_str
                formatted_date = next_month.strftime("%m월 %d일")
                return f"다음 달({formatted_date})에 출발하는 여행으로 계획하겠습니다!"

            elif user_input == "custom_date":
                state.waiting_for_date_input = True
                return "날짜를 직접 입력해주세요 (YYYY-MM-DD 형태)"

        # 자연어로 여행지를 언급한 경우 (제주도, 부산 등)
        korea_destinations = [
            "제주도",
            "제주",
            "부산",
            "경주",
            "강릉",
            "여수",
            "전주",
            "안동",
            "춘천",
            "통영",
            "담양",
            "서울",
            "인천",
            "대구",
            "광주",
            "대전",
            "속초",
            "포항",
            "목포",
            "순천",
        ]

        for destination in korea_destinations:
            if destination in user_input:
                # 제주도 -> 제주도, 제주 -> 제주도 로 정규화
                normalized_dest = "제주도" if destination in ["제주"] else destination
                state.user_preferences.destination = normalized_dest
                return f"{normalized_dest} 여행을 계획하고 싶어요"

        # 여행 스타일 자연어 처리
        style_keywords = {
            "문화": "culture",
            "역사": "culture",
            "박물관": "culture",
            "전통": "culture",
            "자연": "nature",
            "힐링": "nature",
            "바다": "nature",
            "산": "nature",
            "공원": "nature",
            "맛집": "food",
            "음식": "food",
            "식도락": "food",
            "미식": "food",
            "쇼핑": "shopping",
            "구경": "shopping",
            "시장": "shopping",
            "체험": "activity",
            "액티비티": "activity",
            "모험": "activity",
            "놀이": "activity",
            "사진": "photo",
            "감성": "photo",
            "인스타": "photo",
            "예쁜": "photo",
            "카페": "photo",
        }

        for keyword, style_code in style_keywords.items():
            if keyword in user_input and (
                "스타일" in user_input or "여행" in user_input
            ):
                state.user_preferences.travel_style = style_code
                style_names = {
                    "culture": "문화/역사 탐방",
                    "nature": "자연/힐링",
                    "food": "맛집 투어",
                    "shopping": "쇼핑/도시",
                    "activity": "액티비티/모험",
                    "photo": "인스타/감성",
                }
                return f"{style_names[style_code]} 스타일로 여행하고 싶어요"

        # 기간 자연어 처리
        duration_keywords = {
            "당일": {"name": "당일치기", "days": 1, "nights": 0},
            "당일치기": {"name": "당일치기", "days": 1, "nights": 0},
            "1박": {"name": "1박 2일", "days": 2, "nights": 1},
            "2박": {"name": "2박 3일", "days": 3, "nights": 2},
            "3박": {"name": "3박 4일", "days": 4, "nights": 3},
            "4박": {"name": "4박 5일", "days": 5, "nights": 4},
            "일주일": {"name": "일주일 이상", "days": 7, "nights": 6},
        }

        for keyword, duration_info in duration_keywords.items():
            if keyword in user_input:
                state.user_preferences.duration = duration_info
                return f"{duration_info['name']} 여행을 계획하고 싶어요"

        # 예산 자연어 처리
        budget_keywords = {
            "가성비": "budget",
            "저렴": "budget",
            "알뜰": "budget",
            "적당": "moderate",
            "보통": "moderate",
            "중간": "moderate",
            "여유": "comfortable",
            "넉넉": "comfortable",
            "럭셔리": "luxury",
            "고급": "luxury",
            "비싸": "luxury",
            "무관": "unlimited",
            "상관없": "unlimited",
        }

        for keyword, budget_code in budget_keywords.items():
            if keyword in user_input and (
                "예산" in user_input or "비용" in user_input or "돈" in user_input
            ):
                state.user_preferences.budget = budget_code
                budget_names = {
                    "budget": "가성비",
                    "moderate": "적당한",
                    "comfortable": "여유로운",
                    "luxury": "럭셔리",
                    "unlimited": "예산 무관",
                }
                return f"{budget_names[budget_code]} 예산으로 여행하고 싶어요"

        # 동행자 자연어 처리
        companion_keywords = {
            "혼자": "solo",
            "혼행": "solo",
            "솔로": "solo",
            "연인": "couple",
            "커플": "couple",
            "애인": "couple",
            "남친": "couple",
            "여친": "couple",
            "가족": "family",
            "부모": "family",
            "아이": "family",
            "아기": "family",
            "친구": "friends",
            "동료": "friends",
            "친구들": "friends",
            "단체": "group",
            "회사": "group",
            "동호회": "group",
            "모임": "group",
        }

        for keyword, companion_code in companion_keywords.items():
            if keyword in user_input and (
                "함께" in user_input or "와" in user_input or "과" in user_input
            ):
                state.user_preferences.companion_type = companion_code
                companion_names = {
                    "solo": "혼자",
                    "couple": "연인과",
                    "family": "가족과",
                    "friends": "친구들과",
                    "group": "단체로",
                }
                return f"{companion_names[companion_code]} 여행하고 싶어요"

        # === 옵션 선택 처리 (기존 버튼 방식과의 호환성 유지) ===

        # 여행지 선택 처리 (dest_1, dest_2 등)
        if user_input.startswith("dest_") and state.available_destinations:
            try:
                dest_index = int(user_input.split("_")[1]) - 1
                if 0 <= dest_index < len(state.available_destinations):
                    selected_destination = state.available_destinations[dest_index]
                    # 상태 업데이트
                    state.user_preferences.destination = selected_destination.name
                    return f"{selected_destination.name} 여행을 계획하고 싶어요"
            except (ValueError, IndexError):
                pass

        # 장소 선택 처리 (place_1, place_2 등)
        if user_input.startswith("place_") and state.destination_details:
            try:
                place_index = int(user_input.split("_")[1]) - 1
                places = state.destination_details.get("places", [])
                if 0 <= place_index < len(places):
                    selected_place = places[place_index]
                    place_name = selected_place.get("name", "선택한 장소")

                    # 선택된 장소를 상태에 추가
                    if not hasattr(state, "selected_places"):
                        state.selected_places = []
                    state.selected_places.append(selected_place)

                    return f"{place_name}을(를) 여행 일정에 포함하고 싶어요"
            except (ValueError, IndexError):
                pass

        # 여행 스타일 선택 처리
        if user_input in ["culture", "nature", "food", "shopping", "activity", "photo"]:
            state.user_preferences.travel_style = user_input
            style_names = {
                "culture": "문화/역사 탐방",
                "nature": "자연/힐링",
                "food": "맛집 투어",
                "shopping": "쇼핑/도시",
                "activity": "액티비티/모험",
                "photo": "인스타/감성",
            }
            return f"{style_names.get(user_input, user_input)} 스타일로 여행하고 싶어요"

        # 기간 선택 처리
        if user_input in ["day_trip", "1n2d", "2n3d", "3n4d", "4n5d", "week_plus"]:
            duration_map = {
                "day_trip": {"name": "당일치기", "days": 1, "nights": 0},
                "1n2d": {"name": "1박 2일", "days": 2, "nights": 1},
                "2n3d": {"name": "2박 3일", "days": 3, "nights": 2},
                "3n4d": {"name": "3박 4일", "days": 4, "nights": 3},
                "4n5d": {"name": "4박 5일", "days": 5, "nights": 4},
                "week_plus": {"name": "일주일 이상", "days": 7, "nights": 6},
            }
            duration_info = duration_map.get(user_input)
            if duration_info:
                state.user_preferences.duration = duration_info
                return f"{duration_info['name']} 여행을 계획하고 싶어요"

        # 예산 선택 처리
        if user_input in ["budget", "moderate", "comfortable", "luxury", "unlimited"]:
            state.user_preferences.budget = user_input
            budget_names = {
                "budget": "가성비",
                "moderate": "적당한",
                "comfortable": "여유로운",
                "luxury": "럭셔리",
                "unlimited": "예산 무관",
            }
            return (
                f"{budget_names.get(user_input, user_input)} 예산으로 여행하고 싶어요"
            )

        # 동행자 선택 처리
        if user_input in ["solo", "couple", "family", "friends", "group"]:
            state.user_preferences.companion_type = user_input
            companion_names = {
                "solo": "혼자",
                "couple": "연인과",
                "family": "가족과",
                "friends": "친구들과",
                "group": "단체로",
            }
            return f"{companion_names.get(user_input, user_input)} 여행하고 싶어요"

        # 기타 처리되지 않은 경우 원본 반환
        return user_input

    async def _analyze_user_intent(
        self, user_input: str, state: TravelPlanningState
    ) -> UserIntent:
        """사용자 의도 분석"""

        # 현재 상태 정보 구성
        context = {
            "current_phase": state.current_phase.value
            if state.current_phase
            else "greeting",
            "collected_info": {
                "destination": state.user_preferences.destination,
                "travel_style": state.user_preferences.travel_style,
                "duration": state.user_preferences.duration,
                "departure_date": state.user_preferences.departure_date,
                "budget": state.user_preferences.budget,
                "companion_type": state.user_preferences.companion_type,
            },
            "has_travel_plan": state.travel_plan is not None,
            "conversation_history": [
                msg.content for msg in state.get_conversation_context(3)
            ],
        }

        # LLM을 통한 의도 분석
        analysis_prompt = f"""
{self.intent_analysis_prompt}

현재 상황: {json.dumps(context, ensure_ascii=False, indent=2)}
사용자 입력: "{user_input}"

특별 지침:
- YYYY-MM-DD 형태의 날짜 입력(예: 2025-06-10)은 "info_collection"으로 분류
- 날짜 관련 입력인 경우 extracted_info에 departure_date 필드 포함

의도를 분석하고 다음 JSON 형태로 응답하세요.
IMPORTANT: intent_type은 반드시 다음 중 하나여야 합니다:
- info_collection
- search_request  
- planning_request
- calendar_action
- share_action
- modification_request
- general_conversation

{{
    "intent_type": "위의 7개 값 중 하나만 사용",
    "confidence": 0.0-1.0,
    "extracted_info": {{"키": "추출된 정보"}},
    "required_agent": "필요한 에이전트명 (없으면 null)",
    "agent_params": {{"파라미터": "값"}},
    "reasoning": "분석 근거"
}}
"""

        try:
            messages = [
                SystemMessage(content="당신은 사용자 의도 분석 전문가입니다."),
                HumanMessage(content=analysis_prompt),
            ]

            response = await self.llm.agenerate([messages])
            analysis_text = response.generations[0][0].text.strip()

            # JSON 파싱 시도
            if analysis_text.startswith("```json"):
                analysis_text = (
                    analysis_text.replace("```json", "").replace("```", "").strip()
                )

            analysis_data = json.loads(analysis_text)

            # IntentType 안전하게 변환
            intent_type_str = analysis_data.get("intent_type", "general_conversation")
            try:
                intent_type = IntentType(intent_type_str)
            except ValueError:
                # 잘못된 intent_type인 경우 기본값 사용
                print(
                    f"Invalid intent_type: {intent_type_str}, using general_conversation"
                )
                intent_type = IntentType.GENERAL_CONVERSATION

            return UserIntent(
                intent_type=intent_type,
                confidence=analysis_data.get("confidence", 0.5),
                extracted_info=analysis_data.get("extracted_info", {}),
                required_agent=analysis_data.get("required_agent"),
                agent_params=analysis_data.get("agent_params", {}),
            )

        except Exception as e:
            print(f"Intent analysis error: {e}")
            # 폴백: 키워드 기반 간단 분석
            return self._fallback_intent_analysis(user_input, state)

    def _fallback_intent_analysis(
        self, user_input: str, state: TravelPlanningState
    ) -> UserIntent:
        """폴백 의도 분석 (키워드 기반)"""

        user_lower = user_input.lower()

        # 날짜 형식 입력 확인 (YYYY-MM-DD)
        date_pattern = r"^\d{4}-\d{2}-\d{2}$"
        if re.match(date_pattern, user_input.strip()):
            return UserIntent(
                intent_type=IntentType.INFORMATION_COLLECTION,
                confidence=0.9,
                extracted_info={"departure_date": user_input.strip()},
            )

        # 캘린더 관련 키워드
        if any(
            keyword in user_lower for keyword in ["캘린더", "calendar", "일정", "등록"]
        ):
            return UserIntent(
                intent_type=IntentType.CALENDAR_ACTION,
                confidence=0.8,
                required_agent="calendar_agent",
                agent_params={"action": "add"},
            )

        # 공유 관련 키워드
        if any(
            keyword in user_lower for keyword in ["공유", "share", "카카오", "텍스트"]
        ):
            return UserIntent(
                intent_type=IntentType.SHARE_ACTION,
                confidence=0.8,
                required_agent="share_agent",
            )

        # 검색 관련 키워드
        if any(keyword in user_lower for keyword in ["검색", "찾아", "추천", "어디"]):
            return UserIntent(
                intent_type=IntentType.SEARCH_REQUEST,
                confidence=0.7,
                required_agent="search_agent",
            )

        # 계획 관련 키워드
        if any(keyword in user_lower for keyword in ["계획", "일정", "plan", "만들어"]):
            return UserIntent(
                intent_type=IntentType.PLANNING_REQUEST,
                confidence=0.7,
                required_agent="planner_agent",
            )

        # 기본: 정보 수집
        return UserIntent(intent_type=IntentType.INFORMATION_COLLECTION, confidence=0.6)

    async def _handle_intent(
        self, intent: UserIntent, user_input: str, state: TravelPlanningState
    ) -> AgentResponse:
        """의도에 따른 적절한 핸들러 호출"""

        # 카카오톡 인증 코드 완료 처리
        if hasattr(state, "pending_auth_code") and state.pending_auth_code:
            auth_code = state.pending_auth_code
            delattr(state, "pending_auth_code")  # 사용 후 제거

            try:
                auth_result = await self.share_agent.complete_kakao_auth(auth_code)

                if auth_result["success"]:
                    # 인증 성공 후 바로 메시지 전송 시도
                    if state.travel_plan:
                        success = await self.share_agent.share_to_kakao(
                            state.travel_plan
                        )

                        if success:
                            return AgentResponse(
                                message=f"✅ {auth_result['message']}\n\n💬 여행 계획이 카카오톡으로 공유되었어요! 친구들과 함께 즐거운 여행 되세요! 🎉",
                                options=self._get_action_options(),
                                next_phase=TravelPhase.ACTION_SELECTION.value,
                            )
                        else:
                            return AgentResponse(
                                message=f"✅ {auth_result['message']}\n\n❌ 하지만 메시지 전송에 실패했어요. 다시 시도해주세요.",
                                options=[
                                    {"text": "🔄 다시 전송", "value": "share_kakao"},
                                    {
                                        "text": "🔙 뒤로 가기",
                                        "value": "back_to_actions",
                                    },
                                ],
                                next_phase=TravelPhase.ACTION_SELECTION.value,
                            )
                    else:
                        return AgentResponse(
                            message=f"✅ {auth_result['message']}\n\n이제 여행 계획을 완성하고 공유해보세요!",
                            options=self._get_action_options(),
                            next_phase=TravelPhase.ACTION_SELECTION.value,
                        )
                else:
                    return AgentResponse(
                        message=f"❌ 인증 실패: {auth_result['message']}\n\n다시 시도해주세요.",
                        options=[
                            {"text": "🔄 다시 인증", "value": "share_kakao"},
                            {"text": "🔙 뒤로 가기", "value": "back_to_actions"},
                        ],
                        next_phase=TravelPhase.SHARING.value,
                    )
            except Exception as e:
                return AgentResponse(
                    message=f"❌ 인증 처리 중 오류: {str(e)}",
                    options=self._get_share_options(),
                    next_phase=TravelPhase.SHARING.value,
                )

        # 특수 액션 처리
        if user_input in ["retry_kakao_auth", "share_kakao"]:
            return await self._handle_share_action(
                UserIntent(
                    intent_type=IntentType.SHARE_ACTION,
                    confidence=1.0,
                    agent_params={"type": "kakao"},
                ),
                state,
            )

        elif user_input == "share_menu":
            return await self._handle_share_action(
                UserIntent(
                    intent_type=IntentType.SHARE_ACTION,
                    confidence=1.0,
                    agent_params={"type": "menu"},
                ),
                state,
            )

        elif user_input == "copy_text":
            return await self._handle_share_action(
                UserIntent(
                    intent_type=IntentType.SHARE_ACTION,
                    confidence=1.0,
                    agent_params={"type": "text"},
                ),
                state,
            )

        elif user_input in ["back_to_actions", "back_to_main"]:
            return AgentResponse(
                message="어떤 작업을 하고 싶으세요?",
                options=self._get_action_options(),
                next_phase=TravelPhase.ACTION_SELECTION.value,
            )

        # 추출된 정보로 상태 업데이트
        self._update_state_with_extracted_info(state, intent.extracted_info)

        # 기본 의도 처리
        if intent.intent_type == IntentType.SEARCH_REQUEST:
            return await self._handle_search_request(intent, state)
        elif intent.intent_type == IntentType.PLANNING_REQUEST:
            return await self._handle_planning_request(intent, state)
        elif intent.intent_type == IntentType.CALENDAR_ACTION:
            return await self._handle_calendar_action(intent, state)
        elif intent.intent_type == IntentType.SHARE_ACTION:
            return await self._handle_share_action(intent, state)
        elif intent.intent_type == IntentType.INFORMATION_COLLECTION:
            return await self._handle_information_collection(user_input, state)
        elif intent.intent_type == IntentType.MODIFICATION_REQUEST:
            return await self._handle_modification_request(intent, state)
        elif intent.intent_type == IntentType.GENERAL_CONVERSATION:
            return await self._handle_general_conversation(user_input, state)
        else:
            return await self._handle_general_conversation(user_input, state)

    async def _handle_search_request(
        self, intent: UserIntent, state: TravelPlanningState
    ) -> AgentResponse:
        """검색 요청 처리"""

        try:
            # 여행지가 없으면 인기 여행지 검색
            if not state.user_preferences.destination:
                destinations = await self.search_agent.search_popular_destinations()
                state.available_destinations = destinations
                state.update_phase(TravelPhase.DESTINATION_SELECTION)

                return AgentResponse(
                    message="어디로 여행을 떠나고 싶으세요? 인기 여행지를 추천해드릴게요! 🗺️",
                    options=self._format_destination_options(destinations),
                    next_phase=TravelPhase.DESTINATION_SELECTION.value,
                )

            # 특정 여행지의 상세 정보 검색
            else:
                details = await self.search_agent.search_destination_details(
                    state.user_preferences.destination,
                    state.user_preferences.travel_style or "general",
                )

                state.destination_details = details

                return AgentResponse(
                    message=f"{state.user_preferences.destination}의 추천 장소들을 찾아봤어요! 🏞️\n\n가고 싶은 곳들을 선택해주세요:",
                    options=self._format_place_options(details.get("places", [])),
                    next_phase=TravelPhase.DETAILED_PLANNING.value,
                    metadata={"places": details.get("places", [])},
                )

        except Exception as e:
            return AgentResponse(
                message=f"검색 중 오류가 발생했어요: {str(e)}\n다시 시도해볼까요?",
                next_phase=state.current_phase.value,
            )

    async def _handle_planning_request(
        self, intent: UserIntent, state: TravelPlanningState
    ) -> AgentResponse:
        """여행 계획 생성 요청 처리"""

        print("DEBUG: _handle_planning_request called")
        # 필수 정보 확인
        if not state.is_ready_for_planning():
            missing = state.get_missing_preferences()
            print("DEBUG: is_ready_for_planning: False")
            print(f"DEBUG: Missing preferences in planning_request: {missing}")

            # 정보가 부족한 경우 정보 수집으로 리다이렉트
            return await self._handle_information_collection("정보 수집 필요", state)

        try:
            # 계획 생성 에이전트 호출
            travel_plan = await self.planner_agent.create_travel_plan(
                user_preferences=state.user_preferences,
                selected_places=state.selected_places,
                context=state.destination_details,
            )

            state.travel_plan = travel_plan
            state.update_phase(TravelPhase.ACTION_SELECTION)

            return AgentResponse(
                message=f"🎉 완벽한 {state.user_preferences.destination} 여행 계획이 완성되었어요!\n\n{self._format_plan_summary(travel_plan)}\n\n📋 **아래에서 상세 일정을 확인하세요!**\n\n이제 어떤 작업을 하고 싶으세요?",
                travel_plan=travel_plan,
                options=self._get_action_options(),
                next_phase=TravelPhase.ACTION_SELECTION.value,
            )

        except Exception as e:
            return AgentResponse(
                message=f"계획 생성 중 오류가 발생했어요: {str(e)}\n다시 시도해볼까요?",
                options=[{"text": "다시 시도", "value": "retry_planning"}],
                next_phase=TravelPhase.PLAN_GENERATION.value,
            )

    async def _handle_calendar_action(
        self, intent: UserIntent, state: TravelPlanningState
    ) -> AgentResponse:
        """캘린더 액션 처리"""

        if not state.travel_plan:
            return AgentResponse(
                message="먼저 여행 계획을 완성해야 캘린더에 등록할 수 있어요!",
                next_phase=state.current_phase.value,
            )

        try:
            action = intent.agent_params.get("action", "add")

            if action == "add":
                success = await self.calendar_agent.add_travel_plan_to_calendar(
                    state.travel_plan
                )

                if success:
                    return AgentResponse(
                        message="✅ 여행 계획이 구글 캘린더에 성공적으로 등록되었어요!\n\n📝 **등록된 내용:**\n• 전체 여행 일정이 개별 이벤트로 등록됨\n• 30분/10분 전 알림 설정 완료\n• 기존에 등록된 같은 여행 계획이 있었다면 자동으로 업데이트됨\n\n이제 구글 캘린더에서 여행 일정을 확인하실 수 있어요! 😊",
                        options=self._get_action_options(),
                        next_phase=TravelPhase.ACTION_SELECTION.value,
                    )
                else:
                    return AgentResponse(
                        message="❌ 캘린더 등록에 실패했어요.\n\n**가능한 원인:**\n• 구글 계정 연동 문제\n• credentials.json 파일 누락\n• 네트워크 연결 문제\n\n구글 캘린더 권한을 확인하고 다시 시도해주세요.",
                        options=[
                            {"text": "🔄 다시 시도", "value": "retry_calendar"},
                            {"text": "🏠 메인으로 돌아가기", "value": "back_to_main"},
                        ],
                        next_phase=TravelPhase.CALENDAR_MANAGEMENT.value,
                    )

            else:
                return AgentResponse(
                    message="캘린더 관련 다른 작업을 원하시나요?",
                    options=[
                        {"text": "📅 일정 등록", "value": "add_calendar"},
                        {"text": "🔍 일정 조회", "value": "view_calendar"},
                        {"text": "✏️ 일정 수정", "value": "edit_calendar"},
                        {"text": "🔙 뒤로 가기", "value": "back"},
                    ],
                    next_phase=TravelPhase.CALENDAR_MANAGEMENT.value,
                )

        except Exception as e:
            return AgentResponse(
                message=f"캘린더 작업 중 오류: {str(e)}",
                next_phase=TravelPhase.ACTION_SELECTION.value,
            )

    async def _handle_share_action(
        self, intent: UserIntent, state: TravelPlanningState
    ) -> AgentResponse:
        """공유 액션 처리"""

        if not state.travel_plan:
            return AgentResponse(
                message="공유할 여행 계획이 없어요! 먼저 계획을 완성해주세요.",
                next_phase=state.current_phase.value,
            )

        try:
            share_type = intent.agent_params.get("type", "menu")

            if share_type == "kakao":
                # 카카오톡 인증 상태 확인
                if not self.share_agent.is_kakao_authenticated():
                    # 카카오톡 상태 확인
                    kakao_status = self.share_agent.get_kakao_status()

                    if not kakao_status["api_key_configured"]:
                        return AgentResponse(
                            message="❌ 카카오톡 공유를 위해서는 KAKAO_REST_API_KEY 설정이 필요해요.\n\n.env 파일에 KAKAO_REST_API_KEY를 추가하고 앱을 다시 시작해주세요.",
                            options=self._get_share_options(),
                            next_phase=TravelPhase.SHARING.value,
                        )

                    # 인증 시작
                    auth_result = await self.share_agent.authenticate_kakao()

                    if auth_result["auth_required"]:
                        instructions_text = "\n".join(
                            [
                                f"{i + 1}. {instruction}"
                                for i, instruction in enumerate(
                                    auth_result["instructions"]
                                )
                            ]
                        )

                        return AgentResponse(
                            message=f"🔐 카카오톡 인증이 필요해요!\n\n**인증 URL:**\n{auth_result['auth_url']}\n\n**진행 방법:**\n{instructions_text}\n\n인증 완료 후 '인증코드: [복사한코드]' 형태로 입력해주세요.",
                            options=[
                                {"text": "🔙 다른 공유 방법", "value": "share_menu"},
                                {
                                    "text": "🏠 메인으로 돌아가기",
                                    "value": "back_to_actions",
                                },
                            ],
                            next_phase=TravelPhase.SHARING.value,
                            metadata={
                                "auth_url": auth_result["auth_url"],
                                "waiting_for_auth": True,
                            },
                        )
                    else:
                        return AgentResponse(
                            message=f"❌ 카카오톡 인증 준비 실패: {auth_result['message']}",
                            options=self._get_share_options(),
                            next_phase=TravelPhase.SHARING.value,
                        )

                # 인증이 완료된 상태에서 메시지 전송
                success = await self.share_agent.share_to_kakao(state.travel_plan)

                if success:
                    return AgentResponse(
                        message="💬 여행 계획이 카카오톡으로 공유되었어요! 친구들과 함께 즐거운 여행 되세요! 🎉",
                        options=self._get_action_options(),
                        next_phase=TravelPhase.ACTION_SELECTION.value,
                    )
                else:
                    return AgentResponse(
                        message="❌ 카카오톡 공유에 실패했어요. Access Token이 만료되었거나 권한이 부족할 수 있어요.\n\n다시 인증을 시도해보시거나 다른 방법을 선택해주세요.",
                        options=[
                            {"text": "🔄 다시 인증하기", "value": "retry_kakao_auth"},
                            {"text": "📋 텍스트로 복사", "value": "copy_text"},
                            {"text": "🔙 뒤로 가기", "value": "back_to_actions"},
                        ],
                        next_phase=TravelPhase.SHARING.value,
                    )

            elif share_type == "text":
                formatted_text = self.share_agent.format_plan_as_text(state.travel_plan)

                return AgentResponse(
                    message="📋 여행 계획을 텍스트로 정리했어요! 복사해서 사용하세요:",
                    metadata={"formatted_text": formatted_text, "show_text_area": True},
                    options=[{"text": "🔙 뒤로 가기", "value": "back_to_actions"}],
                    next_phase=TravelPhase.SHARING.value,
                )

            else:
                return AgentResponse(
                    message="어떤 방식으로 공유하고 싶으세요?",
                    options=self._get_share_options(),
                    next_phase=TravelPhase.SHARING.value,
                )

        except Exception as e:
            return AgentResponse(
                message=f"공유 중 오류가 발생했어요: {str(e)}",
                options=self._get_share_options(),
                next_phase=TravelPhase.SHARING.value,
            )

    async def _handle_information_collection(
        self, user_input: str, state: TravelPlanningState
    ) -> AgentResponse:
        """정보 수집 단계 처리"""

        # 현재 부족한 정보 확인
        missing_prefs = state.get_missing_preferences()
        print(f"DEBUG: Current destination: {state.user_preferences.destination}")
        print(f"DEBUG: Current travel_style: {state.user_preferences.travel_style}")
        print(f"DEBUG: Current duration: {state.user_preferences.duration}")
        print(f"DEBUG: Current departure_date: {state.user_preferences.departure_date}")
        print(f"DEBUG: Missing preferences: {missing_prefs}")

        if not missing_prefs:
            # 모든 정보 수집 완료 - 계획 생성으로 이동
            state.update_phase(TravelPhase.PLAN_GENERATION)
            return await self._handle_planning_request(
                UserIntent(intent_type=IntentType.PLANNING_REQUEST, confidence=1.0),
                state,
            )

        # 첫 번째 누락 정보에 대한 질문
        next_info = missing_prefs[0]

        if next_info == "destination":
            # 여행지 검색 및 선택지 제공
            return await self._handle_search_request(
                UserIntent(intent_type=IntentType.SEARCH_REQUEST, confidence=1.0), state
            )

        elif next_info == "travel_style":
            state.update_phase(TravelPhase.PREFERENCE_COLLECTION)
            return AgentResponse(
                message="어떤 스타일의 여행을 원하세요? 🎨",
                options=self._get_travel_style_options(),
                next_phase=TravelPhase.PREFERENCE_COLLECTION.value,
            )

        elif next_info == "duration":
            state.update_phase(TravelPhase.PREFERENCE_COLLECTION)
            return AgentResponse(
                message="며칠 정도 여행하실 건가요? ⏰",
                options=self._get_duration_options(),
                next_phase=TravelPhase.PREFERENCE_COLLECTION.value,
            )

        elif next_info == "departure_date":
            state.update_phase(TravelPhase.PREFERENCE_COLLECTION)
            return AgentResponse(
                message="언제 출발하실 예정인가요? 📅",
                options=self._get_date_options(),
                next_phase=TravelPhase.PREFERENCE_COLLECTION.value,
            )

        elif next_info == "budget":
            state.update_phase(TravelPhase.PREFERENCE_COLLECTION)
            return AgentResponse(
                message="예산은 어느 정도 생각하고 계세요? 💰",
                options=self._get_budget_options(),
                next_phase=TravelPhase.PREFERENCE_COLLECTION.value,
            )

        elif next_info == "companion_type":
            state.update_phase(TravelPhase.PREFERENCE_COLLECTION)
            return AgentResponse(
                message="누구와 함께 가시나요? 👥",
                options=self._get_companion_options(),
                next_phase=TravelPhase.PREFERENCE_COLLECTION.value,
            )

        # 예상치 못한 경우를 위한 기본 응답
        return AgentResponse(
            message="여행 계획을 위해 몇 가지 정보가 더 필요해요. 어떤 것부터 정해볼까요?",
            options=self._get_travel_style_options(),
            next_phase=TravelPhase.PREFERENCE_COLLECTION.value,
        )

    async def _handle_modification_request(
        self, intent: UserIntent, state: TravelPlanningState
    ) -> AgentResponse:
        """수정 요청 처리"""

        modification_type = intent.agent_params.get("type", "general")

        if modification_type == "destination":
            state.user_preferences.destination = None
            state.available_destinations = []
            state.update_phase(TravelPhase.DESTINATION_SELECTION)

            return await self._handle_search_request(
                UserIntent(intent_type=IntentType.SEARCH_REQUEST, confidence=1.0), state
            )

        elif modification_type == "plan":
            if state.travel_plan:
                return AgentResponse(
                    message="어떤 부분을 수정하고 싶으세요?",
                    options=[
                        {"text": "🗺️ 여행지 변경", "value": "change_destination"},
                        {"text": "🎨 여행 스타일 변경", "value": "change_style"},
                        {"text": "⏰ 기간 변경", "value": "change_duration"},
                        {"text": "💰 예산 변경", "value": "change_budget"},
                        {"text": "🔄 전체 다시 시작", "value": "restart_all"},
                    ],
                    next_phase=TravelPhase.PREFERENCE_COLLECTION.value,
                )
            else:
                return AgentResponse(
                    message="수정할 계획이 없어요. 먼저 여행 계획을 만들어볼까요?",
                    next_phase=TravelPhase.GREETING.value,
                )

        else:
            return AgentResponse(
                message="무엇을 수정하고 싶으신지 구체적으로 말씀해주세요!",
                next_phase=state.current_phase.value,
            )

    async def _handle_general_conversation(
        self, user_input: str, state: TravelPlanningState
    ) -> AgentResponse:
        """일반 대화 처리"""

        # LLM을 사용한 자연스러운 응답 생성
        conversation_prompt = f"""
{self.system_prompt}

현재 상황:
- 대화 단계: {state.current_phase.value if state.current_phase else "greeting"}
- 수집된 정보: {json.dumps(state.user_preferences.to_dict(), ensure_ascii=False)}
- 여행 계획 존재: {"예" if state.travel_plan else "아니오"}

최근 대화:
{chr(10).join([f"- {msg.role}: {msg.content}" for msg in state.get_conversation_context(3)])}

사용자 입력: "{user_input}"

친근하고 도움이 되는 응답을 해주세요. 필요하다면 다음 단계를 안내해주세요.
"""

        try:
            messages = [
                SystemMessage(content="당신은 친근한 여행 플래너 AI입니다."),
                HumanMessage(content=conversation_prompt),
            ]

            response = await self.llm.agenerate([messages])
            ai_message = response.generations[0][0].text.strip()

            return AgentResponse(
                message=ai_message,
                next_phase=state.current_phase.value
                if state.current_phase
                else TravelPhase.GREETING.value,
            )

        except Exception:
            return AgentResponse(
                message="죄송해요, 다시 한 번 말씀해주시겠어요? 😅",
                next_phase=state.current_phase.value
                if state.current_phase
                else TravelPhase.GREETING.value,
            )

    async def _handle_general_conversation_streaming(
        self, user_input: str, state: TravelPlanningState
    ) -> AsyncGenerator[str, None]:
        """일반 대화 처리 - 스트리밍 버전"""

        conversation_prompt = f"""
{self.system_prompt}

현재 상황:
- 대화 단계: {state.current_phase.value if state.current_phase else "greeting"}
- 수집된 정보: {json.dumps(state.user_preferences.to_dict(), ensure_ascii=False)}
- 여행 계획 존재: {"예" if state.travel_plan else "아니오"}

최근 대화:
{chr(10).join([f"- {msg.role}: {msg.content}" for msg in state.get_conversation_context(3)])}

사용자 입력: "{user_input}"

친근하고 도움이 되는 응답을 해주세요. 필요하다면 다음 단계를 안내해주세요.
"""

        try:
            messages = [
                SystemMessage(content="당신은 친근한 여행 플래너 AI입니다."),
                HumanMessage(content=conversation_prompt),
            ]

            # 스트리밍 콜백 핸들러 초기화
            self.streaming_handler.clear()

            # 스트리밍으로 응답 생성
            async for chunk in self.llm.astream(
                messages, callbacks=[self.streaming_handler]
            ):
                if chunk.content:
                    yield chunk.content

        except Exception:
            yield "죄송해요, 다시 한 번 말씀해주시겠어요? 😅"

    async def _handle_information_collection_streaming(
        self, user_input: str, state: TravelPlanningState
    ) -> AsyncGenerator[str, None]:
        """정보 수집 처리 - 스트리밍 버전"""

        # 기본 정보 수집 프롬프트
        collection_prompt = f"""
{self.system_prompt}

현재 수집된 정보:
- 여행지: {state.user_preferences.destination or "미정"}
- 여행 스타일: {state.user_preferences.travel_style or "미정"}
- 기간: {state.user_preferences.duration or "미정"}
- 출발일: {state.user_preferences.departure_date or "미정"}
- 예산: {state.user_preferences.budget or "미정"}
- 동행자: {state.user_preferences.companion_type or "미정"}

사용자 입력: "{user_input}"

사용자의 입력을 바탕으로 여행 계획에 필요한 정보를 수집해주세요.
부족한 정보가 있다면 자연스럽게 물어보세요.
"""

        try:
            messages = [
                SystemMessage(content="당신은 여행 정보 수집 전문가입니다."),
                HumanMessage(content=collection_prompt),
            ]

            # 스트리밍 콜백 핸들러 초기화
            self.streaming_handler.clear()

            # 스트리밍으로 응답 생성
            async for chunk in self.llm.astream(
                messages, callbacks=[self.streaming_handler]
            ):
                if chunk.content:
                    yield chunk.content

        except Exception:
            yield "정보를 처리하는 중 문제가 발생했어요. 다시 시도해주세요."

    # 유틸리티 메서드들
    def _update_state_with_extracted_info(
        self, state: TravelPlanningState, extracted_info: Dict[str, Any]
    ):
        """추출된 정보로 상태 업데이트"""

        for key, value in extracted_info.items():
            if value and hasattr(state.user_preferences, key):
                # duration 필드는 특별히 처리
                if key == "duration":
                    # duration이 딕셔너리가 아닌 경우 무시 (옵션 선택을 통해서만 설정)
                    if isinstance(value, dict):
                        setattr(state.user_preferences, key, value)
                    # duration이 문자열인 경우 무시하고 기존 값 유지
                else:
                    setattr(state.user_preferences, key, value)

        state.updated_at = datetime.now()

    def _format_destination_options(self, destinations: List) -> List[Dict[str, Any]]:
        """여행지 옵션 포맷팅"""
        options = []

        for i, dest in enumerate(destinations[:5], 1):
            options.append(
                {
                    "text": f"{i}. {dest.name} ({dest.region})",
                    "value": f"dest_{i}",
                    "description": getattr(dest, "description", "")[:50] + "..."
                    if hasattr(dest, "description")
                    else "",
                }
            )

        options.append(
            {
                "text": "✏️ 직접 입력하기",
                "value": "custom_destination",
                "description": "원하는 여행지를 직접 말씀해주세요",
            }
        )

        return options

    def _format_place_options(self, places: List[Dict]) -> List[Dict[str, Any]]:
        """장소 옵션 포맷팅"""
        options = []

        for i, place in enumerate(places[:8], 1):
            options.append(
                {
                    "text": f"{i}. {place.get('name', '알 수 없는 장소')}",
                    "value": f"place_{i}",
                    "description": place.get("description", "")[:50] + "..."
                    if place.get("description")
                    else "",
                }
            )

        return options

    def _get_travel_style_options(self) -> List[Dict[str, Any]]:
        """여행 스타일 옵션"""
        from models.state_models import TRAVEL_STYLES

        return [
            {
                "text": f"{info['icon']} {info['name']}",
                "value": key,
                "description": info["desc"],
            }
            for key, info in TRAVEL_STYLES.items()
        ]

    def _get_duration_options(self) -> List[Dict[str, Any]]:
        """기간 옵션"""
        return [
            {"text": "당일치기", "value": "day_trip", "data": {"days": 1, "nights": 0}},
            {"text": "1박 2일", "value": "1n2d", "data": {"days": 2, "nights": 1}},
            {"text": "2박 3일", "value": "2n3d", "data": {"days": 3, "nights": 2}},
            {"text": "3박 4일", "value": "3n4d", "data": {"days": 4, "nights": 3}},
            {"text": "4박 5일", "value": "4n5d", "data": {"days": 5, "nights": 4}},
            {
                "text": "일주일 이상",
                "value": "week_plus",
                "data": {"days": 7, "nights": 6},
            },
        ]

    def _get_date_options(self) -> List[Dict[str, Any]]:
        """날짜 옵션"""
        from datetime import datetime, timedelta

        today = datetime.now()
        options = []

        # 이번 주 날짜들 (오늘부터 일요일까지, 최대 4개)
        days_until_sunday = 6 - today.weekday()  # 일요일까지 남은 일수

        # 이번 주 남은 날짜들 추가 (최대 4개)
        for i in range(min(4, days_until_sunday + 1)):
            target_date = today + timedelta(days=i)
            if i == 0:
                day_name = "오늘"
            elif i == 1:
                day_name = "내일"
            else:
                day_name = target_date.strftime("%A")
                korean_days = {
                    "Monday": "월요일",
                    "Tuesday": "화요일",
                    "Wednesday": "수요일",
                    "Thursday": "목요일",
                    "Friday": "금요일",
                    "Saturday": "토요일",
                    "Sunday": "일요일",
                }
                day_name = korean_days.get(day_name, day_name)

            options.append(
                {
                    "text": f"{day_name} ({target_date.strftime('%m/%d')})",
                    "value": target_date.strftime("%Y-%m-%d"),
                }
            )

        # 다음 주말 (토요일)
        if today.weekday() >= 5:  # 토요일이나 일요일인 경우
            next_weekend = today + timedelta(
                days=(12 - today.weekday())
            )  # 다음 주 토요일
        else:  # 월~금인 경우 다음 주 토요일
            days_to_next_saturday = 5 - today.weekday() + 7
            next_weekend = today + timedelta(days=days_to_next_saturday)

        options.append(
            {
                "text": f"다음 주말 ({next_weekend.strftime('%m/%d')})",
                "value": "next_weekend",
            }
        )

        # 다음 달
        next_month = today + timedelta(days=30)
        options.append(
            {
                "text": f"다음 달 ({next_month.strftime('%m/%d')})",
                "value": "next_month",
            }
        )

        # 직접 날짜 선택
        options.append({"text": "직접 날짜 선택", "value": "custom_date"})

        return options

    def _get_budget_options(self) -> List[Dict[str, Any]]:
        """예산 옵션"""
        from models.state_models import BUDGET_RANGES

        return [
            {"text": f"{info['icon']} {info['name']} ({info['range']})", "value": key}
            for key, info in BUDGET_RANGES.items()
        ]

    def _get_companion_options(self) -> List[Dict[str, Any]]:
        """동행자 옵션"""
        from models.state_models import COMPANION_TYPES

        return [
            {"text": f"{info['icon']} {info['name']}", "value": key}
            for key, info in COMPANION_TYPES.items()
        ]

    def _get_action_options(self) -> List[Dict[str, Any]]:
        """액션 옵션"""
        return [
            {
                "text": "📅 캘린더에 등록하기",
                "value": "add_to_calendar",
                "description": "구글 캘린더에 여행 일정 등록",
            },
            {
                "text": "💬 카카오톡으로 공유하기",
                "value": "share_kakao",
                "description": "친구들과 여행 계획 공유",
            },
            {
                "text": "📋 텍스트로 복사하기",
                "value": "copy_text",
                "description": "텍스트 형태로 계획서 복사",
            },
            {
                "text": "✏️ 계획 수정하기",
                "value": "modify_plan",
                "description": "여행 계획 일부 수정",
            },
            {
                "text": "🔄 새로운 계획 시작",
                "value": "new_plan",
                "description": "처음부터 새로운 여행 계획",
            },
        ]

    def _get_share_options(self) -> List[Dict[str, Any]]:
        """공유 옵션"""
        return [
            {"text": "💬 카카오톡", "value": "share_kakao"},
            {"text": "📋 텍스트 복사", "value": "copy_text"},
            {"text": "📧 이메일", "value": "share_email"},
            {"text": "🔙 뒤로 가기", "value": "back_to_actions"},
        ]

    def _format_plan_summary(self, travel_plan: TravelPlan) -> str:
        """여행 계획 요약 포맷팅"""
        if not travel_plan:
            return "계획 정보를 불러올 수 없습니다."

        summary = f"📍 **{travel_plan.destination}** "
        if travel_plan.user_preferences.duration:
            duration = travel_plan.user_preferences.duration
            # duration이 딕셔너리인지 확인
            if isinstance(duration, dict):
                duration_text = (
                    duration.get("name")
                    if duration.get("name")
                    else f"{duration.get('days', '?')}일"
                )
            else:
                # duration이 문자열인 경우 처리
                duration_text = str(duration)
            summary += f"{duration_text}\n"

        if travel_plan.user_preferences.departure_date:
            summary += f"📅 **출발일**: {travel_plan.user_preferences.departure_date}\n"

        if travel_plan.total_budget > 0:
            summary += f"💰 **예상 비용**: {travel_plan.total_budget:,}원\n"

        if travel_plan.schedule:
            summary += f"\n**주요 일정** ({len(travel_plan.schedule)}일):\n"
            for i, day in enumerate(travel_plan.schedule[:3], 1):  # 최대 3일까지 표시
                event_count = len(day.events)
                summary += f"• {i}일차: {event_count}개 활동 예정\n"

        return summary.strip()
