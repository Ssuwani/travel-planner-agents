"""
UI 관련 유틸리티 함수들
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st


def load_css():
    """CSS 파일을 로드합니다."""
    css_file = Path("static/style.css")
    if css_file.exists():
        with open(css_file, "r", encoding="utf-8") as f:
            css_content = f.read()
        st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    else:
        # 기본 스타일 (fallback)
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
        }
        .destination-card {
            border: 1px solid #e0e0e0;
            border-radius: 0.5rem;
            padding: 1rem;
            margin: 0.5rem 0;
            transition: all 0.3s ease;
            cursor: pointer;
        }
        .destination-card:hover {
            border-color: #2E86AB;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            transform: translateY(-2px);
        }
        .destination-card.selected {
            border-color: #2E86AB;
            background-color: #e3f2fd;
        }
        .place-option {
            background-color: #f8f9fa;
            border: 1px solid #e0e0e0;
            border-radius: 0.3rem;
            padding: 0.8rem;
            margin: 0.3rem 0;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .place-option:hover {
            background-color: #e3f2fd;
            border-color: #2E86AB;
        }
        .place-option.selected {
            background-color: #e3f2fd;
            border-color: #2E86AB;
        }
        .custom-input-section {
            background-color: #fff8e1;
            border: 2px dashed #ffb300;
            border-radius: 0.5rem;
            padding: 1.5rem;
            margin: 1rem 0;
            text-align: center;
        }
        </style>
        """,
            unsafe_allow_html=True,
        )


def format_duration_safely(duration) -> str:
    """duration을 안전하게 포맷팅하는 유틸리티 함수"""
    if not duration:
        return "미정"

    if isinstance(duration, dict):
        return duration.get("name", f"{duration.get('days', '?')}일")
    else:
        return str(duration)


