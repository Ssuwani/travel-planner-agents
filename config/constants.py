"""
여행 플래너 상수 정의
"""

# 애플리케이션 설정
APP_TITLE = "AI 여행 플래너 🧳"
APP_ICON = "🗺️"
DEFAULT_PORT = 8501
DEFAULT_HOST = "localhost"

# 스타일 색상
THEME_COLORS = {
    "primary": "#2E86AB",
    "secondary": "#1976d2",
    "success": "#388e3c",
    "background": "#f8f9fa",
    "text": "#1a1a1a",
}

# 메시지
WELCOME_MESSAGE = """
안녕하세요! 🧳 AI 여행 플래너입니다.

저는 여러분의 완벽한 여행 계획을 만들어드리는 AI 어시스턴트예요.
어디로 여행을 떠나고 싶으신가요?
"""

ERROR_MESSAGES = {
    "no_openai_key": "⚠️ OPENAI_API_KEY가 설정되지 않았습니다.",
    "no_tavily_key": "⚠️ TAVILY_API_KEY가 설정되지 않았습니다.",
    "no_env_file": "⚠️ .env 파일이 없습니다.",
    "processing_error": "❌ 처리 중 오류가 발생했습니다.",
    "agent_error": "❌ 에이전트 실행 중 오류가 발생했습니다.",
}

# 스피너 메시지들
SPINNER_MESSAGES = {
    "default": "🤔 생각 중입니다...",
    "search": "🔍 최고의 여행지를 찾고 있어요...",
    "planning": "📋 완벽한 여행 계획을 세우고 있어요...",
    "calendar": "📅 캘린더에 일정을 추가하고 있어요...",
    "sharing": "📤 공유 준비를 하고 있어요...",
    "details": "🔍 상세 정보를 찾고 있어요...",
}

# API 관련
REQUIRED_ENV_VARS = ["OPENAI_API_KEY", "TAVILY_API_KEY"]
OPTIONAL_ENV_VARS = ["KAKAO_REST_API_KEY"]
