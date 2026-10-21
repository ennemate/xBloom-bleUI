import os
import sys
import webbrowser
import subprocess
import time
import argparse
import threading
DEFAULT_PORT = 8000
DEFAULT_HOST = '0.0.0.0'

def parse_args():
    parser = argparse.ArgumentParser(description='xBloom bleUI Launcher', epilog='Examples: python run.py 8080  or  python run.py -p 8080')
    parser.add_argument('pos_port', nargs='?', type=int, default=None, help='Server port number (optional)')
    parser.add_argument('-p', '--port', type=int, default=None, help=f'Server port number (default: {DEFAULT_PORT})')
    parser.add_argument('--host', type=str, default=DEFAULT_HOST, help=f'Host address to bind (default: {DEFAULT_HOST})')
    parser.add_argument('--no-browser', action='store_true', help='Disable automatic browser open')
    args, extra_args = parser.parse_known_args()
    chosen_port = args.port or args.pos_port or int(os.environ.get('PORT', DEFAULT_PORT))
    return (chosen_port, args.host, args.no_browser, extra_args)

def main():
    port, host, no_browser, extra_args = parse_args()
    print('=' * 55)
    print('  xBloom bleUI Launcher')
    print(f'  - Web Dashboard : http://localhost:{port}')
    print(f'  - Custom Port   : python run.py [port]  (e.g. python run.py 8080)')
    print('=' * 55)
    server_path = os.path.join(os.path.dirname(__file__), 'server.py')
    if not no_browser:

        def open_browser():
            time.sleep(1.2)
            webbrowser.open(f'http://localhost:{port}')
        threading.Thread(target=open_browser, daemon=True).start()
    cmd = [sys.executable, server_path, '--host', host, '--port', str(port)] + extra_args
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print('\n[xBloom bleUI] Server terminated cleanly.')
if __name__ == '__main__':
    main()
