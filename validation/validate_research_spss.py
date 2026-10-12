"""Opt-in integration validation using licensed SPSS and synthetic data only.

Run: python validation/validate_research_spss.py --output <private-local-directory>
This exercises real MCP stdio, 18 native procedures, table reads and PNG content.
It does not claim to validate every statistical option or AI narrative accuracy.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import time

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def plan_for(paired=False):
    methods = [
        ('descriptive', {'variables': ['x', 'y']}),
        ('frequencies', {'variables': ['group', 'binary']}),
        ('crosstabs', {'row': 'group', 'column': 'binary'}),
        ('ttest_one', {'variables': ['x'], 'test_value': .25}),
        ('ttest_independent', {'variables': ['y'], 'group': 'binary', 'group_values': [0, 1]}),
        ('anova', {'variables': ['y'], 'group': 'group'}),
        ('correlation', {'variables': ['x', 'y', 'z']}),
        ('linear_regression', {'target': 'y', 'predictors': ['x', 'z']}),
        ('logistic_regression', {'target': 'binary', 'predictors': ['x', 'z']}),
        ('reliability', {'variables': ['item1', 'item2', 'item3']}),
        ('mann_whitney', {'variables': ['y'], 'group': 'binary', 'group_values': [0, 1]}),
        ('kruskal', {'variables': ['y'], 'group': 'group', 'group_values': [1, 3]}),
        ('pca', {'variables': ['item1', 'item2', 'item3'], 'components': 2}),
        ('factor', {'variables': ['item1', 'item2', 'item3'], 'components': 1}),
        ('kmeans', {'variables': ['x', 'z'], 'clusters': 3}),
        ('hierarchical', {'variables': ['x', 'z'], 'clusters': 3}),
    ] if not paired else [('ttest_paired', {'before': 'paired_a', 'after': 'paired_b'}),
                          ('wilcoxon', {'before': 'paired_a', 'after': 'paired_b'})]
    names = ['x', 'y', 'z', 'group', 'binary', 'paired_a', 'paired_b', 'item1', 'item2', 'item3']
    return {'question': '合成資料：驗證原生 SPSS 研究流程' if not paired else '合成示範：同一人前後分數是否不同？',
            'design': 'paired' if paired else 'exploratory', 'observation_unit': '一列代表一個合成受試者，前後量測位於同一列',
            'population': '60 筆合成紀錄，無真實個人', 'sampling_and_assignment': '固定亂數生成；沒有真實抽樣或隨機分派',
            'variables': [{'name': x, 'role': 'group' if x in ('group', 'binary') else 'outcome',
                           'kind': 'numeric', 'description': 'Synthetic variable ' + x, 'unit_or_codes': 'Synthetic numeric units'} for x in names],
            'analyses': [{'id': m, 'method': m, 'options': o, 'rationale': '驗證本機 SPSS 模板與資料往返',
                          'hypothesis': '技術測試，不作母體推論', 'primary': paired and m == 'ttest_paired'} for m, o in methods],
            'missing_data': '保留 SPSS 原生排除規則，回報實際 N', 'multiplicity': '這是技術驗證，不以多項 p 值挑選結論',
            'assumptions_to_check': ['正式研究需另外確認設計、抽樣與尺度；本案例僅為合成示範'],
            'limitations': ['沒有真實研究證據；不驗證所有 SPSS 選項'], 'unresolved_questions': []}


async def run(output, case='all'):
    output.mkdir(parents=True, exist_ok=True)
    params = StdioServerParameters(command=sys.executable, args=['-m', 'statstudio', 'research-mcp'],
                                  env=dict(os.environ, STATSTUDIO_HOME=str(output), PYTHONIOENCODING='utf-8'))
    report = {'started_at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'runs': [], 'errors': []}
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer, read_timeout_seconds=300) as session:
            await session.initialize()
            async def call(name, args):
                result = await session.call_tool(name, args)
                if result.is_error:
                    raise RuntimeError(str(result.content))
                return result.structured_content or json.loads(result.content[0].text)
            capabilities = await call('research_capabilities', {})
            report['installation'] = capabilities['installation']
            source = Path(__file__).resolve().parents[1] / 'src/statstudio/resources/demo.csv'
            dataset = await call('import_research_data', {'path': str(source)})
            for paired in ((False, True) if case == 'all' else (case == 'paired',)):
                study = await call('start_research', {'idea': 'SPSS research workflow integration validation (synthetic)'})
                plan = await call('save_research_plan', {'study_id': study['id'], 'plan': plan_for(paired)})
                check = await call('check_research_data', {'plan_id': plan['id'], 'dataset_id': dataset['id']})
                if not check['ready']:
                    raise RuntimeError(str(check['blockers']))
                result = await call('run_research', {'plan_id': plan['id'], 'dataset_id': dataset['id']})
                print(json.dumps({'run_id': result['id'], 'status': result['status'], 'paired': paired}, ensure_ascii=False), flush=True)
                saved = {'run_id': result['id'], 'status': result['status'], 'plan_id': plan['id'],
                         'spss_version': result['worker'].get('spss_version'), 'paths': result['paths'], 'analyses': []}
                report['runs'].append(saved)
                for analysis in result['analyses']:
                    chart_count = 0
                    numeric_cells = 0
                    for table in analysis['tables']:
                        offset = 0
                        while offset is not None:
                            part = await call('read_research_table', {'run_id': result['id'], 'table_id': table['id'], 'offset': offset})
                            numeric_cells += sum(c['number'] is not None for c in part['cells'])
                            offset = part['next_offset']
                    for chart in analysis['charts']:
                        viewed = await session.call_tool('view_research_chart', {'run_id': result['id'], 'chart_id': chart['id']})
                        assert not viewed.is_error and any(c.type == 'image' for c in viewed.content)
                        chart_count += 1
                    saved['analyses'].append({'method': analysis['method'], 'tables': len(analysis['tables']),
                                              'numeric_cells': numeric_cells, 'native_charts_received_via_mcp': chart_count,
                                              'messages': analysis['messages']})
                    assert numeric_cells > 0, analysis['method']
                if result['status'] != 'completed':
                    report['errors'].append(result['worker'])
                (output / 'integration-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if report['errors']:
        raise SystemExit('One or more native procedures failed. See integration-report.json.')
    count = sum(len(r['analyses']) for r in report['runs'])
    print(f'PASSED: {count} native methods, MCP table pagination and native chart image transport.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', choices=['all', 'paired', 'independent'], default='all')
    args = parser.parse_args()
    asyncio.run(run(args.output.resolve(), args.case))
