import os
import sys
import webbrowser
import subprocess
import time
import argparse
import threading

DEFAULT_PORT = 8000
DEFAULT_HOST = "0.0.0.0"

def parse_args():
    parser = argparse.ArgumentParser(
        description="xBloom bleUI v0.8.8 Launcher",
        epilog="예시: python run.py 8080  또는  python run.py -p 8080"
    )
    # 위치 인자(선택사항)로 포트 번호 입력 허용 (예: python run.py 8080)
    parser.add_argument("pos_port", nargs="?", type=int, default=None, help="서버 포트 번호 (선택)")
    parser.add_argument("-p", "--port", type=int, default=None, help=f"서버 포트 번호 (기본값: {DEFAULT_PORT})")
    parser.add_argument("--host", type=str, default=DEFAULT_HOST, help=f"호스트 주소 (기본값: {DEFAULT_HOST})")
    parser.add_argument("--no-browser", action="store_true", help="브라우저 자동 오픈 비활성화")
    
    args, extra_args = parser.parse_known_args()
    
    # 포트 우선순위: --port > 위치 인자 > 환경변수 PORT > 기본값
    chosen_port = args.port or args.pos_port or int(os.environ.get("PORT", DEFAULT_PORT))
    return chosen_port, args.host, args.no_browser, extra_args

def main():
    port, host, no_browser, extra_args = parse_args()
    
    print("=" * 55)
    print("  xBloom bleUI v0.8.8 런처")
    print(f"  - 웹 대시보드 URL : http://localhost:{port}")
    print(f"  - 포트 변경 방법   : python run.py [포트번호]  (예: python run.py 8080)")
    print("=" * 55)

    server_path = os.path.join(os.path.dirname(__file__), "server.py")
    
    if not no_browser:
        def open_browser():
            time.sleep(1.2)
            webbrowser.open(f"http://localhost:{port}")
        threading.Thread(target=open_browser, daemon=True).start()

    cmd = [sys.executable, server_path, "--host", host, "--port", str(port)] + extra_args
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n[xBloom bleUI] 서버가 정상 종료되었습니다.")

if __name__ == "__main__":
    main()
