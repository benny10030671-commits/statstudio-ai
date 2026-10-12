import asyncio
import json
import os
import sys
from pathlib import Path
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def test_real_stdio_handshake_and_analysis(tmp_path):
    async def scenario():
        env = dict(os.environ, STATSTUDIO_HOME=str(tmp_path), PYTHONIOENCODING='utf-8')
        params = StdioServerParameters(command=sys.executable, args=['-m', 'statstudio', 'mcp'], env=env)
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer, read_timeout_seconds=45) as session:
                initialized = await session.initialize()
                assert initialized.server_info.name == 'StatStudio AI'
                tools = await session.list_tools()
                names = {tool.name for tool in tools.tools}
                assert {'list_methods', 'get_validation_status', 'import_dataset', 'load_demo', 'inspect_dataset', 'run_analysis', 'read_result'} <= names
                validation = await session.call_tool('get_validation_status', {})
                status = validation.structured_content or json.loads(validation.content[0].text)
                assert status['fully_spss_compatible'] is False
                assert status['engine_matches_validated_source'] is True
                loaded = await session.call_tool('load_demo', {})
                assert not loaded.is_error
                data = loaded.structured_content or json.loads(loaded.content[0].text)
                analyzed = await session.call_tool('run_analysis', {'dataset_id': data['id'], 'method': 'linear_regression', 'options': {'target': 'y', 'predictors': ['x', 'z']}})
                assert not analyzed.is_error, analyzed
                result = analyzed.structured_content or json.loads(analyzed.content[0].text)
                assert result['details']['n_used'] == 60
                assert Path(result['report_path']).is_file()
                assert result['compatibility']['status'] == 'unverified_for_this_dataset'
                bad = await session.call_tool('run_analysis', {'dataset_id': data['id'], 'method': 'descriptive', 'options': {'variables': ['x'], 'weights': 'z'}})
                assert bad.is_error
    asyncio.run(scenario())
