"""Register a separate MCP server, leaving the independent StatStudio server intact."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


def install(client):
    executable = shutil.which(client)
    if not executable:
        raise RuntimeError(f'找不到 {client} CLI，請先安裝或選擇已安裝的另一個 AI。')
    config = (Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'config.toml'
              if client == 'codex' else Path.home() / '.claude.json')
    arguments = ['-m', 'statstudio', 'research-mcp']
    if client == 'claude' and config.exists():
        existing = json.loads(config.read_text(encoding='utf-8')).get('mcpServers', {}).get('statstudio-spss')
        if existing and existing.get('command') == sys.executable and existing.get('args') == arguments:
            print('Claude Code 的 statstudio-spss 已指向此環境；不需重複登錄。')
            return
    if config.exists():
        shutil.copy2(config, config.with_name(config.name + '.before-statstudio-spss-' + str(time.time_ns()) + '.bak'))
    if client == 'codex':
        command = [executable, 'mcp', 'add', 'statstudio-spss', '--', sys.executable, '-m', 'statstudio', 'research-mcp']
    else:
        if config.exists() and json.loads(config.read_text(encoding='utf-8')).get('mcpServers', {}).get('statstudio-spss'):
            subprocess.run([executable, 'mcp', 'remove', '--scope', 'user', 'statstudio-spss'], check=True)
        command = [executable, 'mcp', 'add', '--transport', 'stdio', '--scope', 'user', 'statstudio-spss', '--', sys.executable, '-m', 'statstudio', 'research-mcp']
    subprocess.run(command, check=True)
    if client == 'codex' and config.exists():
        content = config.read_text(encoding='utf-8')
        pattern = r'(?ms)^\[mcp_servers\.statstudio-spss\]\n.*?(?=^\[|\Z)'
        match = re.search(pattern, content)
        if match:
            block = match.group(0)
            for key, value in [('startup_timeout_sec', 60), ('tool_timeout_sec', 300)]:
                if re.search(rf'(?m)^{key}\s*=', block):
                    block = re.sub(rf'(?m)^{key}\s*=.*$', f'{key} = {value}', block)
                else:
                    block = block.rstrip() + f'\n{key} = {value}\n'
            content = content[:match.start()] + block + '\n' + content[match.end():]
            config.write_text(content, encoding='utf-8')
    print(f'已登錄 statstudio-spss 至 {client}。重新開啟該 AI 後，直接描述研究想法。')


def config_text():
    return json.dumps({'mcpServers': {'statstudio-spss': {'command': sys.executable, 'args': ['-m', 'statstudio', 'research-mcp']}}}, indent=2)
