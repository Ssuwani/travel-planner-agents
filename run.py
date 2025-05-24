#!/usr/bin/env python3
"""
AI 여행 플래너 실행 스크립트
"""

import os
import subprocess
import sys
from pathlib import Path


def check_python_version():
    """Python 버전 확인"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 이상이 필요합니다.")
        print(f"현재 버전: {sys.version}")
        return False

    print(f"✅ Python 버전: {sys.version.split()[0]}")
    return True


def check_env_file():
    """환경 변수 파일 확인"""
    env_file = Path(".env")

    if not env_file.exists():
        print("⚠️ .env 파일이 없습니다.")
        print("필요한 환경 변수를 설정해주세요:")
        print("- OPENAI_API_KEY: OpenAI API 키")
        print("- TAVILY_API_KEY: Tavily 검색 API 키")
        print("- KAKAO_REST_API_KEY: 카카오톡 공유용 API 키 (선택사항)")
        return False

    # 필수 환경 변수 확인
    try:
        from dotenv import load_dotenv

        load_dotenv()

        openai_key = os.getenv("OPENAI_API_KEY")
        tavily_key = os.getenv("TAVILY_API_KEY")

        if not openai_key:
            print("⚠️ OPENAI_API_KEY가 설정되지 않았습니다.")
            return False

        if not tavily_key:
            print("⚠️ TAVILY_API_KEY가 설정되지 않았습니다.")
            return False

        print("✅ 환경 변수 파일이 준비되었습니다.")
        return True

    except ImportError:
        print("❌ python-dotenv가 설치되지 않았습니다.")
        print("다음 명령어로 설치하세요: poetry install")
        return False


def check_poetry():
    """Poetry 설치 및 의존성 확인"""
    try:
        result = subprocess.run(["poetry", "--version"], capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ Poetry가 설치되지 않았습니다.")
            print("Poetry 설치: https://python-poetry.org/docs/#installation")
            return False

        print("✅ Poetry가 설치되어 있습니다.")

        # 의존성 체크
        result = subprocess.run(["poetry", "check"], capture_output=True, text=True)
        if result.returncode != 0:
            print("⚠️ 의존성을 설치해주세요: poetry install")
            return False

        print("✅ 의존성이 설치되어 있습니다.")
        return True

    except FileNotFoundError:
        print("❌ Poetry가 설치되지 않았습니다.")
        print("Poetry 설치: https://python-poetry.org/docs/#installation")
        return False


def run_streamlit():
    """Streamlit 애플리케이션 실행"""
    print("🚀 AI 여행 플래너를 시작합니다...")
    print("브라우저에서 http://localhost:8501로 접속하세요.")
    print("종료하려면 Ctrl+C를 누르세요.")
    print("-" * 50)

    try:
        subprocess.run(
            [
                "poetry",
                "run",
                "streamlit",
                "run",
                "app.py",
                "--server.address",
                "localhost",
                "--server.port",
                "8501",
                "--theme.base",
                "light",
            ]
        )
    except KeyboardInterrupt:
        print("\n👋 AI 여행 플래너를 종료합니다.")
    except Exception as e:
        print(f"❌ 실행 중 오류 발생: {e}")


def main():
    """메인 함수"""
    print("=" * 50)
    print("🧳 AI 여행 플래너 - 멀티 에이전트 시스템")
    print("=" * 50)

    # 시스템 요구사항 확인
    if not check_python_version():
        return

    if not check_poetry():
        return

    if not check_env_file():
        print("\n환경 설정을 완료한 후 다시 실행해주세요.")
        return

    print("✅ 모든 준비가 완료되었습니다!")
    print()

    # Streamlit 애플리케이션 실행
    run_streamlit()


if __name__ == "__main__":
    main()
