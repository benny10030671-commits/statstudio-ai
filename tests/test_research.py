import asyncio
from contextlib import nullcontext
import json
import os
from pathlib import Path
import sys

import pandas as pd
import pyreadstat
import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from statstudio.research import ResearchWorkspace, engine_lock
from statstudio.spss_output import parse_output, render_report
from statstudio.spss_syntax import build, normalize, quote
from statstudio.store import write_json


def example_plan():
    return {'question': 'Does outcome differ between two independent groups?', 'design': 'independent',
            'observation_unit': 'One participant per row', 'population': 'Synthetic demonstration only',
            'sampling_and_assignment': 'Synthetic independent records; no causal interpretation',
            'variables': [
                {'name': 'ID', 'role': 'id', 'kind': 'numeric', 'description': 'Unique participant', 'unit_or_codes': 'Integer'},
                {'name': '組別', 'role': 'group', 'kind': 'categorical', 'description': 'Group', 'unit_or_codes': '0=control; 1=training'},
                {'name': '分數', 'role': 'outcome', 'kind': 'numeric', 'description': 'Outcome', 'unit_or_codes': 'Points'}],
            'analyses': [{'id': 'comparison', 'method': 'ttest_independent',
                          'options': {'variables': ['分數'], 'group': '組別', 'group_values': [0, 1]},
                          'rationale': 'Two independent numeric outcomes', 'hypothesis': 'Means differ', 'primary': True}],
            'missing_data': 'SPSS per-analysis exclusion; report actual N',
            'multiplicity': 'One primary contrast', 'assumptions_to_check': ['Independence and distribution'],
            'limitations': ['Synthetic only'], 'unresolved_questions': []}


def prepared(tmp_path):
    workspace = ResearchWorkspace(tmp_path)
    study = workspace.start('Compare two groups')
    plan = workspace.save_plan(study['id'], example_plan())
    source = tmp_path / 'example.csv'
    pd.DataFrame({'ID': [1, 2, 3, 4, 5, 6], '組別': [0, 0, 0, 1, 1, 1],
                  '分數': [2.3, 3.1, 2.5, 4.1, 5.0, 4.4]}).to_csv(source, index=False)
    data = workspace.import_data(str(source))
    return workspace, study, plan, data, source


def test_idea_plan_template_and_data_roundtrip(tmp_path):
    w, study, plan, data, source = prepared(tmp_path)
    assert Path(plan['template_path']).read_text(encoding='utf-8-sig').strip() == 'ID,組別,分數'
    assert data['mapping']['分數'] == 'v003'
    assert w.check(plan['id'], data['id'])['ready']
    revised = w.save_plan(study['id'], example_plan())
    assert plan['id'] != revised['id']
    assert len(w.list_studies()) == 1
    assert w.data(data['id'])[1]['分數'].iloc[0] == 2.3
    native = w.folder('datasets', data['id']) / 'data.sav'
    native.write_bytes(native.read_bytes() + b'changed')
    with pytest.raises(ValueError, match='SHA-256'):
        w.check(plan['id'], data['id'])


def test_preflight_blocks_unresolved_duplicate_ids_and_extra_groups(tmp_path):
    w, study, plan, data, source = prepared(tmp_path)
    bad = example_plan()
    bad['unresolved_questions'] = ['Are the observations independent?']
    revised = w.save_plan(study['id'], bad)
    assert not w.check(revised['id'], data['id'])['ready']
    df = pd.read_csv(source)
    df.loc[1, 'ID'] = df.loc[0, 'ID']
    df.loc[5, '組別'] = 2
    df.to_csv(source, index=False)
    imported = w.import_data(str(source))
    checked = w.check(plan['id'], imported['id'])
    assert any('ID' in x for x in checked['blockers'])
    assert any('group_values' in x for x in checked['blockers'])


def test_sav_user_missing_is_preserved(tmp_path):
    path = tmp_path / 'original.sav'
    pyreadstat.write_sav(pd.DataFrame({'score': [1., 2., 999., 3.]}), str(path), missing_ranges={'score': [999.]})
    w = ResearchWorkspace(tmp_path)
    info = w.import_data(str(path))
    assert info['columns'][0]['missing'] == 1
    assert info['missing_ranges']['score'][0]['lo'] == 999
    assert (w.folder('datasets', info['id']) / 'data.sav').read_bytes() == path.read_bytes()
    assert w.data(info['id'])[1]['score'].isna().sum() == 1


