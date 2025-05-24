import asyncio
import os
import uuid
from typing import Any, Dict, List, Optional

import streamlit as st
from dotenv import load_dotenv

from agents.supervisor import SupervisorAgent
from models.state_models import TravelPhase, TravelPlanningState

load_dotenv()

# Page configuration
st.set_page_config(
    page_title="AI 여행 플래너 🧳",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Custom CSS
def load_css():
    st.markdown(
        """
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #2E86AB;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        border-left: 4px solid #2E86AB;
        background-color: #f8f9fa;
        color: #1a1a1a;
    }
    
    .user-message {
        background-color: #e3f2fd;
        border-left-color: #1976d2;
        text-align: left;
        color: #1a1a1a;
    }
    
    .ai-message {
        background-color: #f1f8e9;
        border-left-color: #388e3c;
        color: #1a1a1a;
    }
    
    .option-button {
        margin: 0.25rem;
        padding: 0.5rem 1rem;
        border: 1px solid #2E86AB;
        border-radius: 0.5rem;
        background-color: white;
        cursor: pointer;
        transition: all 0.3s;
    }
    
    .option-button:hover {
        background-color: #2E86AB;
        color: white;
    }
    
    .sidebar-section {
        background-color: #f5f5f5;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    
    .progress-indicator {
        display: flex;
        justify-content: space-between;
        margin-bottom: 2rem;
    }
    
    .progress-step {
        padding: 0.5rem 1rem;
        border-radius: 0.25rem;
        background-color: #e0e0e0;
        color: #666;
        font-size: 0.8rem;
    }
    
    .progress-step.active {
        background-color: #2E86AB;
        color: white;
    }
    
    .progress-step.completed {
        background-color: #4caf50;
        color: white;
    }
    
    .text-area-container {
        background-color: #f8f9fa;
        border: 1px solid #ddd;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
        max-height: 300px;
        overflow-y: auto;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )


def initialize_session():
    """세션 상태 초기화"""
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    if "supervisor" not in st.session_state:
        st.session_state.supervisor = SupervisorAgent()

    if "travel_state" not in st.session_state:
        st.session_state.travel_state = TravelPlanningState(
            session_id=st.session_state.session_id
        )


def format_duration_safely(duration) -> str:
    """duration을 안전하게 포맷팅하는 유틸리티 함수"""
    if not duration:
        return "미정"

    if isinstance(duration, dict):
        return duration.get("name", f"{duration.get('days', '?')}일")
    else:
        return str(duration)


def render_sidebar():
    """사이드바 렌더링"""
    with st.sidebar:
        st.markdown("### 🗺️ 여행 계획 현황")

        state = st.session_state.travel_state

        # 현재 수집된 정보 표시
        prefs = state.user_preferences

        if prefs.destination:
            st.markdown(f"**📍 여행지:** {prefs.destination}")

        if prefs.travel_style:
            from models.state_models import TRAVEL_STYLES

            style_name = TRAVEL_STYLES.get(prefs.travel_style, {}).get(
                "name", prefs.travel_style
            )
            st.markdown(f"**🎨 스타일:** {style_name}")

        if prefs.duration:
            duration_name = format_duration_safely(prefs.duration)
            st.markdown(f"**⏰ 기간:** {duration_name}")

        if prefs.departure_date:
            st.markdown(f"**📅 출발일:** {prefs.departure_date}")

        if prefs.budget:
            from models.state_models import BUDGET_RANGES

            budget_name = BUDGET_RANGES.get(prefs.budget, {}).get("name", prefs.budget)
            st.markdown(f"**💰 예산:** {budget_name}")

        if prefs.companion_type:
            from models.state_models import COMPANION_TYPES

            companion_name = COMPANION_TYPES.get(prefs.companion_type, {}).get(
                "name", prefs.companion_type
            )
            st.markdown(f"**👥 동행:** {companion_name}")

        st.markdown("---")

        # 여행 계획 요약
        if state.travel_plan:
            st.markdown("### 📋 완성된 계획")

            plan = state.travel_plan
            st.markdown(f"**제목:** {plan.title}")

            if plan.schedule:
                st.markdown(f"**일정:** {len(plan.schedule)}일")
                for i, day in enumerate(plan.schedule[:3], 1):
                    st.markdown(f"• {i}일차: {len(day.events)}개 활동")

            if plan.total_budget > 0:
                st.markdown(f"**예상 비용:** {plan.total_budget:,}원")

        st.markdown("---")

        # 빠른 액션 버튼
        st.markdown("### 🛠️ 빠른 작업")

        if st.button("🗑️ 대화 초기화", use_container_width=True):
            # 상태 초기화
            st.session_state.travel_state = TravelPlanningState(
                session_id=st.session_state.session_id
            )
            st.rerun()

        if state.travel_plan:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📅", help="캘린더 등록", use_container_width=True):
                    st.session_state.quick_action = "calendar"
                    st.rerun()

            with col2:
                if st.button("💬", help="공유하기", use_container_width=True):
                    st.session_state.quick_action = "share"
                    st.rerun()

        # 개발자 정보
        st.markdown("---")
        st.markdown("### ℹ️ 시스템 정보")
        st.markdown(f"**세션 ID:** {st.session_state.session_id[:8]}...")
        st.markdown(
            f"**현재 단계:** {state.current_phase.value if state.current_phase else 'None'}"
        )
        st.markdown(f"**메시지 수:** {len(state.conversation_history)}")


def render_option_buttons(options: List[Dict[str, Any]]) -> Optional[str]:
    """옵션 버튼들 렌더링 + 직접 입력 모드 지원"""
    if not options:
        return None

    selected_option = None

    # 현재 시간을 포함한 고유 식별자 생성
    button_session_key = f"options_{len(options)}_{hash(str(options))}"
    custom_input_key = f"custom_input_{button_session_key}"

    # 세션 상태 초기화
    if button_session_key not in st.session_state:
        st.session_state[button_session_key] = None
    if custom_input_key not in st.session_state:
        st.session_state[custom_input_key] = False

    # 직접 입력 모드 토글 버튼
    col_toggle, col_spacer = st.columns([2, 3])
    with col_toggle:
        if st.button(
            "✏️ 직접 입력" if not st.session_state[custom_input_key] else "📋 옵션 선택",
            key=f"toggle_{custom_input_key}",
            help="직접 입력 모드로 전환하거나 옵션 선택 모드로 돌아갑니다",
        ):
            st.session_state[custom_input_key] = not st.session_state[custom_input_key]
            st.rerun()

    st.markdown("---")

    # 직접 입력 모드
    if st.session_state[custom_input_key]:
        st.markdown("💡 **직접 입력 모드 활성화** ✏️")
        st.markdown("---")

        # 입력 가이드
        st.markdown("### 📝 입력 가이드")
        st.markdown("""
        **여행지**: "제주도 여행", "부산 가고 싶어"  
        **스타일**: "자연 힐링 스타일", "맛집 투어로"  
        **기간**: "2박 3일", "당일치기로"  
        **날짜**: "2025-06-10", "다음 주말에"  
        **예산**: "가성비로", "럭셔리하게"  
        **동행**: "혼자", "가족과 함께"  
        """)

        # 참고용 옵션들을 비활성화된 상태로 표시
        with st.expander("💭 참고 옵션들", expanded=False):
            st.markdown("**버튼으로 선택 가능한 옵션들:**")
            for option in options:
                button_text = option.get("text", str(option.get("value", "Option")))
                description = option.get("description", "")
                st.markdown(
                    f"• {button_text}" + (f" - {description}" if description else "")
                )

        st.markdown("⬇️ **아래 입력창에 자유롭게 입력하세요**")

        # 입력창은 main에서 처리되므로 None 반환
        return None

    # 옵션 버튼 모드
    else:
        st.markdown(
            "📋 **옵션 선택** - 원하는 항목을 클릭하거나 위에서 직접 입력 모드로 전환하세요:"
        )

        # 옵션을 최대 3개씩 배치
        for i in range(0, len(options), 3):
            cols = st.columns(min(3, len(options) - i))

            for j, option in enumerate(options[i : i + 3]):
                with cols[j]:
                    button_text = option.get("text", str(option.get("value", "Option")))
                    # 더 안전한 키 생성
                    option_value = str(option.get("value", f"option_{i}_{j}"))
                    button_key = f"{button_session_key}_{i}_{j}_{option_value}"

                    if st.button(
                        button_text,
                        key=button_key,
                        use_container_width=True,
                        help=option.get("description", ""),
                    ):
                        selected_option = option.get("value", button_text)
                        # 버튼 클릭 상태를 세션에 저장
                        st.session_state[button_session_key] = selected_option
                        break

            if selected_option:
                break

        # 저장된 클릭 상태 확인
        if st.session_state.get(button_session_key) and not selected_option:
            selected_option = st.session_state[button_session_key]
            # 사용한 후 정리
            st.session_state[button_session_key] = None

    return selected_option


def render_travel_plan_display(travel_plan):
    """여행 계획 상세 표시"""
    if not travel_plan:
        return

    st.markdown("### 🗓️ 상세 여행 계획")

    # 기본 정보
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("📍 목적지", travel_plan.destination)

    with col2:
        if travel_plan.user_preferences.duration:
            duration = travel_plan.user_preferences.duration
            duration_text = format_duration_safely(duration)
            st.metric("⏰ 기간", duration_text)

    with col3:
        if travel_plan.total_budget > 0:
            st.metric("💰 예상 비용", f"{travel_plan.total_budget:,}원")

    # 일정 표시
    if travel_plan.schedule:
        st.markdown("#### 📅 일정표")

        for day_idx, day_schedule in enumerate(travel_plan.schedule, 1):
            with st.expander(
                f"📅 {day_idx}일차 - {day_schedule.date}", expanded=(day_idx == 1)
            ):
                if day_schedule.events:
                    for event in day_schedule.events:
                        event_html = f"""
                        <div style="
                            border-left: 3px solid #2E86AB;
                            padding-left: 1rem;
                            margin-bottom: 1rem;
                            background-color: #f8f9fa;
                            border-radius: 0 0.5rem 0.5rem 0;
                            padding: 0.5rem 1rem;
                        ">
                            <strong>{event.time}</strong> - {event.activity}<br>
                            <small>📍 {event.location}</small>
                            {f"<br><small>💰 {event.estimated_cost:,}원</small>" if event.estimated_cost else ""}
                            {f"<br><small>📝 {event.notes}</small>" if event.notes else ""}
                        </div>
                        """
                        st.markdown(event_html, unsafe_allow_html=True)

                # 일차별 요약
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**활동 수:** {len(day_schedule.events)}개")
                with col2:
                    if day_schedule.total_cost > 0:
                        st.markdown(f"**일일 비용:** {day_schedule.total_cost:,}원")


def render_text_area_response(formatted_text: str):
    """텍스트 영역 응답 렌더링"""
    st.markdown("### 📋 여행 계획서")

    # 복사 가능한 텍스트 영역
    st.text_area(
        "아래 내용을 복사해서 사용하세요:",
        value=formatted_text,
        height=400,
        key="plan_text_area",
    )

    # 복사 버튼 (JavaScript 사용)
    copy_button_html = """
    <button onclick="
        navigator.clipboard.writeText(document.getElementById('plan_text_area').value)
        .then(() => alert('복사되었습니다!'))
        .catch(() => alert('복사에 실패했습니다.'));
    " style="
        background-color: #2E86AB;
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 0.25rem;
        cursor: pointer;
        margin-top: 0.5rem;
    ">
        📋 클립보드에 복사
    </button>
    """
    st.markdown(copy_button_html, unsafe_allow_html=True)


def render_chat_interface():
    """메인 채팅 인터페이스"""
    st.markdown(
        '<h1 class="main-header">AI 여행 플래너 🧳</h1>', unsafe_allow_html=True
    )

    state = st.session_state.travel_state

    # 빠른 액션 처리
    if hasattr(st.session_state, "quick_action"):
        quick_action = st.session_state.quick_action
        del st.session_state.quick_action

        if quick_action == "calendar":
            st.session_state.pending_user_input = "캘린더에 등록해줘"
        elif quick_action == "share":
            st.session_state.pending_user_input = "카카오톡으로 공유해줘"

    # 대화 히스토리 표시
    chat_container = st.container()

    with chat_container:
        for message in state.conversation_history:
            if message.role == "user":
                st.markdown(
                    f"""
                <div class="chat-message user-message">
                    <strong>👤 나:</strong> {message.content}
                </div>
                """,
                    unsafe_allow_html=True,
                )

            elif message.role == "assistant":
                st.markdown(
                    f"""
                <div class="chat-message ai-message">
                    <strong>🤖 AI 플래너:</strong> {message.content}
                </div>
                """,
                    unsafe_allow_html=True,
                )

                # 텍스트 영역 표시 (공유 기능)
                if message.metadata and message.metadata.get("show_text_area"):
                    formatted_text = message.metadata.get("formatted_text", "")
                    if formatted_text:
                        render_text_area_response(formatted_text)

    # 여행 계획 표시 - 계획이 완성되면 항상 표시
    if state.travel_plan:
        render_travel_plan_display(state.travel_plan)

    # 대기 중인 입력 처리
    if hasattr(st.session_state, "pending_user_input"):
        user_input = st.session_state.pending_user_input
        del st.session_state.pending_user_input

        # 즉시 처리
        process_user_message(user_input)
        st.rerun()

    # 옵션 버튼 표시 및 처리
    if (
        hasattr(st.session_state, "pending_options")
        and st.session_state.pending_options
    ):
        options = st.session_state.pending_options

        selected = render_option_buttons(options)
        if selected:
            # 옵션이 선택되면 pending_options 삭제하고 처리
            del st.session_state.pending_options
            process_user_message(selected)
            st.rerun()

    # 사용자 입력
    user_input = st.chat_input("무엇을 도와드릴까요?")

    if user_input:
        # 새로운 사용자 입력이 있으면 기존 옵션 제거
        if hasattr(st.session_state, "pending_options"):
            del st.session_state.pending_options
        process_user_message(user_input)
        st.rerun()


def process_user_message(user_input: str):
    """사용자 메시지 처리"""
    state = st.session_state.travel_state
    supervisor = st.session_state.supervisor

    try:
        # 현재 상황에 맞는 스피너 메시지 결정
        spinner_message = get_spinner_message(user_input, state)

        # Supervisor Agent를 통해 메시지 처리
        with st.spinner(spinner_message):
            response = asyncio.run(supervisor.process_message(user_input, state))

        # 응답 메시지가 있으면 표시를 위해 잠시 대기
        if response.message:
            # 메시지가 이미 대화 기록에 추가되었으므로 별도 처리 불필요
            pass

        # 옵션이 있는 경우 다음 렌더링에서 표시
        if response.options:
            st.session_state.pending_options = response.options

        # 여행 계획이 업데이트된 경우
        if response.travel_plan:
            state.travel_plan = response.travel_plan

        # 단계 업데이트
        if response.next_phase:
            try:
                new_phase = TravelPhase(response.next_phase)
                state.update_phase(new_phase)
            except ValueError:
                pass  # 잘못된 단계명인 경우 무시

    except Exception as e:
        st.error(f"오류가 발생했습니다: {str(e)}")

        # 에러 메시지를 대화에 추가
        error_msg = "죄송합니다. 처리 중 문제가 발생했어요. 다시 시도해주세요. 😅"
        state.add_message("assistant", error_msg)


def get_spinner_message(user_input: str, state: TravelPlanningState) -> str:
    """사용자 입력과 현재 상태에 따른 적절한 스피너 메시지 반환"""

    user_lower = user_input.lower()
    current_phase = state.current_phase

    # 여행지 이름이 포함된 경우
    travel_destinations = [
        "제주",
        "부산",
        "경주",
        "강릉",
        "여수",
        "전주",
        "서울",
        "인천",
        "대구",
        "광주",
        "대전",
    ]
    mentioned_destination = None
    for dest in travel_destinations:
        if dest in user_input:
            mentioned_destination = dest
            break

    # 구체적인 작업별 메시지
    if any(keyword in user_lower for keyword in ["검색", "찾아", "추천", "어디"]):
        if mentioned_destination:
            return f"🔍 {mentioned_destination} 여행 정보를 검색하고 있어요..."
        return "🔍 맞춤 여행지를 검색하고 있어요..."

    elif any(keyword in user_lower for keyword in ["계획", "일정", "plan", "만들어"]):
        if mentioned_destination:
            return f"📋 {mentioned_destination} 여행 계획을 생성하고 있어요..."
        return "📋 완벽한 여행 계획을 생성하고 있어요..."

    elif any(keyword in user_lower for keyword in ["캘린더", "calendar", "등록"]):
        return "📅 구글 캘린더에 일정을 등록하고 있어요..."

    elif any(keyword in user_lower for keyword in ["공유", "share", "카카오"]):
        return "💬 카카오톡 공유 메시지를 준비하고 있어요..."

    elif any(keyword in user_lower for keyword in ["텍스트", "복사", "copy"]):
        return "📋 여행 계획서를 텍스트로 변환하고 있어요..."

    elif any(keyword in user_lower for keyword in ["수정", "변경", "바꿔", "다시"]):
        return "✏️ 여행 계획을 수정하고 있어요..."

    elif any(keyword in user_lower for keyword in ["맛집", "음식", "식당"]):
        return "🍽️ 현지 맛집 정보를 찾고 있어요..."

    elif any(keyword in user_lower for keyword in ["숙소", "호텔", "펜션", "리조트"]):
        return "🏨 숙박 시설 정보를 검색하고 있어요..."

    elif any(keyword in user_lower for keyword in ["관광지", "명소", "볼거리", "가볼"]):
        return "🎯 인기 관광명소를 찾고 있어요..."

    # 여행 스타일 관련
    elif any(keyword in user_lower for keyword in ["문화", "역사", "전통"]):
        return "🏛️ 문화/역사 여행 정보를 준비하고 있어요..."

    elif any(keyword in user_lower for keyword in ["자연", "힐링", "바다", "산"]):
        return "🌿 자연 힐링 여행 정보를 찾고 있어요..."

    elif any(keyword in user_lower for keyword in ["액티비티", "체험", "모험"]):
        return "🎡 재미있는 액티비티를 찾고 있어요..."

    elif any(keyword in user_lower for keyword in ["쇼핑", "시장", "백화점"]):
        return "🛍️ 쇼핑 스팟을 검색하고 있어요..."

    elif any(keyword in user_lower for keyword in ["카페", "감성", "인스타", "포토"]):
        return "☕ 감성 카페와 포토존을 찾고 있어요..."

    # 여행 기간 관련
    elif any(keyword in user_lower for keyword in ["당일", "1일"]):
        return "⏰ 당일치기 여행 일정을 최적화하고 있어요..."

    elif any(keyword in user_lower for keyword in ["1박", "2일"]):
        return "⏰ 1박 2일 여행 계획을 세우고 있어요..."

    elif any(keyword in user_lower for keyword in ["2박", "3일"]):
        return "⏰ 2박 3일 여행 일정을 구성하고 있어요..."

    # 옵션 선택인 경우
    elif user_input.startswith(
        ("dest_", "place_", "style_", "duration_", "budget_", "companion_")
    ):
        return "✨ 선택하신 옵션을 반영해서 계획을 업데이트하고 있어요..."

    # 버튼 액션 관련
    elif user_input in [
        "add_to_calendar",
        "share_kakao",
        "copy_text",
        "modify_plan",
        "new_plan",
    ]:
        action_messages = {
            "add_to_calendar": "📅 캘린더에 일정을 등록하고 있어요...",
            "share_kakao": "💬 카카오톡 공유를 준비하고 있어요...",
            "copy_text": "📋 텍스트 형태로 변환하고 있어요...",
            "modify_plan": "✏️ 계획 수정 모드로 전환하고 있어요...",
            "new_plan": "🔄 새로운 여행 계획을 시작하고 있어요...",
        }
        return action_messages.get(user_input, "⚙️ 요청하신 작업을 처리하고 있어요...")

    # 현재 단계별 메시지
    elif current_phase == TravelPhase.DESTINATION_SELECTION:
        return "🗺️ 인기 여행지 정보를 불러오고 있어요..."

    elif current_phase == TravelPhase.PREFERENCE_COLLECTION:
        return "🎨 여행 취향을 분석하고 맞춤 정보를 준비하고 있어요..."

    elif current_phase == TravelPhase.DETAILED_PLANNING:
        return "🔍 선택하신 여행지의 상세 정보를 검색하고 있어요..."

    elif current_phase == TravelPhase.PLAN_GENERATION:
        return "🎯 모든 정보를 종합해서 완벽한 여행 계획을 만들고 있어요..."

    elif current_phase == TravelPhase.ACTION_SELECTION:
        return "⚙️ 요청하신 작업을 진행하고 있어요..."

    elif current_phase == TravelPhase.CALENDAR_MANAGEMENT:
        return "📅 캘린더 연동 작업을 처리하고 있어요..."

    elif current_phase == TravelPhase.SHARING:
        return "💬 공유 옵션을 준비하고 있어요..."

    # 기본 메시지들 (더 구체적으로)
    elif len(user_input) > 30:  # 긴 메시지
        return "🤖 상세한 요청사항을 분석하고 답변을 준비하고 있어요..."

    elif any(char in user_input for char in "?？"):  # 질문인 경우
        return "❓ 질문을 분석하고 최적의 답변을 찾고 있어요..."

    elif mentioned_destination:  # 여행지만 언급된 경우
        return f"🗺️ {mentioned_destination} 관련 정보를 준비하고 있어요..."

    else:
        return "🧠 AI가 똑똑하게 분석하고 있어요..."


def render_welcome_message():
    """환영 메시지 (첫 방문시)"""
    if not st.session_state.travel_state.conversation_history:
        st.markdown("""
        ### 👋 안녕하세요! AI 여행 플래너입니다.
        
        저는 여러분의 완벽한 여행 계획을 도와드리는 똑똑한 AI 어시스턴트예요! 🤖✨
        
        **🎯 제가 도와드릴 수 있는 것들:**
        - 🔍 **여행지 추천**: 인기 여행지부터 숨은 명소까지
        - 📋 **맞춤 일정**: 여러분의 취향에 딱 맞는 여행 계획
        - 📅 **캘린더 연동**: 구글 캘린더에 자동 등록
        - 💬 **간편 공유**: 카카오톡으로 친구들과 공유
        
        **🚀 시작하는 방법:**
        
        단순히 "부산 여행 계획해줘" 또는 "제주도로 2박 3일 여행 가고 싶어"라고 말씀해주시면 돼요!
        
        아니면 아래 버튼을 눌러서 시작해보세요 👇
        """)

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button(
                "🗺️ 여행지 추천받기",
                key="welcome_destinations",
                use_container_width=True,
            ):
                # 즉시 처리하지 않고 pending_user_input으로 설정
                st.session_state.pending_user_input = "여행지 추천해줘"
                st.rerun()

        with col2:
            if st.button(
                "🎨 맞춤 여행 계획", key="welcome_custom", use_container_width=True
            ):
                st.session_state.pending_user_input = "맞춤 여행 계획을 세우고 싶어"
                st.rerun()

        with col3:
            if st.button(
                "❓ 사용법 알아보기", key="welcome_help", use_container_width=True
            ):
                st.session_state.pending_user_input = "사용법을 알려줘"
                st.rerun()


def main():
    """메인 함수"""
    load_css()
    initialize_session()

    # 환경 변수 체크
    if not os.getenv("OPENAI_API_KEY"):
        st.error("⚠️ OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요.")
        st.stop()

    if not os.getenv("TAVILY_API_KEY"):
        st.warning(
            "⚠️ TAVILY_API_KEY가 설정되지 않았습니다. 검색 기능이 제한될 수 있습니다."
        )

    # 사이드바 렌더링
    render_sidebar()

    # 메인 채팅 인터페이스
    render_chat_interface()

    # 환영 메시지 (첫 방문시)
    render_welcome_message()


if __name__ == "__main__":
    main()
