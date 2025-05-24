import base64
import json
import os
import webbrowser
from typing import Any, Dict, Optional

import requests

from models.state_models import TravelPlan


class ShareAgent:
    """여행 계획 공유 기능 전문 에이전트"""

    def __init__(self):
        # 카카오톡 API 설정
        self.kakao_rest_api_key = os.getenv("KAKAO_REST_API_KEY")
        self.kakao_access_token = os.getenv("KAKAO_ACCESS_TOKEN")
        self.redirect_uri = "http://localhost:8080/callback"

        # OAuth 인증 헬퍼
        self.oauth_helper = None
        if self.kakao_rest_api_key:
            self.oauth_helper = KakaoOAuthHelper(
                self.kakao_rest_api_key, self.redirect_uri
            )

        # 공유 템플릿 설정
        self.share_templates = {
            "simple": self._simple_template,
            "detailed": self._detailed_template,
            "timeline": self._timeline_template,
        }

    def is_kakao_authenticated(self) -> bool:
        """카카오톡 인증 상태 확인"""
        return bool(self.kakao_access_token)

    async def authenticate_kakao(self) -> Dict[str, Any]:
        """카카오톡 OAuth 인증 시작"""

        if not self.kakao_rest_api_key:
            return {
                "success": False,
                "message": "KAKAO_REST_API_KEY가 설정되지 않았습니다.",
                "auth_required": False,
            }

        if not self.oauth_helper:
            return {
                "success": False,
                "message": "OAuth 헬퍼 초기화에 실패했습니다.",
                "auth_required": False,
            }

        try:
            # 인증 URL 생성
            auth_url = self.oauth_helper.get_auth_url()

            # 브라우저에서 자동으로 인증 페이지 열기
            try:
                webbrowser.open(auth_url)
                browser_opened = True
            except Exception as e:
                print(f"브라우저 자동 열기 실패: {e}")
                browser_opened = False

            return {
                "success": True,
                "message": "브라우저에서 카카오 로그인을 완료해주세요."
                if browser_opened
                else "아래 URL을 브라우저에 복사해서 카카오 로그인을 완료해주세요.",
                "auth_url": auth_url,
                "auth_required": True,
                "browser_opened": browser_opened,
                "instructions": [
                    "브라우저에서 카카오 계정으로 로그인하세요"
                    if browser_opened
                    else "위의 URL을 브라우저에서 열어주세요",
                    "카카오 계정으로 로그인하세요",
                    "권한을 승인해주세요",
                    "리다이렉트된 URL에서 'code=' 뒤의 값을 복사하세요",
                    "복사한 인증 코드를 입력해주세요",
                ],
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"인증 URL 생성 실패: {str(e)}",
                "auth_required": False,
            }

    async def complete_kakao_auth(self, auth_code: str) -> Dict[str, Any]:
        """카카오톡 OAuth 인증 완료"""

        if not self.oauth_helper:
            return {"success": False, "message": "OAuth 헬퍼가 초기화되지 않았습니다."}

        try:
            access_token = self.oauth_helper.get_access_token(auth_code)

            if access_token:
                self.kakao_access_token = access_token

                return {
                    "success": True,
                    "message": "카카오톡 인증이 완료되었습니다!",
                    "access_token": access_token,
                    "note": f".env 파일에 KAKAO_ACCESS_TOKEN={access_token} 을 추가하세요",
                }
            else:
                return {
                    "success": False,
                    "message": "인증 코드가 유효하지 않습니다. 다시 시도해주세요.",
                }

        except Exception as e:
            return {"success": False, "message": f"인증 완료 실패: {str(e)}"}

    async def share_to_kakao(
        self, travel_plan: TravelPlan, recipient_info: Dict = None
    ) -> bool:
        """카카오톡으로 여행 계획 공유"""

        # 인증 상태 확인
        if not self.is_kakao_authenticated():
            print("카카오톡 인증이 필요합니다. authenticate_kakao()를 먼저 호출하세요.")
            return False

        try:
            # 카카오톡 메시지 템플릿 생성
            message_template = self._create_kakao_message_template(travel_plan)

            # 실제 카카오톡 API 호출 (템플릿 메시지)
            success = await self._send_kakao_template_message(
                message_template, recipient_info
            )

            if not success:
                # 폴백: 단순 텍스트 메시지
                text_message = self.format_plan_as_text(travel_plan, template="simple")
                success = await self._send_kakao_text_message(
                    text_message, recipient_info
                )

            return success

        except Exception as e:
            print(f"카카오톡 공유 실패: {e}")
            return False

    def _create_kakao_message_template(self, travel_plan: TravelPlan) -> Dict[str, Any]:
        """카카오톡 메시지 템플릿 생성"""

        # 기본 정보
        title = f"🧳 {travel_plan.title}"
        description = (
            f"📍 {travel_plan.destination} | 📅 {len(travel_plan.schedule)}일 여행"
        )

        # 주요 일정 요약
        highlights = []
        for i, day in enumerate(travel_plan.schedule[:3], 1):  # 최대 3일까지
            main_activities = [
                event.activity
                for event in day.events
                if event.category not in ["식사", "이동", "숙박"]
            ][:2]
            if main_activities:
                highlights.append(f"• {i}일차: {', '.join(main_activities)}")

        # Feed 템플릿 사용
        template = {
            "object_type": "feed",
            "content": {
                "title": title,
                "description": description,
                "image_url": self._get_destination_image_url(travel_plan.destination),
                "link": {
                    "web_url": "http://localhost:8501",  # Streamlit 앱 URL
                    "mobile_web_url": "http://localhost:8501",
                },
            },
            "item_content": {
                "profile_text": "AI 여행 플래너",
                "title_image_url": "https://example.com/travel-icon.png",
                "items": [
                    {"item": "일정", "item_op": f"{len(travel_plan.schedule)}일"},
                    {
                        "item": "예산",
                        "item_op": f"{travel_plan.total_budget:,}원"
                        if travel_plan.total_budget > 0
                        else "미정",
                    },
                    {
                        "item": "스타일",
                        "item_op": self._get_style_name(
                            travel_plan.user_preferences.travel_style
                        ),
                    },
                ],
            },
            "social": {"like_count": 0, "comment_count": 0, "shared_count": 0},
            "buttons": [
                {
                    "title": "상세 일정 보기",
                    "link": {
                        "web_url": "http://localhost:8501",
                        "mobile_web_url": "http://localhost:8501",
                    },
                }
            ],
        }

        return template

    async def _send_kakao_template_message(
        self, template: Dict[str, Any], recipient_info: Dict = None
    ) -> bool:
        """카카오톡 템플릿 메시지 전송"""

        try:
            # 카카오톡 메시지 API 엔드포인트
            url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"

            headers = {
                "Authorization": f"Bearer {self.kakao_access_token}",
                "Content-Type": "application/x-www-form-urlencoded",
            }

            data = {"template_object": json.dumps(template, ensure_ascii=False)}

            # API 호출
            response = requests.post(url, headers=headers, data=data)

            if response.status_code == 200:
                print("카카오톡 메시지 전송 성공!")
                return True
            else:
                print(f"카카오톡 메시지 전송 실패: {response.status_code}")
                print(f"응답: {response.text}")

                # 401 에러인 경우 토큰 만료 안내
                if response.status_code == 401:
                    print(
                        "Access Token이 만료되었거나 유효하지 않습니다. 재인증이 필요합니다."
                    )

                return False

        except Exception as e:
            print(f"카카오톡 템플릿 메시지 전송 오류: {e}")
            return False

    async def _send_kakao_text_message(
        self, text_message: str, recipient_info: Dict = None
    ) -> bool:
        """카카오톡 텍스트 메시지 전송 (폴백)"""

        try:
            # 간단한 텍스트 템플릿
            template = {
                "object_type": "text",
                "text": text_message,
                "link": {
                    "web_url": "http://localhost:8501",
                    "mobile_web_url": "http://localhost:8501",
                },
            }

            return await self._send_kakao_template_message(template, recipient_info)

        except Exception as e:
            print(f"카카오톡 텍스트 메시지 전송 오류: {e}")
            return False

    async def test_kakao_connection(self) -> Dict[str, Any]:
        """카카오톡 연결 테스트"""

        if not self.is_kakao_authenticated():
            return {
                "success": False,
                "message": "카카오톡 인증이 필요합니다.",
                "authenticated": False,
            }

        try:
            # 사용자 정보 조회로 연결 테스트
            url = "https://kapi.kakao.com/v2/user/me"
            headers = {
                "Authorization": f"Bearer {self.kakao_access_token}",
                "Content-Type": "application/x-www-form-urlencoded",
            }

            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                user_info = response.json()
                nickname = user_info.get("properties", {}).get("nickname", "Unknown")

                return {
                    "success": True,
                    "message": f"카카오톡 연결 성공! ({nickname}님)",
                    "authenticated": True,
                    "user_info": user_info,
                }
            else:
                return {
                    "success": False,
                    "message": f"카카오톡 연결 실패: {response.status_code}",
                    "authenticated": False,
                    "response": response.text,
                }

        except Exception as e:
            return {
                "success": False,
                "message": f"연결 테스트 오류: {str(e)}",
                "authenticated": False,
            }

    def format_plan_as_text(
        self, travel_plan: TravelPlan, template: str = "detailed"
    ) -> str:
        """여행 계획을 텍스트 형식으로 포맷팅"""

        formatter = self.share_templates.get(template, self._detailed_template)
        return formatter(travel_plan)

    def _simple_template(self, travel_plan: TravelPlan) -> str:
        """간단한 텍스트 템플릿"""

        text_parts = [
            f"🧳 {travel_plan.title}",
            f"📍 {travel_plan.destination}",
            f"📅 {travel_plan.user_preferences.departure_date or '날짜 미정'}",
            f"⏰ {len(travel_plan.schedule)}일 여행",
            "",
        ]

        if travel_plan.total_budget > 0:
            text_parts.append(f"💰 예상 비용: {travel_plan.total_budget:,}원")
            text_parts.append("")

        # 주요 일정
        text_parts.append("📋 주요 일정:")
        for i, day in enumerate(travel_plan.schedule, 1):
            main_activities = [
                event.activity
                for event in day.events
                if event.category not in ["식사", "이동", "숙박"]
            ][:2]
            if main_activities:
                text_parts.append(f"• {i}일차: {', '.join(main_activities)}")

        text_parts.extend(["", "✨ AI 여행 플래너로 생성된 계획입니다!"])

        return "\n".join(text_parts)

    def _detailed_template(self, travel_plan: TravelPlan) -> str:
        """상세 텍스트 템플릿"""

        text_parts = [
            "=" * 40,
            f"🧳 {travel_plan.title}",
            "=" * 40,
            "",
            f"📍 목적지: {travel_plan.destination}",
            f"📅 출발일: {travel_plan.user_preferences.departure_date or '날짜 미정'}",
            f"⏰ 기간: {len(travel_plan.schedule)}일",
            f"🎨 스타일: {self._get_style_name(travel_plan.user_preferences.travel_style)}",
            f"👥 동행: {self._get_companion_name(travel_plan.user_preferences.companion_type)}",
            "",
        ]

        if travel_plan.total_budget > 0:
            text_parts.extend(
                [
                    f"💰 총 예산: {travel_plan.total_budget:,}원",
                    f"💰 일평균: {travel_plan.total_budget // len(travel_plan.schedule):,}원",
                    "",
                ]
            )

        # 일별 상세 일정
        text_parts.append("📅 상세 일정:")
        text_parts.append("-" * 40)

        for day in travel_plan.schedule:
            text_parts.extend(["", f"📆 {day.day_number}일차 ({day.date})", "-" * 20])

            for event in day.events:
                cost_text = (
                    f" (₩{event.estimated_cost:,})" if event.estimated_cost else ""
                )
                text_parts.append(f"{event.time} | {event.activity}{cost_text}")
                text_parts.append(f"     📍 {event.location}")

                if event.notes:
                    text_parts.append(f"     📝 {event.notes}")

                text_parts.append("")

            if day.total_cost > 0:
                text_parts.append(f"💰 일일 총 비용: {day.total_cost:,}원")
                text_parts.append("")

        text_parts.extend(
            [
                "=" * 40,
                "✨ AI 여행 플래너로 생성된 계획",
                f"🕐 생성 시간: {travel_plan.created_at.strftime('%Y-%m-%d %H:%M')}",
                "=" * 40,
            ]
        )

        return "\n".join(text_parts)

    def _timeline_template(self, travel_plan: TravelPlan) -> str:
        """타임라인 형식 템플릿"""

        text_parts = [f"🧳 {travel_plan.title} - 타임라인", "=" * 50, ""]

        # 모든 이벤트를 시간순으로 정렬
        all_events = []
        for day in travel_plan.schedule:
            for event in day.events:
                all_events.append(
                    {"date": day.date, "day_number": day.day_number, "event": event}
                )

        current_date = None
        for item in all_events:
            event = item["event"]

            # 날짜가 바뀔 때마다 구분선
            if item["date"] != current_date:
                current_date = item["date"]
                text_parts.extend(
                    ["", f"📅 {item['day_number']}일차 - {current_date}", "─" * 30, ""]
                )

            # 이벤트 정보
            emoji = self._get_category_emoji(event.category)
            text_parts.append(f"{event.time} {emoji} {event.activity}")
            text_parts.append(f"      📍 {event.location}")

            if event.estimated_cost:
                text_parts.append(f"      💰 {event.estimated_cost:,}원")

            text_parts.append("")

        return "\n".join(text_parts)

    def _get_style_name(self, travel_style: Optional[str]) -> str:
        """여행 스타일 이름 반환"""
        style_names = {
            "culture": "문화/역사 탐방",
            "nature": "자연/힐링",
            "food": "맛집 투어",
            "shopping": "쇼핑/도시",
            "activity": "액티비티/모험",
            "photo": "인스타/감성",
        }
        return style_names.get(travel_style, "일반 관광")

    def _get_companion_name(self, companion_type: Optional[str]) -> str:
        """동행자 타입 이름 반환"""
        companion_names = {
            "solo": "혼자",
            "couple": "연인/배우자",
            "family": "가족",
            "friends": "친구들",
            "group": "단체",
        }
        return companion_names.get(companion_type, "미정")

    def _get_category_emoji(self, category: str) -> str:
        """카테고리별 이모지 반환"""
        emoji_map = {
            "이동": "🚗",
            "숙박": "🏨",
            "식사": "🍽️",
            "관광": "🎯",
            "문화/역사": "🏛️",
            "자연/관광": "🌿",
            "액티비티": "🎡",
            "쇼핑": "🛍️",
            "카페/감성": "☕",
        }
        return emoji_map.get(category, "📍")

    def _get_destination_image_url(self, destination: str) -> str:
        """목적지별 대표 이미지 URL (예시)"""
        # 실제로는 외부 이미지 서비스나 미리 준비된 이미지 사용
        image_urls = {
            "제주도": "https://example.com/jeju.jpg",
            "부산": "https://example.com/busan.jpg",
            "경주": "https://example.com/gyeongju.jpg",
            "강릉": "https://example.com/gangneung.jpg",
            "여수": "https://example.com/yeosu.jpg",
        }
        return image_urls.get(destination, "https://example.com/default-travel.jpg")

    async def share_via_email(
        self, travel_plan: TravelPlan, email_address: str
    ) -> bool:
        """이메일로 여행 계획 공유"""

        try:
            # 이메일 내용 생성
            subject = f"🧳 {travel_plan.title} - 여행 계획서"
            body = self.format_plan_as_text(travel_plan, template="detailed")

            # 실제 구현에서는 SMTP 서버 사용
            # 여기서는 Mock 구현
            print("이메일 전송 시뮬레이션:")
            print(f"To: {email_address}")
            print(f"Subject: {subject}")
            print(f"Body: {body[:200]}...")

            return True

        except Exception as e:
            print(f"이메일 공유 실패: {e}")
            return False

    def generate_share_link(self, travel_plan: TravelPlan) -> str:
        """공유 링크 생성"""

        # 실제로는 계획 ID를 암호화하여 공유 링크 생성
        base_url = "http://localhost:8501"
        share_id = base64.urlsafe_b64encode(travel_plan.id.encode()).decode()

        return f"{base_url}/shared/{share_id}"

    def export_to_pdf(self, travel_plan: TravelPlan) -> bytes:
        """여행 계획을 PDF로 내보내기 (Mock)"""

        try:
            # 실제로는 reportlab 등을 사용하여 PDF 생성
            # 여기서는 텍스트 내용을 바이트로 변환
            text_content = self.format_plan_as_text(travel_plan, template="detailed")

            return text_content.encode("utf-8")

        except Exception as e:
            print(f"PDF 생성 실패: {e}")
            return b""

    def get_share_statistics(self, travel_plan_id: str) -> Dict[str, Any]:
        """공유 통계 (Mock)"""

        return {
            "plan_id": travel_plan_id,
            "kakao_shares": 0,
            "email_shares": 0,
            "link_views": 0,
            "pdf_downloads": 0,
            "last_shared": None,
        }

    def get_kakao_status(self) -> Dict[str, Any]:
        """카카오톡 연동 상태 반환"""
        return {
            "api_key_configured": bool(self.kakao_rest_api_key),
            "access_token_available": bool(self.kakao_access_token),
            "authenticated": self.is_kakao_authenticated(),
            "oauth_helper_ready": bool(self.oauth_helper),
        }