def render_option_buttons(options: List[Dict[str, Any]]) -> Optional[str]:
    """옵션 버튼들을 렌더링하고 선택된 값을 반환"""
    if not options:
        return None

    selected_option = None

    # 행별로 버튼 배치
    cols_per_row = 2
    for i in range(0, len(options), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, option in enumerate(options[i : i + cols_per_row]):
            with cols[j]:
                if st.button(
                    option["label"],
                    key=f"option_{option['value']}_{i + j}",
                    use_container_width=True,
                ):
                    selected_option = option["value"]

    return selected_option


def render_text_area_response(formatted_text: str):
    """텍스트 영역으로 응답을 렌더링"""
    st.markdown(
        f"""
        <div class="text-area-container">
            {formatted_text.replace("\n", "<br>")}
        </div>
        """,
        unsafe_allow_html=True,
    )


def display_chat_message(role: str, content: str):
    """채팅 메시지를 표시"""
    if role == "user":
        st.markdown(
            f'<div class="chat-message user-message">{content}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="chat-message ai-message">{content}</div>',
            unsafe_allow_html=True,
        )


def show_welcome_message():
    """환영 메시지를 표시"""
    from config.constants import WELCOME_MESSAGE

    st.markdown('<div class="main-header">AI 여행 플래너</div>', unsafe_allow_html=True)

    st.markdown(
        f'<div class="chat-message ai-message">{WELCOME_MESSAGE}</div>',
        unsafe_allow_html=True,
    )


def render_destination_selector(destinations: List[Any]) -> Optional[str]:
    """여행지 선택 UI를 렌더링합니다."""
    st.markdown("### 🗺️ 추천 여행지")
    st.markdown("아래 추천 여행지 중 선택하시거나, 직접 입력해주세요!")

    selected_destination = None

    # 추천 여행지 카드 형태로 표시
    for i, dest in enumerate(destinations[:6]):
        col1, col2 = st.columns([3, 1])

        with col1:
            st.markdown(
                f"""
            <div class="destination-card">
                <h4>{dest.name} ({dest.region})</h4>
                <p>{dest.description}</p>
                <small>인기도: {"⭐" * int(dest.popularity_score)}</small>
            </div>
            """,
                unsafe_allow_html=True,
            )

        with col2:
            if st.button("선택", key=f"dest_btn_{i}", use_container_width=True):
                selected_destination = dest.name

    # 직접 입력 섹션
    st.markdown("---")
    st.markdown(
        """
    <div class="custom-input-section">
        <h4>✏️ 직접 입력하기</h4>
        <p>원하는 여행지가 위에 없나요? 직접 입력해주세요!</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    custom_destination = st.text_input(
        "여행지 직접 입력",
        placeholder="예: 강릉, 속초, 경주 등...",
        key="custom_destination_input",
    )

    if custom_destination:
        if st.button("✅ 입력한 여행지로 결정", key="confirm_custom_dest"):
            selected_destination = custom_destination

    return selected_destination


def render_place_selector(places: List[Dict[str, Any]], destination: str) -> List[str]:
    """장소 선택 UI를 렌더링합니다."""
    st.markdown(f"### 📍 {destination} 추천 장소")
    st.markdown("가고 싶은 장소들을 선택해주세요! (여러 개 선택 가능)")

    if not places:
        st.warning(
            "추천 장소를 찾을 수 없어요. 다른 여행지를 선택해보시거나 직접 입력해주세요."
        )
        return []

    selected_places = []

    # 장소들을 카테고리별로 그룹화
    categorized_places = {}
    for place in places:
        category = place.get("category", "기타")
        if category not in categorized_places:
            categorized_places[category] = []
        categorized_places[category].append(place)

    # 카테고리별로 장소 표시
    for category, category_places in categorized_places.items():
        st.markdown(f"#### {category}")

        cols = st.columns(2)
        for i, place in enumerate(category_places):
            col_idx = i % 2

            with cols[col_idx]:
                place_key = f"place_{place['name']}"

                # 체크박스로 장소 선택
                if st.checkbox(
                    f"**{place['name']}**",
                    key=place_key,
                    help=place.get("description", ""),
                ):
                    selected_places.append(place["name"])

                # 장소 설명 표시
                if place.get("description"):
                    st.markdown(
                        f"<small>{place['description'][:60]}...</small>",
                        unsafe_allow_html=True,
                    )

    # 직접 입력 옵션
    st.markdown("---")
    st.markdown("### ✏️ 추가로 가고 싶은 곳이 있나요?")

    additional_place = st.text_input(
        "장소 직접 입력",
        placeholder=f"{destination}에서 가고 싶은 다른 곳을 입력해주세요",
        key="additional_place_input",
    )

    if additional_place:
        if st.button("➕ 장소 추가", key="add_custom_place"):
            selected_places.append(additional_place)
            st.success(f"'{additional_place}'이(가) 추가되었습니다!")

    return selected_places


def render_mixed_destination_input() -> Optional[str]:
    """여행지 추천과 직접 입력을 함께 제공하는 UI"""
    st.markdown("### 🌍 어디로 여행을 떠나고 싶으세요?")

    # 탭으로 구분
    tab1, tab2 = st.tabs(["🔥 인기 여행지", "✏️ 직접 입력"])

    selected_destination = None

    with tab1:
        st.markdown("**인기 여행지에서 선택해보세요!**")

        # 간단한 인기 여행지 목록
        popular_destinations = [
            {"name": "제주도", "desc": "한라산과 아름다운 해변의 섬", "emoji": "🏝️"},
            {"name": "부산", "desc": "해운대와 광안리의 바다 도시", "emoji": "🌊"},
            {"name": "경주", "desc": "신라 천년의 역사가 살아있는 도시", "emoji": "🏛️"},
            {"name": "강릉", "desc": "커피거리와 동해바다의 낭만", "emoji": "☕"},
            {"name": "여수", "desc": "밤바다의 아름다운 야경", "emoji": "🌙"},
            {"name": "전주", "desc": "한옥마을과 맛있는 음식", "emoji": "🏠"},
        ]

        cols = st.columns(2)
        for i, dest in enumerate(popular_destinations):
            col_idx = i % 2
            with cols[col_idx]:
                if st.button(
                    f"{dest['emoji']} {dest['name']}\n{dest['desc']}",
                    key=f"popular_dest_{dest['name']}",
                    use_container_width=True,
                ):
                    selected_destination = dest["name"]

    with tab2:
        st.markdown("**원하는 여행지를 직접 입력해주세요!**")

        custom_dest = st.text_input(
            "여행지 입력",
            placeholder="예: 속초, 춘천, 안동, 담양, 통영 등...",
            key="custom_destination_tab",
        )

        if custom_dest:
            if st.button("🎯 이 여행지로 결정!", key="confirm_custom_destination"):
                selected_destination = custom_dest
                st.success(f"'{custom_dest}' 여행을 계획해보겠습니다! ✈️")

    return selected_destination


def render_travel_style_selector() -> Optional[str]:
    """여행 스타일 선택 UI"""
    from models.state_models import TRAVEL_STYLES

    st.markdown("### 🎨 어떤 스타일의 여행을 원하세요?")

    selected_style = None

    # 3열로 배치
    cols = st.columns(3)
    styles = list(TRAVEL_STYLES.items())

    for i, (key, info) in enumerate(styles):
        col_idx = i % 3

        with cols[col_idx]:
            if st.button(
                f"{info['icon']}\n**{info['name']}**\n{info['desc']}",
                key=f"style_{key}",
                use_container_width=True,
                help=info["desc"],
            ):
                selected_style = key

    return selected_style


def render_duration_selector() -> Optional[Dict[str, Any]]:
    """여행 기간 선택 UI"""
    st.markdown("### ⏰ 며칠 정도 여행하실 건가요?")

    duration_options = [
        {"key": "day_trip", "name": "당일치기", "days": 1, "nights": 0, "icon": "🌅"},
        {"key": "1n2d", "name": "1박 2일", "days": 2, "nights": 1, "icon": "🌙"},
        {"key": "2n3d", "name": "2박 3일", "days": 3, "nights": 2, "icon": "🌛"},
        {"key": "3n4d", "name": "3박 4일", "days": 4, "nights": 3, "icon": "🌜"},
        {"key": "4n5d", "name": "4박 5일", "days": 5, "nights": 4, "icon": "🌝"},
        {
            "key": "week_plus",
            "name": "일주일 이상",
            "days": 7,
            "nights": 6,
            "icon": "📅",
        },
    ]

    selected_duration = None

    # 2열로 배치
    cols = st.columns(2)

    for i, option in enumerate(duration_options):
        col_idx = i % 2

        with cols[col_idx]:
            if st.button(
                f"{option['icon']} {option['name']}",
                key=f"duration_{option['key']}",
                use_container_width=True,
            ):
                selected_duration = {
                    "key": option["key"],
                    "name": option["name"],
                    "days": option["days"],
                    "nights": option["nights"],
                }

    return selected_duration


def render_budget_selector() -> Optional[str]:
    """예산 선택 UI"""
    from models.state_models import BUDGET_RANGES

    st.markdown("### 💰 예산은 어느 정도 생각하고 계세요?")

    selected_budget = None

    # 버튼으로 예산 선택
    for key, info in BUDGET_RANGES.items():
        if st.button(
            f"{info['icon']} {info['name']} ({info['range']})",
            key=f"budget_{key}",
            use_container_width=True,
        ):
            selected_budget = key

    return selected_budget


def render_companion_selector() -> Optional[str]:
    """동행자 선택 UI"""
    from models.state_models import COMPANION_TYPES

    st.markdown("### 👥 누구와 함께 가시나요?")

    selected_companion = None

    # 2열로 배치
    cols = st.columns(2)
    companions = list(COMPANION_TYPES.items())

    for i, (key, info) in enumerate(companions):
        col_idx = i % 2

        with cols[col_idx]:
            if st.button(
                f"{info['icon']} {info['name']}",
                key=f"companion_{key}",
                use_container_width=True,
            ):
                selected_companion = key

    return selected_companion


def render_departure_date_selector() -> Optional[str]:
    """출발일 선택 UI"""
    st.markdown("### 📅 언제 출발하실 예정인가요?")

    from datetime import datetime, timedelta

    selected_date = None

    # 빠른 선택 옵션
    quick_options = [
        {"label": "이번 주말", "days": 2, "icon": "🌅"},
        {"label": "다음 주말", "days": 9, "icon": "📆"},
        {"label": "2주 후", "days": 14, "icon": "🗓️"},
        {"label": "다음 달", "days": 30, "icon": "📝"},
    ]

    st.markdown("**빠른 선택:**")
    cols = st.columns(2)

    for i, option in enumerate(quick_options):
        col_idx = i % 2
        target_date = datetime.now() + timedelta(days=option["days"])

        with cols[col_idx]:
            if st.button(
                f"{option['icon']} {option['label']}\n({target_date.strftime('%m/%d')})",
                key=f"quick_date_{i}",
                use_container_width=True,
            ):
                selected_date = target_date.strftime("%Y-%m-%d")

    # 직접 날짜 선택
    st.markdown("---")
    st.markdown("**직접 날짜 선택:**")

    date_input = st.date_input(
        "출발일을 선택해주세요",
        value=datetime.now().date() + timedelta(days=7),
        min_value=datetime.now().date(),
        key="custom_date_input",
    )

    if st.button("📅 선택한 날짜로 확정", key="confirm_custom_date"):
        selected_date = date_input.strftime("%Y-%m-%d")

    return selected_date


def render_preference_collection_ui(state) -> Optional[Dict[str, Any]]:
    """사용자 선호사항 수집을 위한 통합 UI"""
    prefs = state.user_preferences

    # 누락된 정보 확인
    missing_info = []
    if not prefs.travel_style:
        missing_info.append("travel_style")
    if not prefs.duration:
        missing_info.append("duration")
    if not prefs.departure_date:
        missing_info.append("departure_date")
    if not prefs.budget:
        missing_info.append("budget")
    if not prefs.companion_type:
        missing_info.append("companion_type")

    if not missing_info:
        return None  # 모든 정보가 수집됨

    # 첫 번째 누락된 정보에 대한 UI 표시
    next_step = missing_info[0]

    if next_step == "travel_style":
        return {"type": "travel_style", "value": render_travel_style_selector()}
    elif next_step == "duration":
        duration_result = render_duration_selector()
        if duration_result:
            # JSON 문자열로 변환
            duration_json = json.dumps(duration_result)
            return {"type": "duration", "value": duration_json}
        return None
    elif next_step == "departure_date":
        return {"type": "departure_date", "value": render_departure_date_selector()}
    elif next_step == "budget":
        return {"type": "budget", "value": render_budget_selector()}
    elif next_step == "companion_type":
        return {"type": "companion_type", "value": render_companion_selector()}

    return None
