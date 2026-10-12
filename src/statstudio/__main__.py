import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import webbrowser


def main():
    parser = argparse.ArgumentParser(description='StatStudio AI：獨立統計與 AI 操作介面')
    sub = parser.add_subparsers(dest='command', required=True)
    serve = sub.add_parser('serve', help='開啟本機操作介面')
    serve.add_argument('--port', type=int, default=8765)
    serve.add_argument('--open', action='store_true')
    serve.add_argument('--research', action='store_true', help='開啟 SPSS 研究計畫與報告頁')
    sub.add_parser('mcp', help='執行 MCP stdio 服務')
    sub.add_parser('install-mcp', help='在 Codex 登錄這個 Python 環境的 MCP 服務')
    sub.add_parser('mcp-config', help='顯示可手動貼入 Codex 的 MCP 設定')
    sub.add_parser('research-mcp', help='研究助理：由 AI 透過 Python 操作本機 SPSS')
    sub.add_parser('research-status', help='檢查本機 SPSS 安裝與研究助理設定')
    research_install = sub.add_parser('install-research-mcp', help='登錄 SPSS 研究助理至 Codex 或 Claude Code')
    research_install.add_argument('--client', choices=['codex', 'claude'], default='codex')
    args = parser.parse_args()
    if args.command == 'research-mcp':
        from .research_mcp import build_research_mcp
        build_research_mcp().run(transport='stdio')
    elif args.command == 'research-status':
        from .research import ResearchWorkspace
        print(json.dumps(ResearchWorkspace().installation(), ensure_ascii=False, indent=2))
    elif args.command == 'install-research-mcp':
        from .research_install import install
        install(args.client)
    elif args.command == 'serve':
        if args.open:
            from urllib.request import urlopen
            from urllib.error import URLError
            address = f'http://127.0.0.1:{args.port}'
            page = '/research' if args.research else ''
            try:
                with urlopen(address + '/api/health', timeout=1) as response:
                    existing = json.load(response)
                if existing.get('app') == 'statstudio-ai':
                    webbrowser.open(address + page)
                    print('已開啟正在執行的 StatStudio AI。')
                    return
            except (URLError, OSError, ValueError):
                pass
        import uvicorn
        from .server import create_app
        if args.open:
            timer = threading.Timer(2, lambda: webbrowser.open(f'http://127.0.0.1:{args.port}' + ('/research' if args.research else '')))
            timer.daemon = True
            timer.start()
        uvicorn.run(create_app(), host='127.0.0.1', port=args.port)
    elif args.command == 'mcp':
        from .mcp_server import build_mcp
        build_mcp().run(transport='stdio')
    elif args.command == 'mcp-config':
        print('[mcp_servers.statstudio]\ncommand = ' + json.dumps(sys.executable) + '\nargs = ["-m", "statstudio", "mcp"]\nstartup_timeout_sec = 60\ntool_timeout_sec = 300')
    elif args.command == 'install-mcp':
        codex = shutil.which('codex')
        if not codex:
            parser.exit(1, '找不到 Codex CLI。請執行 python -m statstudio mcp-config，將設定加入 Codex 設定檔。\n')
        config = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'config.toml'
        if config.exists():
            import time
            backup = config.with_name('config.toml.before-statstudio-' + str(time.time_ns()) + '.bak')
            shutil.copy2(config, backup)
            print(f'設定備份：{backup}')
        subprocess.run([codex, 'mcp', 'add', 'statstudio', '--', sys.executable, '-m', 'statstudio', 'mcp'], check=True)
        if config.exists():
            import re
            text = config.read_text(encoding='utf-8')
            header = '[mcp_servers.statstudio]\n'
            match = re.search(r'(?ms)^\[mcp_servers\.statstudio\]\n.*?(?=^\[|\Z)', text)
            if match:
                block = match.group(0)
                additions = ''
                if 'startup_timeout_sec' not in block:
                    additions += 'startup_timeout_sec = 60\n'
                if 'tool_timeout_sec' not in block:
                    additions += 'tool_timeout_sec = 300\n'
                text = text.replace(header, header + additions, 1)
                config.write_text(text, encoding='utf-8')
        print('已登錄 statstudio。請重新啟動 Codex 以載入工具。')


if __name__ == '__main__':
    main()
