import os
from datetime import datetime, timedelta
from typing import Any, Dict, List

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from models.state_models import ScheduleItem, TravelPlan
from dotenv import load_dotenv

load_dotenv()


class CalendarAgent:
    """구글 캘린더 연동 및 일정 관리 에이전트"""

    def __init__(self):
        # Google Calendar API 설정
        self.scopes = ["https://www.googleapis.com/auth/calendar"]
        self.credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE")
        self.token_file = os.getenv("GOOGLE_TOKEN_FILE")

        # 서비스 객체 (lazy loading)
        self._calendar_service = None

        # 로컬 저장용 캐시
        self.calendar_events_cache = {}

    @property
    def calendar_service(self):
        """Google Calendar 서비스 객체를 생성하고 반환합니다."""
        if self._calendar_service is None:
            try:
                self._calendar_service = self._get_calendar_service()
            except Exception as e:
                print(f"Calendar service 초기화 실패: {e}")
                self._calendar_service = None
        return self._calendar_service

    def _get_calendar_service(self):
        """Google Calendar 서비스 객체를 생성합니다."""
        creds = None

        # 토큰 파일이 있으면 로드
        if os.path.exists(self.token_file):
            try:
                creds = Credentials.from_authorized_user_file(
                    self.token_file, self.scopes
                )
            except Exception as e:
                print(f"토큰 파일 로드 실패: {e}")

        # 유효한 인증 정보가 없으면 로그인 플로우 실행
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"토큰 갱신 실패: {e}")
                    creds = None

            if not creds:
                if not os.path.exists(self.credentials_file):
                    print(f"인증 파일 {self.credentials_file}이 없습니다.")
                    return None

                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, self.scopes
                    )
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    print(f"OAuth 인증 실패: {e}")
                    return None

            # 토큰을 파일에 저장
            try:
                with open(self.token_file, "w") as token:
                    token.write(creds.to_json())
            except Exception as e:
                print(f"토큰 저장 실패: {e}")

        try:
            service = build("calendar", "v3", credentials=creds)
            return service
        except Exception as e:
            print(f"Calendar 서비스 생성 실패: {e}")
            return None

    async def add_travel_plan_to_calendar(self, travel_plan: TravelPlan) -> bool:
        """여행 계획을 구글 캘린더에 추가"""

        try:
            # travel_plan 유효성 검사
            if not travel_plan:
                print("캘린더 추가 실패: travel_plan이 None입니다")
                return False

            if not travel_plan.schedule:
                print("캘린더 추가 실패: 여행 일정이 없습니다")
                return False

            # 캘린더 서비스 확인
            if not self.calendar_service:
                print("캘린더 서비스에 연결할 수 없습니다")
                return False

            # 중복 등록 체크 및 처리
            print(f"여행 계획 ID {travel_plan.id}에 대한 기존 이벤트 확인 중...")
            existing_events = await self._check_existing_events(travel_plan.id)

            if existing_events:
                print(
                    f"기존에 등록된 {len(existing_events)}개의 이벤트를 발견했습니다. 삭제 후 새로 등록합니다."
                )

                # 기존 이벤트들 삭제
                deleted_count = 0
                for event in existing_events:
                    try:
                        self.calendar_service.events().delete(
                            calendarId="primary", eventId=event["id"]
                        ).execute()
                        deleted_count += 1
                        print(
                            f"기존 이벤트 삭제 완료: {event.get('summary', 'Unknown')}"
                        )
                    except Exception as e:
                        print(f"기존 이벤트 삭제 실패: {e}")

                print(f"총 {deleted_count}개의 기존 이벤트가 삭제되었습니다.")

            # 여행 계획의 각 일정을 캘린더 이벤트로 변환
            calendar_events = self._convert_plan_to_calendar_events(travel_plan)

            # 캘린더에 이벤트 추가
            success_count = 0
            created_events = []

            for event in calendar_events:
                try:
                    created_event = (
                        self.calendar_service.events()
                        .insert(calendarId="primary", body=event)
                        .execute()
                    )
                    created_events.append(created_event)
                    success_count += 1
                    print(f"이벤트 생성 성공: {event.get('summary', 'Unknown')}")
                except HttpError as e:
                    print(f"캘린더 이벤트 추가 실패: {e}")
                except Exception as e:
                    print(f"이벤트 추가 중 오류: {e}")

            # 생성된 이벤트들을 캐시에 저장
            if created_events:
                self.calendar_events_cache[travel_plan.id] = {
                    "events": created_events,
                    "created_at": datetime.now().isoformat(),
                    "travel_plan_id": travel_plan.id,
                }

            print(f"총 {success_count}개의 새로운 이벤트가 등록되었습니다.")
            return success_count > 0

        except Exception as e:
            print(f"캘린더 추가 중 오류: {e}")
            return False

    def _convert_plan_to_calendar_events(
        self, travel_plan: TravelPlan
    ) -> List[Dict[str, Any]]:
        """여행 계획을 Google Calendar 이벤트 형식으로 변환"""
        calendar_events = []

        # travel_plan과 schedule 안전성 검사
        if not travel_plan or not travel_plan.schedule:
            print(
                "_convert_plan_to_calendar_events: travel_plan 또는 schedule이 없습니다"
            )
            return calendar_events

        for day_schedule in travel_plan.schedule:
            if not day_schedule or not day_schedule.events:
                continue

            date_str = day_schedule.date

            for event in day_schedule.events:
                if not event:
                    continue

                try:
                    # 시작 시간 계산
                    start_datetime = self._combine_date_time(date_str, event.time)
                    end_datetime = start_datetime + timedelta(minutes=event.duration)

                    calendar_event = {
                        "summary": f"🧳 {event.activity}",
                        "location": event.location,
                        "description": self._create_event_description(
                            event, travel_plan
                        ),
                        "start": {
                            "dateTime": start_datetime.isoformat(),
                            "timeZone": "Asia/Seoul",
                        },
                        "end": {
                            "dateTime": end_datetime.isoformat(),
                            "timeZone": "Asia/Seoul",
                        },
                        "colorId": self._get_color_by_category(event.category),
                        "reminders": {
                            "useDefault": False,
                            "overrides": [
                                {"method": "popup", "minutes": 30},
                                {"method": "popup", "minutes": 10},
                            ],
                        },
                        # 여행 계획 ID를 메타데이터로 추가
                        "extendedProperties": {
                            "private": {
                                "travel_plan_id": travel_plan.id,
                                "event_type": "travel_plan",
                                "day_number": str(day_schedule.day_number),
                                "activity_category": event.category,
                            }
                        },
                    }

                    calendar_events.append(calendar_event)
                except Exception as e:
                    print(f"이벤트 변환 중 오류: {e}")
                    continue

        # 여행 전체 기간 요약 이벤트 추가
        if travel_plan.schedule:
            try:
                summary_event = self._create_travel_summary_event(travel_plan)
                calendar_events.insert(0, summary_event)
            except Exception as e:
                print(f"요약 이벤트 생성 중 오류: {e}")

        return calendar_events

    def _create_event_description(
        self, event: ScheduleItem, travel_plan: TravelPlan
    ) -> str:
        """이벤트 설명 생성"""
        description_parts = [
            f"📍 위치: {event.location}",
            f"⏰ 소요시간: {event.duration}분",
            f"🎯 카테고리: {event.category}",
        ]

        if event.estimated_cost:
            description_parts.append(f"💰 예상비용: {event.estimated_cost:,}원")

        if event.notes:
            description_parts.append(f"📝 메모: {event.notes}")

        description_parts.extend(
            [
                "",
                f"🗺️ {travel_plan.destination} 여행",
                f"📅 전체 일정: {len(travel_plan.schedule)}일",
                f"🆔 여행계획 ID: {travel_plan.id}",
                "",
                "✨ AI 여행 플래너로 생성된 일정입니다",
            ]
        )

        return "\n".join(description_parts)

    def _create_travel_summary_event(self, travel_plan: TravelPlan) -> Dict[str, Any]:
        """여행 전체 요약 이벤트 생성"""
        first_day = travel_plan.schedule[0].date
        last_day = travel_plan.schedule[-1].date

        start_date = datetime.strptime(first_day, "%Y-%m-%d")
        end_date = datetime.strptime(last_day, "%Y-%m-%d") + timedelta(days=1)

        summary_description = [
            f"🎉 {travel_plan.destination} 여행이 시작됩니다!",
            "",
            f"📅 기간: {len(travel_plan.schedule)}일",
            f"💰 총 예산: {travel_plan.total_budget:,}원",
            f"🎨 여행 스타일: {travel_plan.user_preferences.travel_style or '일반'}",
            f"🆔 여행계획 ID: {travel_plan.id}",
            "",
            "📋 주요 일정:",
        ]

        for i, day in enumerate(travel_plan.schedule, 1):
            main_activities = [
                e.activity
                for e in day.events
                if e.category not in ["식사", "이동", "숙박"]
            ][:2]
            if main_activities:
                summary_description.append(f"• {i}일차: {', '.join(main_activities)}")

        return {
            "summary": f"🧳 {travel_plan.title}",
            "description": "\n".join(summary_description),
            "start": {
                "date": start_date.strftime("%Y-%m-%d"),
            },
            "end": {
                "date": end_date.strftime("%Y-%m-%d"),
            },
            "colorId": "9",  # 파란색
            "transparency": "transparent",  # 전일 이벤트로 설정
            "extendedProperties": {
                "private": {
                    "travel_plan_id": travel_plan.id,
                    "event_type": "travel_summary",
                }
            },
        }

    def _combine_date_time(self, date_str: str, time_str: str) -> datetime:
        """날짜와 시간 문자열을 datetime 객체로 결합"""
        date_part = datetime.strptime(date_str, "%Y-%m-%d").date()
        time_part = datetime.strptime(time_str, "%H:%M").time()
        return datetime.combine(date_part, time_part)

    def _get_color_by_category(self, category: str) -> str:
        """카테고리별 캘린더 색상 ID"""
        color_map = {
            "이동": "8",  # 회색
            "숙박": "5",  # 노란색
            "식사": "6",  # 주황색
            "관광": "1",  # 보라색
            "문화/역사": "3",  # 보라색
            "자연/관광": "2",  # 초록색
            "액티비티": "4",  # 빨간색
            "쇼핑": "7",  # 청록색
            "카페/감성": "10",  # 분홍색
        }
        return color_map.get(category, "1")  # 기본값: 보라색

    async def view_calendar_events(self, travel_plan_id: str) -> List[Dict[str, Any]]:
        """저장된 캘린더 이벤트 조회"""

        # 통합된 이벤트 검색 메서드 사용
        events = await self._check_existing_events(travel_plan_id)

        # 현재 시간 이후의 이벤트만 필터링 (선택사항)
        current_time = datetime.utcnow().isoformat() + "Z"
        future_events = []

        for event in events:
            event_start = event.get("start", {})
            start_time = event_start.get("dateTime") or event_start.get("date")

            if start_time and start_time >= current_time:
                future_events.append(event)

        # 캐시 업데이트
        if events:
            self.calendar_events_cache[travel_plan_id] = {
                "events": events,
                "retrieved_at": datetime.now().isoformat(),
                "travel_plan_id": travel_plan_id,
            }

        print(
            f"조회된 이벤트: 전체 {len(events)}개, 미래 이벤트 {len(future_events)}개"
        )
        return future_events  # 미래 이벤트만 반환

    async def update_calendar_event(
        self, event_id: str, updates: Dict[str, Any]
    ) -> bool:
        """캘린더 이벤트 수정"""

        if not self.calendar_service:
            return False

        try:
            # 기존 이벤트 조회
            existing_event = (
                self.calendar_service.events()
                .get(calendarId="primary", eventId=event_id)
                .execute()
            )

            # 업데이트 정보 적용
            existing_event.update(updates)

            # 수정된 이벤트 저장
            updated_event = (
                self.calendar_service.events()
                .update(calendarId="primary", eventId=event_id, body=existing_event)
                .execute()
            )

            print(f"이벤트 수정 성공: {updated_event.get('summary', 'Unknown')}")
            return True

        except HttpError as e:
            print(f"캘린더 이벤트 수정 실패: {e}")
            return False
        except Exception as e:
            print(f"이벤트 수정 중 오류: {e}")
            return False

    async def delete_travel_plan_from_calendar(self, travel_plan_id: str) -> bool:
        """여행 계획을 캘린더에서 삭제"""

        if not self.calendar_service:
            return False

        try:
            # 여행 계획 관련 모든 이벤트 검색
            events = await self.view_calendar_events(travel_plan_id)

            deleted_count = 0
            for event in events:
                try:
                    self.calendar_service.events().delete(
                        calendarId="primary", eventId=event["id"]
                    ).execute()
                    deleted_count += 1
                    print(f"이벤트 삭제 성공: {event.get('summary', 'Unknown')}")
                except HttpError as e:
                    print(f"이벤트 삭제 실패: {e}")
                except Exception as e:
                    print(f"이벤트 삭제 중 오류: {e}")

            # 로컬 캐시에서도 삭제
            if travel_plan_id in self.calendar_events_cache:
                del self.calendar_events_cache[travel_plan_id]

            return deleted_count > 0

        except Exception as e:
            print(f"캘린더 삭제 실패: {e}")
            return False

    async def delete_single_event(self, event_id: str) -> bool:
        """단일 이벤트 삭제"""

        if not self.calendar_service:
            return False

        try:
            self.calendar_service.events().delete(
                calendarId="primary", eventId=event_id
            ).execute()

            print(f"이벤트 삭제 성공: {event_id}")
            return True

        except HttpError as e:
            print(f"이벤트 삭제 실패: {e}")
            return False
        except Exception as e:
            print(f"이벤트 삭제 중 오류: {e}")
            return False

    def get_calendar_integration_status(self) -> Dict[str, Any]:
        """캘린더 연동 상태 확인"""
        return {
            "authenticated": self.calendar_service is not None,
            "credentials_file_exists": os.path.exists(self.credentials_file),
            "token_file_exists": os.path.exists(self.token_file),
            "cached_plans": len(self.calendar_events_cache),
            "scopes": self.scopes,
        }

    async def list_calendars(self) -> List[Dict[str, Any]]:
        """사용자의 캘린더 목록 조회"""

        if not self.calendar_service:
            return []

        try:
            calendar_list = self.calendar_service.calendarList().list().execute()
            calendars = calendar_list.get("items", [])

            return [
                {
                    "id": cal["id"],
                    "summary": cal.get("summary", "Unknown"),
                    "primary": cal.get("primary", False),
                    "accessRole": cal.get("accessRole", ""),
                    "backgroundColor": cal.get("backgroundColor", ""),
                }
                for cal in calendars
            ]

        except HttpError as e:
            print(f"캘린더 목록 조회 실패: {e}")
            return []
        except Exception as e:
            print(f"캘린더 목록 조회 중 오류: {e}")
            return []

    def export_to_ics(self, travel_plan: TravelPlan) -> str:
        """여행 계획을 ICS 파일 형식으로 내보내기"""

        ics_content = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//AI Travel Planner//Travel Schedule//KO",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
        ]

        for day_schedule in travel_plan.schedule:
            for event in day_schedule.events:
                start_datetime = self._combine_date_time(day_schedule.date, event.time)
                end_datetime = start_datetime + timedelta(minutes=event.duration)

                # UTC 시간으로 변환 (한국시간 -9시간)
                start_utc = start_datetime - timedelta(hours=9)
                end_utc = end_datetime - timedelta(hours=9)

                ics_content.extend(
                    [
                        "BEGIN:VEVENT",
                        f"UID:{travel_plan.id}-{day_schedule.day_number}-{event.time}@ai-travel-planner.com",
                        f"DTSTART:{start_utc.strftime('%Y%m%dT%H%M%SZ')}",
                        f"DTEND:{end_utc.strftime('%Y%m%dT%H%M%SZ')}",
                        f"SUMMARY:{event.activity}",
                        f"LOCATION:{event.location}",
                        f"DESCRIPTION:{event.notes or ''}",
                        f"CATEGORIES:{event.category}",
                        "STATUS:CONFIRMED",
                        "TRANSP:OPAQUE",
                        "END:VEVENT",
                    ]
                )

        ics_content.append("END:VCALENDAR")

        return "\n".join(ics_content)

    async def sync_travel_plan(self, travel_plan: TravelPlan) -> Dict[str, Any]:
        """여행 계획 동기화 (업데이트된 내용 반영)"""

        try:
            print(f"여행 계획 {travel_plan.id} 동기화 시작...")

            # 기존 이벤트 확인
            existing_events = await self._check_existing_events(travel_plan.id)
            existing_count = len(existing_events)

            print(f"기존 이벤트 {existing_count}개 발견")

            # 기존 이벤트 삭제 (있는 경우만)
            deleted = False
            if existing_events:
                deleted = await self.delete_travel_plan_from_calendar(travel_plan.id)
                print(f"기존 이벤트 삭제: {'성공' if deleted else '실패'}")

            # 새로운 이벤트 추가
            added = await self.add_travel_plan_to_calendar(travel_plan)
            print(f"새 이벤트 추가: {'성공' if added else '실패'}")

            if added:
                message = f"여행 계획이 성공적으로 동기화되었습니다. (기존 {existing_count}개 삭제, 새 이벤트 추가)"
            else:
                message = "동기화에 실패했습니다. 다시 시도해주세요."

            return {
                "success": added,
                "deleted_existing": deleted,
                "existing_count": existing_count,
                "message": message,
            }

        except Exception as e:
            error_msg = f"동기화 중 오류가 발생했습니다: {str(e)}"
            print(error_msg)
            return {
                "success": False,
                "error": str(e),
                "message": error_msg,
            }

    async def _check_existing_events(self, travel_plan_id: str) -> List[Dict[str, Any]]:
        """특정 여행 계획 ID로 등록된 기존 이벤트들을 검색"""

        if not self.calendar_service:
            return []

        try:
            # 로컬 캐시 먼저 확인
            if travel_plan_id in self.calendar_events_cache:
                cached_events = self.calendar_events_cache[travel_plan_id]["events"]
                print(f"캐시에서 {len(cached_events)}개의 기존 이벤트를 발견했습니다.")
                return cached_events

            # Google Calendar에서 이벤트 검색
            # extendedProperties로 travel_plan_id 검색
            events_result = (
                self.calendar_service.events()
                .list(
                    calendarId="primary",
                    privateExtendedProperty=f"travel_plan_id={travel_plan_id}",
                    maxResults=100,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            events = events_result.get("items", [])
            print(f"Google Calendar에서 {len(events)}개의 기존 이벤트를 발견했습니다.")

            return events

        except HttpError as e:
            print(f"기존 이벤트 검색 실패 (HttpError): {e}")

            # 폴백: 제목으로 검색 시도
            try:
                # 여행 계획 ID를 포함한 이벤트들을 제목으로 검색
                fallback_result = (
                    self.calendar_service.events()
                    .list(
                        calendarId="primary",
                        q=f"여행계획 ID: {travel_plan_id}",
                        maxResults=50,
                        singleEvents=True,
                    )
                    .execute()
                )

                fallback_events = fallback_result.get("items", [])
                print(
                    f"폴백 검색으로 {len(fallback_events)}개의 이벤트를 발견했습니다."
                )
                return fallback_events

            except Exception as fallback_error:
                print(f"폴백 검색도 실패: {fallback_error}")
                return []

        except Exception as e:
            print(f"기존 이벤트 검색 중 오류: {e}")
            return []