def test_blank_text_is_native_user_missing(tmp_path):
    path = tmp_path / 'text.csv'
    path.write_text('name,score\nA,1\n,2\nB,3\n', encoding='utf-8')
    info = ResearchWorkspace(tmp_path).import_data(str(path))
    assert info['columns'][0]['missing'] == 1


def test_plan_rejects_unknown_option_and_paired_independence_mismatch(tmp_path):
    w = ResearchWorkspace(tmp_path)
    study = w.start('An idea')
    plan = example_plan()
    plan['analyses'][0]['options']['weights'] = 'ID'
    with pytest.raises(ValueError, match='allowed'):
        w.save_plan(study['id'], plan)
    plan = example_plan()
    plan['design'] = 'paired'
    with pytest.raises(ValueError, match='成對'):
        w.save_plan(study['id'], plan)


@pytest.mark.parametrize('bad', ['x.\nHOST COMMAND', 'x /EXEC', "x'", 'x y'])
def test_syntax_injection_is_rejected(bad):
    with pytest.raises(ValueError):
        build('descriptive', {'variables': ['chosen']}, {'chosen': bad})


def test_literal_column_names_are_mapped_and_paths_quoted():
    command = build('descriptive', {'variables': ['<script>.exec'], 'plots': False}, {'<script>.exec': 'v001'})
    assert '<script>' not in command[0]
    assert 'v001' in command[0]
    assert quote("C:/O'Brien/data.sav") == "'C:/O''Brien/data.sav'"
    with pytest.raises(ValueError):
        normalize('ttest_one', {'variables': ['x'], 'test_value': float('nan')})


def test_paired_contrasts_use_spss_specific_order():
    mapping = {'pre': 'v001', 'post': 'v002'}
    opts = {'before': 'pre', 'after': 'post', 'plots': False}
    assert 'v002 WITH v001' in build('ttest_paired', opts, mapping)[0]
    # SPSS NPAR labels the difference in the reverse order of its arguments.
    assert 'v001 WITH v002' in build('wilcoxon', opts, mapping)[0]


def test_research_dashboard_is_local_and_serves_only_known_artifacts(tmp_path):
    from fastapi.testclient import TestClient
    from statstudio.server import create_app
    w, study, plan, data, source = prepared(tmp_path)
    client = TestClient(create_app(tmp_path), base_url='http://127.0.0.1')
    assert client.get('/research').status_code == 200
    index = client.get('/api/research').json()
    assert index['plans'][0]['id'] == plan['id']
    assert client.get('/api/research/plans/' + plan['id'] + '/template').status_code == 200
    assert client.get('/api/research/plans/' + plan['id'] + '/original').status_code == 400
    assert client.get('/api/research', headers={'Origin': 'https://example.com'}).status_code == 403
    assert client.get('/api/research/runs/' + 'a'*32 + '/report?interpretation=..').status_code == 400


def test_oxml_precision_missing_footnotes_and_html_escape(tmp_path):
    xml = tmp_path / 'result.xml'
    xml.write_text('''<outputTree><command command="Regression"><pivotTable subType="Coefficients" text="&lt;script&gt;">
      <footnote><note text="Dependent variable: y"/></footnote><category text="x"><category text="Sig.">
      <cell number="0.000123456789" text=".000"/></category><category text="undefined"><cell null="true" text="."/></category></category>
      </pivotTable></command></outputTree>''', encoding='utf-8')
    parsed = parse_output(xml, 'model')
    table = parsed['tables'][0]
    assert table['cells'][0]['number_raw'] == '0.000123456789'
    assert table['cells'][1]['number'] is None
    assert table['notes'] == ['Dependent variable: y']
    result = {'id': 'run', 'plan_id': 'plan', 'status': 'completed', 'dataset': {'sha256': 'abc'},
              'plan': {'question': '<script>alert(1)</script>', 'observation_unit': 'one', 'sampling_and_assignment': 'synthetic'},
              'analyses': [dict(parsed, id='model', method='regression')]}
    html = render_report(result)
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert '0.000123456789' in html and 'model:t1:c1' in html


def test_chart_path_cannot_escape_run(tmp_path):
    xml = tmp_path / 'result.xml'
    xml.write_text('<outputTree><chart imageFile="../outside.png"/></outputTree>')
    with pytest.raises(ValueError, match='escapes'):
        parse_output(xml, 'a')