class KakaoOAuthHelper:
    """카카오 OAuth 인증 헬퍼 클래스"""

    def __init__(self, client_id: str, redirect_uri: str):
        self.client_id = client_id
        self.redirect_uri = redirect_uri

    def get_auth_url(self) -> str:
        """1단계: 인증 URL 생성"""
        base_url = "https://kauth.kakao.com/oauth/authorize"
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "profile_nickname,talk_message",
        }

        param_str = "&".join([f"{k}={v}" for k, v in params.items()])
        auth_url = f"{base_url}?{param_str}"

        return auth_url

    def get_access_token(self, auth_code: str) -> Optional[str]:
        """2단계: Access Token 발급"""
        url = "https://kauth.kakao.com/oauth/token"

        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "code": auth_code,
        }

        try:
            response = requests.post(url, data=data)

            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get("access_token")

                print("✅ Access Token 발급 성공!")
                print(f"토큰: {access_token}")

                # .env 파일에 저장 안내
                print("\n📝 .env 파일에 다음 줄을 추가하세요:")
                print(f"KAKAO_ACCESS_TOKEN={access_token}")

                return access_token
            else:
                print(f"❌ 토큰 발급 실패: {response.text}")
                return None

        except Exception as e:
            print(f"❌ 토큰 발급 중 오류: {e}")
            return None
