import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from tavily import TavilyClient

from models.state_models import Destination


class SearchAgent:
    """여행 관련 정보 검색 전문 에이전트"""

    def __init__(self):
        self.tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

        # 캐시
        self.search_cache = {}
        self.cache_duration = 3600  # 1시간

        # 한국 주요 여행지 기본 데이터 (폴백용)
        self.fallback_destinations = [
            Destination(
                name="제주도",
                region="제주특별자치도",
                type="island",
                description="한라산과 아름다운 해변, 독특한 문화가 어우러진 한국 최고의 관광지",
                popularity_score=9.5,
            ),
            Destination(
                name="부산",
                region="부산광역시",
                type="coastal",
                description="해운대, 광안리 해변과 신선한 해산물, 활기찬 항구 도시의 매력",
                popularity_score=9.0,
            ),
            Destination(
                name="경주",
                region="경상북도",
                type="historical",
                description="신라 천년의 역사가 살아 숨 쉬는 야외 박물관 같은 고도",
                popularity_score=8.5,
            ),
            Destination(
                name="강릉",
                region="강원도",
                type="coastal",
                description="동해의 푸른 바다와 커피 거리, 사시사철 아름다운 관동팔경",
                popularity_score=8.0,
            ),
            Destination(
                name="여수",
                region="전라남도",
                type="coastal",
                description="여수 밤바다의 낭만과 돌산대교, 해상케이블카의 절경",
                popularity_score=7.8,
            ),
        ]

    async def search_popular_destinations(
        self, region: str = "한국"
    ) -> List[Destination]:
        """인기 여행지 검색"""

        cache_key = f"popular_destinations_{region}"

        # 캐시 확인
        if self._is_cache_valid(cache_key):
            return self.search_cache[cache_key]["data"]

        destinations = []

        try:
            # Tavily를 통한 실시간 검색
            query = f"{region} 인기 여행지 추천 관광명소 2024 2025"

            search_results = self.tavily_client.search(
                query=query,
                search_depth="basic",
                max_results=8,
                include_domains=["visitkorea.or.kr", "korea.net", "naverblog.com"],
            )

            destinations = self._extract_destinations_from_search(
                search_results.get("results", [])
            )

        except Exception as e:
            print(f"Tavily search error: {e}")
            destinations = self.fallback_destinations

        # 캐시 저장
        self._save_to_cache(cache_key, destinations)

        return destinations[:5]  # Top 5 반환

    async def search_destination_details(
        self, destination: str, travel_style: str = "general"
    ) -> Dict[str, Any]:
        """특정 여행지의 상세 정보 검색"""

        cache_key = f"destination_details_{destination}_{travel_style}"

        # 캐시 확인
        if self._is_cache_valid(cache_key):
            return self.search_cache[cache_key]["data"]

        details = {
            "destination": destination,
            "travel_style": travel_style,
            "places": [],
            "restaurants": [],
            "accommodations": [],
            "activities": [],
        }

        try:
            # 여행 스타일에 따른 키워드 매핑
            style_keywords = self._get_style_keywords(travel_style)

            # 장소 검색
            places_query = f"{destination} 가볼만한곳 {style_keywords} 추천 명소"
            places_results = self.tavily_client.search(
                query=places_query, search_depth="basic", max_results=6
            )

            details["places"] = self._extract_places_from_search(
                places_results.get("results", []), destination
            )

            # 맛집 검색 (food 스타일이거나 기본적으로)
            if travel_style in ["food", "general"]:
                restaurants_query = f"{destination} 맛집 추천 현지음식"
                restaurants_results = self.tavily_client.search(
                    query=restaurants_query, search_depth="basic", max_results=4
                )

                details["restaurants"] = self._extract_restaurants_from_search(
                    restaurants_results.get("results", []), destination
                )

        except Exception as e:
            print(f"Detailed search error: {e}")
            details = self._get_fallback_destination_details(destination, travel_style)

        # 캐시 저장
        self._save_to_cache(cache_key, details)

        return details

    def _get_style_keywords(self, travel_style: str) -> str:
        """여행 스타일에 따른 검색 키워드"""
        keywords_map = {
            "culture": "문화재 박물관 전통 역사",
            "nature": "자연 공원 바다 산 힐링",
            "food": "맛집 음식 특산물 현지음식",
            "shopping": "쇼핑 시장 백화점 아울렛",
            "activity": "체험 액티비티 놀이공원 테마파크",
            "photo": "포토존 카페 예쁜곳 인스타그램",
            "general": "관광지 명소",
        }
        return keywords_map.get(travel_style, "관광지 명소")

    def _extract_destinations_from_search(
        self, search_results: List[Dict]
    ) -> List[Destination]:
        """검색 결과에서 여행지 정보 추출"""
        destinations = []

        # 검색 결과에서 한국 주요 여행지 매칭
        known_destinations = {
            "제주": {"name": "제주도", "region": "제주특별자치도", "type": "island"},
            "부산": {"name": "부산", "region": "부산광역시", "type": "coastal"},
            "경주": {"name": "경주", "region": "경상북도", "type": "historical"},
            "강릉": {"name": "강릉", "region": "강원도", "type": "coastal"},
            "여수": {"name": "여수", "region": "전라남도", "type": "coastal"},
            "전주": {"name": "전주", "region": "전라북도", "type": "cultural"},
            "안동": {"name": "안동", "region": "경상북도", "type": "historical"},
            "춘천": {"name": "춘천", "region": "강원도", "type": "nature"},
            "통영": {"name": "통영", "region": "경상남도", "type": "coastal"},
            "담양": {"name": "담양", "region": "전라남도", "type": "nature"},
        }

        found_destinations = set()

        for result in search_results:
            content = result.get("content", "") + " " + result.get("title", "")

            for key, dest_info in known_destinations.items():
                if key in content and dest_info["name"] not in found_destinations:
                    destinations.append(
                        Destination(
                            name=dest_info["name"],
                            region=dest_info["region"],
                            type=dest_info["type"],
                            description=self._extract_description_from_content(
                                content, dest_info["name"]
                            ),
                            popularity_score=self._calculate_popularity(
                                content, dest_info["name"]
                            ),
                            source_url=result.get("url", ""),
                        )
                    )
                    found_destinations.add(dest_info["name"])

        # 부족한 경우 기본 데이터로 보완
        if len(destinations) < 5:
            for fallback_dest in self.fallback_destinations:
                if fallback_dest.name not in found_destinations:
                    destinations.append(fallback_dest)
                    if len(destinations) >= 5:
                        break

        return sorted(destinations, key=lambda x: x.popularity_score, reverse=True)

    def _extract_places_from_search(
        self, search_results: List[Dict], destination: str
    ) -> List[Dict[str, Any]]:
        """검색 결과에서 장소 정보 추출"""
        places = []

        for i, result in enumerate(search_results[:8]):
            title = result.get("title", "")
            content = result.get("content", "")
            url = result.get("url", "")

            # 제목에서 장소명 추출 시도
            place_name = self._extract_place_name_from_title(title, destination)

            if place_name:
                places.append(
                    {
                        "name": place_name,
                        "category": self._categorize_place(title + content),
                        "description": self._extract_place_description(content)[:100],
                        "source_url": url,
                        "rating": None,  # Tavily에서는 평점 정보가 제한적
                        "address": self._extract_address(content),
                    }
                )

        # 기본 장소들로 보완 (검색 결과가 부족한 경우)
        if len(places) < 4:
            fallback_places = self._get_fallback_places(destination)
            places.extend(fallback_places[: 4 - len(places)])

        return places

    def _extract_restaurants_from_search(
        self, search_results: List[Dict], destination: str
    ) -> List[Dict[str, Any]]:
        """검색 결과에서 맛집 정보 추출"""
        restaurants = []

        for result in search_results[:6]:
            title = result.get("title", "")
            content = result.get("content", "")

            restaurant_name = self._extract_restaurant_name(title, destination)

            if restaurant_name:
                restaurants.append(
                    {
                        "name": restaurant_name,
                        "category": "맛집",
                        "description": self._extract_place_description(content)[:80],
                        "cuisine_type": self._extract_cuisine_type(title + content),
                        "source_url": result.get("url", ""),
                        "address": self._extract_address(content),
                    }
                )

        return restaurants

    def _extract_place_name_from_title(
        self, title: str, destination: str
    ) -> Optional[str]:
        """제목에서 장소명 추출"""
        if not title:
            return None

        # 일반적인 패턴들 제거
        noise_words = [
            "추천",
            "베스트",
            "가볼만한",
            "명소",
            "관광지",
            "여행",
            destination,
        ]

        cleaned_title = title
        for noise in noise_words:
            cleaned_title = cleaned_title.replace(noise, "")

        # 특수문자 및 숫자 제거 후 첫 번째 의미있는 단어 추출
        import re

        words = re.findall(r"[가-힣]+", cleaned_title)

        if words and len(words[0]) >= 2:
            return words[0]

        return None

    def _categorize_place(self, text: str) -> str:
        """텍스트 내용을 바탕으로 장소 카테고리 분류"""
        text_lower = text.lower()

        if any(word in text_lower for word in ["박물관", "미술관", "문화재", "궁"]):
            return "문화/역사"
        elif any(word in text_lower for word in ["해변", "바다", "산", "공원", "자연"]):
            return "자연/관광"
        elif any(word in text_lower for word in ["시장", "쇼핑", "백화점"]):
            return "쇼핑"
        elif any(word in text_lower for word in ["놀이공원", "테마파크", "체험"]):
            return "액티비티"
        elif any(word in text_lower for word in ["카페", "포토존", "예쁜"]):
            return "카페/감성"
        else:
            return "관광지"

    def _extract_place_description(self, content: str) -> str:
        """장소 설명 추출"""
        if not content:
            return "상세 정보를 확인해보세요."

        # 첫 번째 문장이나 의미있는 부분 추출
        sentences = content.split(".")
        for sentence in sentences:
            if len(sentence.strip()) > 20:
                return sentence.strip()

        return content[:100] + "..." if len(content) > 100 else content

    def _extract_address(self, content: str) -> Optional[str]:
        """주소 정보 추출"""
        import re

        # 한국 주소 패턴 매칭
        address_patterns = [
            r"[가-힣]+시\s+[가-힣]+구\s+[가-힣]+동",
            r"[가-힣]+도\s+[가-힣]+시\s+[가-힣]+구",
            r"[가-힣]+특별시\s+[가-힣]+구",
            r"[가-힣]+광역시\s+[가-힣]+구",
        ]

        for pattern in address_patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(0)

        return None

    def _extract_restaurant_name(self, title: str, destination: str) -> Optional[str]:
        """제목에서 음식점명 추출"""
        if not title or destination not in title:
            return None

        # 맛집, 음식점 등의 키워드가 있는 경우
        if any(
            word in title for word in ["맛집", "음식점", "식당", "카페", "레스토랑"]
        ):
            # 첫 번째 고유명사 추출
            import re

            korean_words = re.findall(r"[가-힣]+", title)

            for word in korean_words:
                if (
                    word not in ["맛집", "음식점", "식당", "추천", destination]
                    and len(word) >= 2
                ):
                    return word

        return None

    def _extract_cuisine_type(self, text: str) -> str:
        """음식 종류 추출"""
        cuisine_keywords = {
            "한식": ["한식", "국밥", "비빔밥", "김치", "불고기", "갈비"],
            "해산물": ["회", "조개", "생선", "해산물", "횟집", "수산"],
            "중식": ["중식", "짜장면", "짬뽕", "탕수육"],
            "일식": ["일식", "초밥", "라멘", "돈카츠", "우동"],
            "양식": ["양식", "파스타", "피자", "스테이크"],
            "카페": ["카페", "커피", "디저트", "케이크"],
            "분식": ["분식", "떡볶이", "김밥", "순대"],
        }

        for cuisine_type, keywords in cuisine_keywords.items():
            if any(keyword in text for keyword in keywords):
                return cuisine_type

        return "기타"

    def _extract_description_from_content(self, content: str, destination: str) -> str:
        """검색 결과에서 여행지 설명 추출"""
        sentences = content.split(".")

        for sentence in sentences:
            if destination in sentence and len(sentence.strip()) > 30:
                return sentence.strip()[:150] + "..."

        return f"{destination}의 아름다운 풍경과 독특한 매력을 경험해보세요."

    def _calculate_popularity(self, content: str, destination: str) -> float:
        """내용을 바탕으로 인기도 점수 계산"""
        popularity_keywords = ["인기", "유명", "추천", "베스트", "핫플", "명소"]
        score = 5.0  # 기본 점수

        for keyword in popularity_keywords:
            if keyword in content:
                score += 0.5

        # 특정 여행지의 기본 점수 조정
        base_scores = {
            "제주도": 9.0,
            "부산": 8.5,
            "서울": 8.8,
            "경주": 8.0,
            "강릉": 7.8,
            "여수": 7.5,
            "전주": 7.3,
        }

        return min(base_scores.get(destination, score), 10.0)

    def _get_fallback_destination_details(
        self, destination: str, travel_style: str
    ) -> Dict[str, Any]:
        """폴백 여행지 상세 정보"""

        fallback_places_db = {
            "제주도": [
                {
                    "name": "한라산",
                    "category": "자연/관광",
                    "description": "한국 최고봉의 웅장한 자연경관",
                },
                {
                    "name": "성산일출봉",
                    "category": "자연/관광",
                    "description": "유네스코 세계자연유산, 일출 명소",
                },
                {
                    "name": "협재해수욕장",
                    "category": "자연/관광",
                    "description": "에메랄드빛 바다와 하얀 모래사장",
                },
                {
                    "name": "흑돼지거리",
                    "category": "맛집",
                    "description": "제주 특산 흑돼지 맛집 거리",
                },
                {
                    "name": "카멜리아힐",
                    "category": "카페/감성",
                    "description": "동백꽃이 아름다운 수목원",
                },
            ],
            "부산": [
                {
                    "name": "해운대해수욕장",
                    "category": "자연/관광",
                    "description": "부산 대표 해변과 스카이라인",
                },
                {
                    "name": "감천문화마을",
                    "category": "문화/역사",
                    "description": "알록달록한 색채의 산복도로 마을",
                },
                {
                    "name": "광안대교",
                    "category": "자연/관광",
                    "description": "부산의 야경을 대표하는 현수교",
                },
                {
                    "name": "자갈치시장",
                    "category": "쇼핑",
                    "description": "한국 최대 수산물 시장",
                },
                {
                    "name": "태종대",
                    "category": "자연/관광",
                    "description": "기암절벽과 울창한 숲의 절경",
                },
            ],
            "경주": [
                {
                    "name": "불국사",
                    "category": "문화/역사",
                    "description": "신라 불교문화의 정수를 담은 사찰",
                },
                {
                    "name": "석굴암",
                    "category": "문화/역사",
                    "description": "본존불상이 모셔진 석굴 사원",
                },
                {
                    "name": "첨성대",
                    "category": "문화/역사",
                    "description": "동양에서 가장 오래된 천문대",
                },
                {
                    "name": "안압지",
                    "category": "문화/역사",
                    "description": "신라 왕궁의 별궁 연못",
                },
                {
                    "name": "황리단길",
                    "category": "카페/감성",
                    "description": "전통과 현대가 어우러진 거리",
                },
            ],
            "강릉": [
                {
                    "name": "경포해변",
                    "category": "자연/관광",
                    "description": "넓은 백사장과 소나무 숲의 조화",
                },
                {
                    "name": "오죽헌",
                    "category": "문화/역사",
                    "description": "율곡 이이의 생가이자 역사 유적",
                },
                {
                    "name": "안목해변",
                    "category": "카페/감성",
                    "description": "커피거리로 유명한 해변",
                },
                {
                    "name": "정동진",
                    "category": "자연/관광",
                    "description": "기차역에서 가장 가까운 바다",
                },
                {
                    "name": "초당순두부마을",
                    "category": "맛집",
                    "description": "강릉 대표 음식 순두부 맛집 집합소",
                },
            ],
            "여수": [
                {
                    "name": "여수밤바다",
                    "category": "자연/관광",
                    "description": "아름다운 야경으로 유명한 항구",
                },
                {
                    "name": "오동도",
                    "category": "자연/관광",
                    "description": "동백꽃이 피는 섬",
                },
                {
                    "name": "여수엑스포",
                    "category": "액티비티",
                    "description": "해양과학 체험 공간",
                },
                {
                    "name": "돌산대교",
                    "category": "자연/관광",
                    "description": "여수와 돌산을 연결하는 현수교",
                },
                {
                    "name": "해상케이블카",
                    "category": "액티비티",
                    "description": "바다 위를 가로지르는 케이블카",
                },
            ],
        }

        places = fallback_places_db.get(
            destination,
            [
                {
                    "name": f"{destination} 관광지",
                    "category": "관광지",
                    "description": f"{destination}의 대표 명소입니다.",
                }
            ],
        )

        return {
            "destination": destination,
            "travel_style": travel_style,
            "places": places,
            "restaurants": [place for place in places if place["category"] == "맛집"][
                :3
            ],
            "accommodations": [],
            "activities": [
                place for place in places if place["category"] == "액티비티"
            ][:2],
        }

    def _get_fallback_places(self, destination: str) -> List[Dict[str, Any]]:
        """폴백 장소 데이터"""
        details = self._get_fallback_destination_details(destination, "general")
        return details.get("places", [])

    def _is_cache_valid(self, cache_key: str) -> bool:
        """캐시 유효성 검사"""
        if cache_key not in self.search_cache:
            return False

        cache_time = self.search_cache[cache_key]["timestamp"]
        current_time = datetime.now().timestamp()

        return (current_time - cache_time) < self.cache_duration

    def _save_to_cache(self, cache_key: str, data: Any):
        """캐시에 데이터 저장"""
        self.search_cache[cache_key] = {
            "data": data,
            "timestamp": datetime.now().timestamp(),
        }

    async def search_accommodations(
        self, destination: str, budget: str, companion: str
    ) -> List[Dict[str, Any]]:
        """숙소 검색"""
        # 예산에 따른 숙소 타입 결정
        accommodation_types = {
            "budget": ["게스트하우스", "모텔", "호스텔"],
            "moderate": ["호텔", "펜션", "리조트"],
            "comfortable": ["특급호텔", "리조트", "풀빌라"],
            "luxury": ["럭셔리호텔", "프리미엄리조트", "풀빌라"],
            "unlimited": ["최고급호텔", "럭셔리리조트"],
        }

        # 동행자에 따른 추천 숙소
        companion_preferences = {
            "solo": ["싱글룸", "도미토리"],
            "couple": ["더블룸", "스위트룸"],
            "family": ["패밀리룸", "펜션"],
            "friends": ["트윈룸", "단체룸"],
            "group": ["단체숙소", "펜션"],
        }

        types = accommodation_types.get(budget, ["호텔"])
        preferences = companion_preferences.get(companion, ["스탠다드룸"])

        # 기본 숙소 추천 데이터
        accommodations = []
        for i, acc_type in enumerate(types[:3]):
            accommodations.append(
                {
                    "name": f"{destination} {acc_type}",
                    "type": acc_type,
                    "price_range": budget,
                    "description": f"{destination}의 편안한 {acc_type}",
                    "rating": 4.0 + (i * 0.3),
                    "amenities": preferences,
                }
            )

        return accommodations

    async def search_restaurants_by_style(
        self, destination: str, travel_style: str
    ) -> List[Dict[str, Any]]:
        """스타일별 맛집 검색"""
        cache_key = f"restaurants_{destination}_{travel_style}"

        if self._is_cache_valid(cache_key):
            return self.search_cache[cache_key]["data"]

        try:
            # 여행 스타일에 따른 맛집 검색
            style_keywords = {
                "food": "맛집 현지음식 특산물",
                "culture": "전통음식 향토음식",
                "nature": "자연식당 산장",
                "shopping": "푸드코트 먹거리",
                "activity": "간편식 패스트푸드",
                "photo": "예쁜카페 감성식당",
            }

            keyword = style_keywords.get(travel_style, "맛집")
            query = f"{destination} {keyword} 추천"

            results = self.tavily_client.search(
                query=query, search_depth="basic", max_results=6
            )

            restaurants = self._extract_restaurants_from_search(
                results.get("results", []), destination
            )

            self._save_to_cache(cache_key, restaurants)
            return restaurants

        except Exception as e:
            print(f"맛집 검색 오류: {e}")

        # 폴백 데이터
        return self._get_fallback_restaurants(destination, travel_style)

    def _get_fallback_restaurants(
        self, destination: str, travel_style: str
    ) -> List[Dict[str, Any]]:
        """폴백 맛집 데이터"""
        restaurant_db = {
            "제주도": [
                {
                    "name": "흑돼지 맛집",
                    "cuisine_type": "한식",
                    "description": "제주 특산 흑돼지 전문점",
                },
                {
                    "name": "해물탕 전문점",
                    "cuisine_type": "해산물",
                    "description": "신선한 제주 해산물 요리",
                },
                {
                    "name": "옥돔 구이집",
                    "cuisine_type": "해산물",
                    "description": "제주 대표 생선 옥돔 전문점",
                },
            ],
            "부산": [
                {
                    "name": "돼지국밥 원조집",
                    "cuisine_type": "한식",
                    "description": "부산 대표 음식 돼지국밥",
                },
                {
                    "name": "회센터",
                    "cuisine_type": "해산물",
                    "description": "자갈치 시장 신선한 회",
                },
                {
                    "name": "밀면 맛집",
                    "cuisine_type": "한식",
                    "description": "부산 향토음식 밀면 전문점",
                },
            ],
        }

        return restaurant_db.get(
            destination,
            [
                {
                    "name": f"{destination} 현지 음식점",
                    "cuisine_type": "한식",
                    "description": f"{destination}의 대표 음식",
                }
            ],
        )

    async def search_activities(
        self, destination: str, travel_style: str, companion: str
    ) -> List[Dict[str, Any]]:
        """액티비티 검색"""
        cache_key = f"activities_{destination}_{travel_style}_{companion}"

        if self._is_cache_valid(cache_key):
            return self.search_cache[cache_key]["data"]

        # 여행 스타일별 액티비티 키워드
        activity_keywords = {
            "culture": "박물관 문화체험 전통공예",
            "nature": "하이킹 트레킹 자연체험",
            "food": "요리체험 시장투어 와이너리",
            "shopping": "쇼핑몰 시장 아울렛",
            "activity": "스포츠 익스트림 체험활동",
            "photo": "포토스팟 전망대 카페",
        }

        # 동행자별 적합한 액티비티
        companion_activities = {
            "solo": "개인체험 명상 독립활동",
            "couple": "로맨틱 데이트 커플체험",
            "family": "가족체험 어린이 안전활동",
            "friends": "그룹활동 파티 모험",
            "group": "단체체험 팀빌딩 대형활동",
        }

        try:
            style_kw = activity_keywords.get(travel_style, "체험활동")
            companion_kw = companion_activities.get(companion, "")

            query = f"{destination} {style_kw} {companion_kw} 추천"

            results = self.tavily_client.search(
                query=query, search_depth="basic", max_results=8
            )

            activities = self._extract_activities_from_search(
                results.get("results", []), destination
            )

            self._save_to_cache(cache_key, activities)
            return activities

        except Exception as e:
            print(f"액티비티 검색 오류: {e}")

        # 폴백 데이터
        return self._get_fallback_activities(destination, travel_style, companion)

    def _extract_activities_from_search(
        self, search_results: List[Dict], destination: str
    ) -> List[Dict[str, Any]]:
        """검색 결과에서 액티비티 정보 추출"""
        activities = []

        for result in search_results[:8]:
            title = result.get("title", "")
            content = result.get("content", "")

            if any(
                keyword in title + content
                for keyword in ["체험", "투어", "활동", "놀이", "스포츠"]
            ):
                activity_name = self._extract_activity_name(title, destination)

                if activity_name:
                    activities.append(
                        {
                            "name": activity_name,
                            "type": self._categorize_activity(title + content),
                            "description": self._extract_place_description(content)[
                                :80
                            ],
                            "duration": self._estimate_activity_duration(
                                title + content
                            ),
                            "difficulty": self._estimate_difficulty(title + content),
                            "source_url": result.get("url", ""),
                        }
                    )

        return activities

    def _extract_activity_name(self, title: str, destination: str) -> Optional[str]:
        """제목에서 액티비티명 추출"""
        # 액티비티 키워드가 포함된 경우
        activity_keywords = ["체험", "투어", "관광", "놀이", "스포츠", "클래스"]

        for keyword in activity_keywords:
            if keyword in title:
                # 키워드 앞의 주요 단어 추출
                import re

                words = re.findall(r"[가-힣A-Za-z]+", title)

                for i, word in enumerate(words):
                    if keyword in word and i > 0:
                        return words[i - 1] + " " + word
                    elif keyword in word:
                        return word

        return None

    def _categorize_activity(self, text: str) -> str:
        """액티비티 카테고리 분류"""
        if any(word in text for word in ["스포츠", "서핑", "다이빙", "등반"]):
            return "스포츠"
        elif any(word in text for word in ["체험", "만들기", "클래스"]):
            return "체험활동"
        elif any(word in text for word in ["투어", "관광", "견학"]):
            return "관광투어"
        elif any(word in text for word in ["놀이", "게임", "엔터테인먼트"]):
            return "엔터테인먼트"
        else:
            return "기타활동"

    def _estimate_activity_duration(self, text: str) -> int:
        """액티비티 소요시간 추정 (분)"""
        if any(word in text for word in ["반나절", "4시간", "5시간"]):
            return 300  # 5시간
        elif any(word in text for word in ["하루", "종일", "8시간"]):
            return 480  # 8시간
        elif any(word in text for word in ["1시간", "단시간"]):
            return 60  # 1시간
        else:
            return 120  # 기본 2시간

    def _estimate_difficulty(self, text: str) -> str:
        """액티비티 난이도 추정"""
        if any(word in text for word in ["초급", "쉬운", "간단한", "어린이"]):
            return "쉬움"
        elif any(word in text for word in ["고급", "어려운", "전문", "익스트림"]):
            return "어려움"
        else:
            return "보통"

    def _get_fallback_activities(
        self, destination: str, travel_style: str, companion: str
    ) -> List[Dict[str, Any]]:
        """폴백 액티비티 데이터"""
        activities_db = {
            "제주도": [
                {
                    "name": "한라산 등반",
                    "type": "스포츠",
                    "description": "한국 최고봉 등반 체험",
                    "duration": 480,
                    "difficulty": "어려움",
                },
                {
                    "name": "승마 체험",
                    "type": "체험활동",
                    "description": "제주 조랑말과 함께하는 승마",
                    "duration": 120,
                    "difficulty": "보통",
                },
                {
                    "name": "감귤 따기",
                    "type": "체험활동",
                    "description": "제주 특산 감귤 수확 체험",
                    "duration": 90,
                    "difficulty": "쉬움",
                },
            ],
            "부산": [
                {
                    "name": "해변 서핑",
                    "type": "스포츠",
                    "description": "해운대에서 즐기는 서핑",
                    "duration": 180,
                    "difficulty": "보통",
                },
                {
                    "name": "야경 투어",
                    "type": "관광투어",
                    "description": "부산 야경 명소 투어",
                    "duration": 240,
                    "difficulty": "쉬움",
                },
                {
                    "name": "시장 투어",
                    "type": "관광투어",
                    "description": "자갈치 시장 음식 투어",
                    "duration": 150,
                    "difficulty": "쉬움",
                },
            ],
        }

        return activities_db.get(
            destination,
            [
                {
                    "name": f"{destination} 현지 체험",
                    "type": "체험활동",
                    "description": f"{destination}의 특색 체험",
                    "duration": 120,
                    "difficulty": "보통",
                }
            ],
        )
