import random
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from models.state_models import (
    DaySchedule,
    Place,
    ScheduleItem,
    TravelPlan,
    UserPreferences,
)


class PlannerAgent:
    """여행 계획 생성 및 최적화 전문 에이전트"""

    def __init__(self):
        # 예산별 기본 비용 설정
        self.budget_ranges = {
            "budget": {
                "daily_budget": 50000,
                "meal_cost": 15000,
                "activity_cost": 20000,
            },
            "moderate": {
                "daily_budget": 100000,
                "meal_cost": 25000,
                "activity_cost": 40000,
            },
            "comfortable": {
                "daily_budget": 150000,
                "meal_cost": 40000,
                "activity_cost": 60000,
            },
            "luxury": {
                "daily_budget": 250000,
                "meal_cost": 60000,
                "activity_cost": 100000,
            },
            "unlimited": {
                "daily_budget": 300000,
                "meal_cost": 80000,
                "activity_cost": 120000,
            },
        }

        # 동행자별 활동 선호도
        self.companion_preferences = {
            "solo": {"relaxed": 0.7, "cultural": 0.8, "adventure": 0.6},
            "couple": {"romantic": 0.9, "cultural": 0.6, "relaxed": 0.8},
            "family": {"family_friendly": 0.9, "educational": 0.7, "adventure": 0.5},
            "friends": {"adventure": 0.8, "entertainment": 0.9, "cultural": 0.5},
            "group": {"group_activities": 0.9, "entertainment": 0.8, "cultural": 0.6},
        }

    async def create_travel_plan(
        self,
        user_preferences: UserPreferences,
        selected_places: List[Place] = None,
        context: Dict[str, Any] = None,
    ) -> TravelPlan:
        """여행 계획 생성"""

        # 기본 정보 설정
        plan_id = str(uuid.uuid4())
        title = f"{user_preferences.destination} {user_preferences.duration.get('name', '여행')} 계획"

        # 예산 정보 가져오기
        budget_info = self.budget_ranges.get(user_preferences.budget or "moderate")

        # 일정 생성
        schedule = await self._create_daily_schedule(
            user_preferences=user_preferences,
            selected_places=selected_places or [],
            context=context or {},
            budget_info=budget_info,
        )

        # 총 예산 계산
        total_budget = sum(day.total_cost for day in schedule)

        # 추천 장소 목록 (선택된 장소 + 컨텍스트의 장소들)
        recommended_places = []
        if selected_places:
            recommended_places.extend(
                self._convert_dict_to_place(place)
                for place in selected_places
                if isinstance(place, dict)
            )

        if context and context.get("places"):
            for place_data in context["places"][:5]:
                if isinstance(place_data, dict):
                    recommended_places.append(self._convert_dict_to_place(place_data))

        # TravelPlan 객체 생성
        travel_plan = TravelPlan(
            id=plan_id,
            title=title,
            destination=user_preferences.destination,
            user_preferences=user_preferences,
            schedule=schedule,
            recommended_places=recommended_places,
            total_budget=total_budget,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        return travel_plan

    async def _create_daily_schedule(
        self,
        user_preferences: UserPreferences,
        selected_places: List,
        context: Dict[str, Any],
        budget_info: Dict[str, int],
    ) -> List[DaySchedule]:
        """일별 스케줄 생성"""

        duration = user_preferences.duration or {"days": 2, "nights": 1}
        # duration이 딕셔너리인지 확인하고 안전하게 처리
        if isinstance(duration, dict):
            days = duration.get("days", 2)
        else:
            # duration이 딕셔너리가 아닌 경우 기본값 사용
            days = 2

        schedule = []
        departure_date = self._parse_departure_date(user_preferences.departure_date)

        # 사용 가능한 장소들 준비
        available_places = self._prepare_available_places(selected_places, context)

        for day_num in range(1, days + 1):
            current_date = departure_date + timedelta(days=day_num - 1)

            # 하루 일정 생성
            daily_events = self._create_daily_events(
                day_number=day_num,
                total_days=days,
                user_preferences=user_preferences,
                available_places=available_places,
                budget_info=budget_info,
            )

            # 일일 비용 계산
            daily_cost = sum(event.estimated_cost or 0 for event in daily_events)

            day_schedule = DaySchedule(
                date=current_date.strftime("%Y-%m-%d"),
                day_number=day_num,
                events=daily_events,
                total_cost=daily_cost,
                travel_time=self._calculate_travel_time(daily_events),
            )

            schedule.append(day_schedule)

        return schedule

    def _create_daily_events(
        self,
        day_number: int,
        total_days: int,
        user_preferences: UserPreferences,
        available_places: List[Dict],
        budget_info: Dict[str, int],
    ) -> List[ScheduleItem]:
        """하루 일정의 이벤트들 생성"""

        events = []

        # 시간대별 기본 구조
        if day_number == 1:
            # 첫날: 도착 및 체크인
            events.extend(self._create_arrival_events(user_preferences, budget_info))

        # 오전 활동
        morning_activity = self._select_activity_for_time(
            time_slot="morning",
            available_places=available_places,
            user_preferences=user_preferences,
            budget_info=budget_info,
        )
        if morning_activity:
            events.append(morning_activity)

        # 점심
        lunch_event = self._create_meal_event(
            time="12:00",
            meal_type="점심",
            user_preferences=user_preferences,
            budget_info=budget_info,
            available_places=available_places,
        )
        events.append(lunch_event)

        # 오후 활동
        afternoon_activity = self._select_activity_for_time(
            time_slot="afternoon",
            available_places=available_places,
            user_preferences=user_preferences,
            budget_info=budget_info,
        )
        if afternoon_activity:
            events.append(afternoon_activity)

        # 저녁 (마지막 날이 아닌 경우)
        if day_number < total_days:
            dinner_event = self._create_meal_event(
                time="18:00",
                meal_type="저녁",
                user_preferences=user_preferences,
                budget_info=budget_info,
                available_places=available_places,
            )
            events.append(dinner_event)

            # 저녁 활동 (선택적)
            if user_preferences.travel_style in ["photo", "activity"]:
                evening_activity = self._select_activity_for_time(
                    time_slot="evening",
                    available_places=available_places,
                    user_preferences=user_preferences,
                    budget_info=budget_info,
                )
                if evening_activity:
                    events.append(evening_activity)

        if day_number == total_days:
            # 마지막 날: 체크아웃 및 출발
            events.extend(self._create_departure_events(user_preferences))

        return events

    def _create_arrival_events(
        self, user_preferences: UserPreferences, budget_info: Dict
    ) -> List[ScheduleItem]:
        """도착 일정 생성"""
        events = []

        # 도착
        arrival_event = ScheduleItem(
            time="09:00",
            activity=f"{user_preferences.destination} 도착",
            location=f"{user_preferences.destination} 터미널/역",
            duration=60,
            category="이동",
            notes="여행 시작! 짐을 맡기고 가벼운 마음으로 출발",
            estimated_cost=0,
        )
        events.append(arrival_event)

        # 숙소 체크인 또는 짐 보관
        checkin_event = ScheduleItem(
            time="10:30",
            activity="숙소 체크인 또는 짐 보관",
            location="숙소",
            duration=30,
            category="숙박",
            notes="체크인 시간이 아니라면 짐만 맡기고 관광 시작",
            estimated_cost=0,
        )
        events.append(checkin_event)

        return events

    def _create_departure_events(
        self, user_preferences: UserPreferences
    ) -> List[ScheduleItem]:
        """출발 일정 생성"""
        events = []

        # 체크아웃
        checkout_event = ScheduleItem(
            time="11:00",
            activity="체크아웃 및 짐 정리",
            location="숙소",
            duration=60,
            category="숙박",
            notes="마지막 정리를 하고 아쉬운 마음으로 체크아웃",
            estimated_cost=0,
        )
        events.append(checkout_event)

        # 마지막 쇼핑이나 간단한 관광
        last_activity = ScheduleItem(
            time="13:00",
            activity="기념품 쇼핑 또는 마지막 관광",
            location=f"{user_preferences.destination} 중심가",
            duration=120,
            category="쇼핑",
            notes="여행의 추억을 담은 기념품을 구입하세요",
            estimated_cost=30000,
        )
        events.append(last_activity)

        # 출발
        departure_event = ScheduleItem(
            time="16:00",
            activity=f"{user_preferences.destination} 출발",
            location=f"{user_preferences.destination} 터미널/역",
            duration=60,
            category="이동",
            notes="즐거웠던 여행을 마무리하며 집으로",
            estimated_cost=0,
        )
        events.append(departure_event)

        return events

    def _select_activity_for_time(
        self,
        time_slot: str,
        available_places: List[Dict],
        user_preferences: UserPreferences,
        budget_info: Dict[str, int],
    ) -> Optional[ScheduleItem]:
        """시간대별 적절한 활동 선택"""

        time_mapping = {"morning": "10:00", "afternoon": "14:00", "evening": "19:00"}

        if not available_places:
            return self._create_default_activity(
                time_slot, user_preferences, budget_info
            )

        # 여행 스타일에 맞는 장소 필터링
        suitable_places = self._filter_places_by_style_and_time(
            available_places, user_preferences.travel_style, time_slot
        )

        if not suitable_places:
            suitable_places = available_places  # 필터된 결과가 없으면 전체 사용

        # 랜덤하게 장소 선택
        selected_place = random.choice(suitable_places)

        return ScheduleItem(
            time=time_mapping[time_slot],
            activity=f"{selected_place['name']} 관광",
            location=selected_place["name"],
            duration=self._get_duration_by_category(
                selected_place.get("category", "관광지")
            ),
            category=selected_place.get("category", "관광지"),
            notes=selected_place.get("description", ""),
            estimated_cost=self._estimate_activity_cost(selected_place, budget_info),
        )

    def _create_meal_event(
        self,
        time: str,
        meal_type: str,
        user_preferences: UserPreferences,
        budget_info: Dict[str, int],
        available_places: List[Dict],
    ) -> ScheduleItem:
        """식사 이벤트 생성"""

        # 맛집 정보가 있으면 사용
        restaurants = [
            place for place in available_places if place.get("category") == "맛집"
        ]

        if restaurants:
            restaurant = random.choice(restaurants)
            location = restaurant["name"]
            notes = f"{restaurant.get('description', '')} - {user_preferences.destination} 현지 맛집"
        else:
            location = f"{user_preferences.destination} 현지 음식점"
            notes = f"{user_preferences.destination}의 특색 있는 음식을 맛보세요"

        return ScheduleItem(
            time=time,
            activity=f"{meal_type} 식사",
            location=location,
            duration=90,
            category="식사",
            notes=notes,
            estimated_cost=budget_info.get("meal_cost", 20000),
        )

    def _create_default_activity(
        self,
        time_slot: str,
        user_preferences: UserPreferences,
        budget_info: Dict[str, int],
    ) -> ScheduleItem:
        """기본 활동 생성 (장소 정보가 없을 때)"""

        time_mapping = {"morning": "10:00", "afternoon": "14:00", "evening": "19:00"}

        # 여행 스타일별 기본 활동
        default_activities = {
            "culture": f"{user_preferences.destination} 문화유적 탐방",
            "nature": f"{user_preferences.destination} 자연경관 감상",
            "food": f"{user_preferences.destination} 현지 맛집 탐방",
            "shopping": f"{user_preferences.destination} 쇼핑 및 시장 구경",
            "activity": f"{user_preferences.destination} 체험 활동",
            "photo": f"{user_preferences.destination} 포토스팟 투어",
        }

        activity_name = default_activities.get(
            user_preferences.travel_style, f"{user_preferences.destination} 관광"
        )

        return ScheduleItem(
            time=time_mapping[time_slot],
            activity=activity_name,
            location=f"{user_preferences.destination} 중심가",
            duration=180,
            category="관광",
            notes=f"{user_preferences.destination}의 매력을 느껴보세요",
            estimated_cost=budget_info.get("activity_cost", 30000),
        )

    def _filter_places_by_style_and_time(
        self, places: List[Dict], travel_style: str, time_slot: str
    ) -> List[Dict]:
        """여행 스타일과 시간대에 맞는 장소 필터링"""

        # 시간대별 적합한 카테고리
        time_categories = {
            "morning": ["문화/역사", "자연/관광", "관광지"],
            "afternoon": ["자연/관광", "액티비티", "쇼핑", "관광지"],
            "evening": ["카페/감성", "쇼핑", "관광지"],
        }

        # 여행 스타일별 선호 카테고리
        style_categories = {
            "culture": ["문화/역사", "관광지"],
            "nature": ["자연/관광", "관광지"],
            "food": ["맛집", "관광지"],
            "shopping": ["쇼핑", "관광지"],
            "activity": ["액티비티", "관광지"],
            "photo": ["카페/감성", "자연/관광", "관광지"],
        }

        suitable_categories = set(time_categories.get(time_slot, [])) & set(
            style_categories.get(travel_style, [])
        )

        if not suitable_categories:
            return places  # 필터링 결과가 없으면 전체 반환

        return [
            place for place in places if place.get("category") in suitable_categories
        ]

    def _get_duration_by_category(self, category: str) -> int:
        """카테고리별 소요 시간 (분)"""
        duration_map = {
            "문화/역사": 120,
            "자연/관광": 180,
            "액티비티": 240,
            "쇼핑": 120,
            "카페/감성": 90,
            "맛집": 90,
            "관광지": 150,
        }
        return duration_map.get(category, 120)

    def _estimate_activity_cost(self, place: Dict, budget_info: Dict[str, int]) -> int:
        """활동 비용 추정"""
        category = place.get("category", "관광지")

        base_cost = budget_info.get("activity_cost", 30000)

        # 카테고리별 비용 조정
        cost_multiplier = {
            "문화/역사": 0.5,  # 입장료 위주
            "자연/관광": 0.3,  # 대부분 무료
            "액티비티": 1.5,  # 체험비용
            "쇼핑": 1.2,  # 쇼핑비용
            "카페/감성": 0.4,  # 음료비
            "관광지": 0.6,  # 일반 관광
        }

        multiplier = cost_multiplier.get(category, 0.6)
        return int(base_cost * multiplier)

    def _calculate_travel_time(self, events: List[ScheduleItem]) -> int:
        """하루 총 이동 시간 계산 (분)"""
        # 이벤트 간 평균 이동 시간 추정
        if len(events) <= 1:
            return 0

        # 이벤트 수에 따른 대략적인 이동 시간
        travel_between_events = 20  # 평균 20분
        return (len(events) - 1) * travel_between_events

    def _prepare_available_places(
        self, selected_places: List, context: Dict[str, Any]
    ) -> List[Dict]:
        """사용 가능한 장소들 준비"""
        available_places = []

        # 선택된 장소들 추가
        if selected_places:
            for place in selected_places:
                if isinstance(place, dict):
                    available_places.append(place)
                elif hasattr(place, "__dict__"):
                    available_places.append(place.__dict__)

        # 컨텍스트의 장소들 추가
        if context and context.get("places"):
            for place in context["places"]:
                if isinstance(place, dict):
                    available_places.append(place)

        # 중복 제거 (이름 기준)
        seen_names = set()
        unique_places = []

        for place in available_places:
            name = place.get("name", "")
            if name and name not in seen_names:
                seen_names.add(name)
                unique_places.append(place)

        return unique_places

    def _convert_dict_to_place(self, place_data: Dict) -> Place:
        """딕셔너리를 Place 객체로 변환"""
        return Place(
            name=place_data.get("name", "알 수 없는 장소"),
            address=place_data.get("address", ""),
            category=place_data.get("category", "관광지"),
            description=place_data.get("description", ""),
            rating=place_data.get("rating"),
            price_range=place_data.get("price_range"),
            opening_hours=place_data.get("opening_hours"),
            contact=place_data.get("contact"),
            image_url=place_data.get("image_url"),
            coordinates=place_data.get("coordinates"),
        )

    def _parse_departure_date(self, departure_date: Optional[str]) -> datetime:
        """출발 날짜 파싱"""
        if not departure_date:
            return datetime.now() + timedelta(days=7)  # 기본값: 일주일 후

        try:
            # YYYY-MM-DD 형식
            return datetime.strptime(departure_date, "%Y-%m-%d")
        except ValueError:
            try:
                # MM/DD 형식
                current_year = datetime.now().year
                parsed_date = datetime.strptime(
                    f"{current_year}-{departure_date}", "%Y-%m/%d"
                )
                return parsed_date
            except ValueError:
                # 파싱 실패 시 기본값
                return datetime.now() + timedelta(days=7)

    async def optimize_schedule(self, travel_plan: TravelPlan) -> TravelPlan:
        """기존 여행 계획 최적화"""
        # 이동 시간 최소화
        optimized_schedule = []

        for day_schedule in travel_plan.schedule:
            # 지리적으로 가까운 장소들끼리 그룹핑
            optimized_events = self._optimize_daily_route(day_schedule.events)

            # 시간 재조정
            adjusted_events = self._adjust_event_times(optimized_events)

            optimized_day = DaySchedule(
                date=day_schedule.date,
                day_number=day_schedule.day_number,
                events=adjusted_events,
                total_cost=sum(event.estimated_cost or 0 for event in adjusted_events),
                travel_time=self._calculate_travel_time(adjusted_events),
            )

            optimized_schedule.append(optimized_day)

        travel_plan.schedule = optimized_schedule
        travel_plan.total_budget = sum(day.total_cost for day in optimized_schedule)
        travel_plan.updated_at = datetime.now()

        return travel_plan

    def _optimize_daily_route(self, events: List[ScheduleItem]) -> List[ScheduleItem]:
        """하루 일정의 경로 최적화"""
        # 식사와 고정 시간 활동은 그대로 유지
        fixed_events = [
            event for event in events if event.category in ["식사", "이동", "숙박"]
        ]
        flexible_events = [
            event for event in events if event.category not in ["식사", "이동", "숙박"]
        ]

        # 유연한 이벤트들을 지리적 근접성을 고려하여 재배열
        # (실제로는 GPS 좌표가 필요하지만, 여기서는 이름 기반 간단 로직)
        optimized_flexible = self._sort_events_by_proximity(flexible_events)

        # 시간 순서로 재배열
        all_events = fixed_events + optimized_flexible
        return sorted(all_events, key=lambda x: x.time)

    def _sort_events_by_proximity(
        self, events: List[ScheduleItem]
    ) -> List[ScheduleItem]:
        """근접성 기반 이벤트 정렬 (간단한 휴리스틱)"""
        if len(events) <= 1:
            return events

        # 장소 이름의 키워드 기반 그룹화
        location_groups = {}

        for event in events:
            # 장소 이름에서 주요 키워드 추출
            location_key = self._extract_location_key(event.location)

            if location_key not in location_groups:
                location_groups[location_key] = []
            location_groups[location_key].append(event)

        # 그룹별로 이벤트들을 평평하게 펼치기
        sorted_events = []
        for group_events in location_groups.values():
            sorted_events.extend(group_events)

        return sorted_events

    def _extract_location_key(self, location: str) -> str:
        """장소명에서 지역 키워드 추출"""
        # 한국 지역명 키워드
        region_keywords = [
            "해운대",
            "광안리",
            "중구",
            "서구",
            "동구",
            "남구",
            "북구",
            "중심가",
            "구시가지",
            "신도시",
        ]

        for keyword in region_keywords:
            if keyword in location:
                return keyword

        # 키워드가 없으면 첫 번째 단어 사용
        words = location.split()
        return words[0] if words else location

    def _adjust_event_times(self, events: List[ScheduleItem]) -> List[ScheduleItem]:
        """이벤트 시간 재조정"""
        if not events:
            return events

        # 시간 순서로 정렬
        sorted_events = sorted(events, key=lambda x: x.time)
        adjusted_events = []

        current_time = datetime.strptime("09:00", "%H:%M")

        for event in sorted_events:
            # 이벤트 시간을 순차적으로 조정
            event.time = current_time.strftime("%H:%M")
            adjusted_events.append(event)

            # 다음 이벤트 시간 계산 (현재 이벤트 시간 + 지속시간 + 이동시간)
            duration_minutes = event.duration + 15  # 15분 이동시간 추가
            current_time += timedelta(minutes=duration_minutes)

        return adjusted_events

    async def modify_plan(
        self,
        travel_plan: TravelPlan,
        modification_type: str,
        modification_data: Dict[str, Any],
    ) -> TravelPlan:
        """여행 계획 수정"""

        if modification_type == "change_destination":
            # 목적지 변경
            new_destination = modification_data.get("destination")
            if new_destination:
                travel_plan.destination = new_destination
                travel_plan.user_preferences.destination = new_destination
                travel_plan.title = f"{new_destination} {travel_plan.user_preferences.duration.get('name', '여행')} 계획"

        elif modification_type == "change_budget":
            # 예산 변경
            new_budget = modification_data.get("budget")
            if new_budget:
                travel_plan.user_preferences.budget = new_budget
                # 예산에 따른 비용 재계산
                await self._recalculate_costs(travel_plan)

        elif modification_type == "add_place":
            # 장소 추가
            new_place = modification_data.get("place")
            if new_place:
                # 새 장소를 일정에 추가
                await self._add_place_to_schedule(travel_plan, new_place)

        elif modification_type == "remove_place":
            # 장소 제거
            place_name = modification_data.get("place_name")
            if place_name:
                self._remove_place_from_schedule(travel_plan, place_name)

        # 수정 시간 업데이트
        travel_plan.updated_at = datetime.now()

        return travel_plan

    async def _recalculate_costs(self, travel_plan: TravelPlan):
        """예산 변경에 따른 비용 재계산"""
        budget_info = self.budget_ranges.get(
            travel_plan.user_preferences.budget or "moderate"
        )

        for day_schedule in travel_plan.schedule:
            for event in day_schedule.events:
                if event.category == "식사":
                    event.estimated_cost = budget_info.get("meal_cost", 20000)
                elif event.category in ["관광", "액티비티", "문화/역사"]:
                    event.estimated_cost = int(
                        budget_info.get("activity_cost", 30000) * 0.6
                    )

            # 일일 총 비용 재계산
            day_schedule.total_cost = sum(
                event.estimated_cost or 0 for event in day_schedule.events
            )

        # 전체 예산 재계산
        travel_plan.total_budget = sum(day.total_cost for day in travel_plan.schedule)

    async def _add_place_to_schedule(
        self, travel_plan: TravelPlan, new_place: Dict[str, Any]
    ):
        """새 장소를 일정에 추가"""
        if not travel_plan.schedule:
            return

        # 첫 번째 날에 추가 (간단한 구현)
        first_day = travel_plan.schedule[0]

        new_event = ScheduleItem(
            time="15:30",  # 임시 시간
            activity=f"{new_place.get('name', '새 장소')} 방문",
            location=new_place.get("name", "새 장소"),
            duration=120,
            category=new_place.get("category", "관광지"),
            notes=new_place.get("description", ""),
            estimated_cost=20000,
        )

        first_day.events.append(new_event)
        first_day.total_cost += new_event.estimated_cost or 0

        # 전체 예산 재계산
        travel_plan.total_budget = sum(day.total_cost for day in travel_plan.schedule)

    def _remove_place_from_schedule(self, travel_plan: TravelPlan, place_name: str):
        """일정에서 장소 제거"""
        for day_schedule in travel_plan.schedule:
            events_to_remove = [
                event
                for event in day_schedule.events
                if place_name in event.location or place_name in event.activity
            ]

            for event in events_to_remove:
                day_schedule.events.remove(event)
                day_schedule.total_cost -= event.estimated_cost or 0

        # 전체 예산 재계산
        travel_plan.total_budget = sum(day.total_cost for day in travel_plan.schedule)

    def get_plan_statistics(self, travel_plan: TravelPlan) -> Dict[str, Any]:
        """여행 계획 통계 정보"""
        stats = {
            "총_일수": len(travel_plan.schedule),
            "총_예산": travel_plan.total_budget,
            "일평균_예산": travel_plan.total_budget
            // max(len(travel_plan.schedule), 1),
            "총_활동수": sum(len(day.events) for day in travel_plan.schedule),
            "카테고리별_활동수": {},
            "일별_예산": [day.total_cost for day in travel_plan.schedule],
        }

        # 카테고리별 활동 수 계산
        category_count = {}
        for day in travel_plan.schedule:
            for event in day.events:
                category = event.category
                category_count[category] = category_count.get(category, 0) + 1

        stats["카테고리별_활동수"] = category_count

        return stats