def test_interpretation_requires_existing_evidence(tmp_path):
    w = ResearchWorkspace(tmp_path)
    run_id = 'a' * 32
    folder = w.folder('runs', run_id)
    folder.mkdir(parents=True)
    write_json(folder / 'result.json', {'status': 'completed', 'analyses': [{'tables': [], 'charts': []}]})
    interpretation = {'summary': 'A finding', 'findings': [{'text': 'Invented', 'evidence': ['fake:t1:c1']}],
                      'assumptions_review': 'Not checked', 'limitations': ['Unknown'], 'next_steps': ['Review'], 'author': 'test'}
    with pytest.raises(ValueError, match='Unknown evidence'):
        w.save_interpretation(run_id, interpretation)


def test_worker_failure_is_retained_and_cannot_be_interpreted(tmp_path, monkeypatch):
    import statstudio.research as module
    w, study, plan, data, source = prepared(tmp_path)
    monkeypatch.setattr(w, 'installation', lambda: {'available': True, 'supported_platform': True,
                                                   'python': sys.executable, 'spss_home': str(tmp_path)})
    monkeypatch.setattr(module, 'engine_lock', lambda *args, **kwargs: nullcontext())
    class FailedWorker:
        returncode = 1
        def __init__(self, *args, **kwargs):
            pass
        def wait(self, timeout):
            return self.returncode
    monkeypatch.setattr(module.subprocess, 'Popen', FailedWorker)
    result = w.run(plan['id'], data['id'])
    assert result['status'] == 'failed'
    assert 'without a status' in result['worker']['error']
    assert Path(result['paths']['json']).exists() and Path(result['paths']['syntax']).exists()
    with pytest.raises(ValueError, match='Failed runs'):
        w.save_interpretation(result['id'], {})


def test_engine_lock_serializes_and_releases(tmp_path):
    path = tmp_path / 'engine.lock'
    with engine_lock(path):
        with pytest.raises(TimeoutError):
            with engine_lock(path, timeout=.05):
                pass
    with engine_lock(path, timeout=.05):
        pass


def test_claude_registration_is_idempotent(tmp_path, monkeypatch):
    import statstudio.research_install as installer
    monkeypatch.setattr(installer.Path, 'home', lambda: tmp_path)
    monkeypatch.setattr(installer.shutil, 'which', lambda name: 'claude.exe')
    config = tmp_path / '.claude.json'
    original = {'unrelated': {'keep': True}, 'mcpServers': {'statstudio-spss': {'command': sys.executable,
                'args': ['-m', 'statstudio', 'research-mcp']}}}
    config.write_text(json.dumps(original), encoding='utf-8')
    def unexpected(*args, **kwargs):
        raise AssertionError('An already configured server must not be removed or re-added.')
    monkeypatch.setattr(installer.subprocess, 'run', unexpected)
    installer.install('claude')
    assert json.loads(config.read_text(encoding='utf-8')) == original


def test_research_mcp_handshake_plan_schema_and_blocking(tmp_path):
    async def scenario():
        params = StdioServerParameters(command=sys.executable, args=['-m', 'statstudio', 'research-mcp'],
                                      env=dict(os.environ, STATSTUDIO_HOME=str(tmp_path), PYTHONIOENCODING='utf-8'))
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer, read_timeout_seconds=45) as session:
                initialized = await session.initialize()
                assert initialized.server_info.name == 'StatStudio SPSS Research Assistant'
                tools = await session.list_tools()
                assert len(tools.tools) == 12
                async def call(name, arguments):
                    result = await session.call_tool(name, arguments)
                    assert not result.is_error, result
                    return result.structured_content or json.loads(result.content[0].text)
                study = await call('start_research', {'idea': 'Compare training groups'})
                assert study['intake']['questions']
                plan = example_plan()
                plan['unresolved_questions'] = ['Is this independent or paired?']
                saved = await call('save_research_plan', {'study_id': study['id'], 'plan': plan})
                assert Path(saved['template_path']).exists()
                capabilities = await call('research_capabilities', {})
                assert len(capabilities['methods']) == 18
                prompts = await session.list_prompts()
                assert prompts.prompts[0].name == 'research_assistant'
    asyncio.run(scenario())
