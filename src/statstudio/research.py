"""Local, versioned research plans and runs backed by the actual SPSS engine."""
from contextlib import contextmanager
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid

import numpy as np
import pandas as pd
import pyreadstat

from .research_models import INTAKE, Interpretation, ResearchPlan
from .spss_output import parse_output, render_report
from .spss_syntax import LIST_ROLES, SINGLE_ROLES, build, normalize, quote, used_columns, variable
from .store import MAX_BYTES, MAX_COLUMNS, MAX_ROWS, Store, clean, now, write_json


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@contextmanager
def engine_lock(path, timeout=20):
    """OS-held lock works across MCP/web processes and releases on process exit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        deadline = time.monotonic() + timeout
        acquired = False
        try:
            while not acquired:
                handle.seek(0)
                try:
                    if os.name == 'nt':
                        import msvcrt
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Another SPSS research run is active; retry after it finishes.')
                    time.sleep(.2)
            yield
        finally:
            if acquired:
                handle.seek(0)
                if os.name == 'nt':
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class ResearchWorkspace:
    def __init__(self, root=None):
        home = Path(root or os.environ.get('STATSTUDIO_HOME') or Path.home() / '.statstudio')
        self.root = (home / 'research').resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def folder(self, kind, identifier):
        return self.root / kind / Store.valid_id(identifier)

    def start(self, idea):
        if not isinstance(idea, str) or not 1 <= len(idea.strip()) <= 12000:
            raise ValueError('請描述研究想法（1–12,000 字元）。')
        identifier = uuid.uuid4().hex
        folder = self.folder('studies', identifier)
        folder.mkdir(parents=True)
        study = {'id': identifier, 'idea': idea, 'created_at': now()}
        write_json(folder / 'study.json', study)
        return dict(study, intake=INTAKE, next_step='AI 先釐清研究設計，再 save_research_plan；尚未執行任何統計。')

    def list_studies(self):
        return [read_json(p) for p in sorted((self.root / 'studies').glob('*/study.json'), key=lambda p: p.stat().st_mtime, reverse=True)]

    def overview(self):
        plans = []
        for p in (self.root / 'plans').glob('*/plan.json'):
            record = read_json(p)
            plans.append({k: record[k] for k in ('id', 'study_id', 'created_at')} | {'question': record['plan']['question']})
        runs = []
        for p in (self.root / 'runs').glob('*/result.json'):
            r = read_json(p)
            interpretations = sorted(p.parent.glob('interpretations/*/interpretation.json'), key=lambda p: p.stat().st_mtime, reverse=True)
            runs.append({k: r[k] for k in ('id', 'study_id', 'plan_id', 'status', 'created_at')} |
                        {'question': r['plan']['question'], 'analyses': len(r['analyses']),
                         'charts': sum(len(a['charts']) for a in r['analyses']),
                         'interpretation_id': interpretations[0].parent.name if interpretations else None})
        return {'installation': self.installation(), 'studies': self.list_studies(),
                'plans': sorted(plans, key=lambda x: x['created_at'], reverse=True),
                'runs': sorted(runs, key=lambda x: x['created_at'], reverse=True)}

    def save_plan(self, study_id, plan):
        study_folder = self.folder('studies', study_id)
        read_json(study_folder / 'study.json')
        plan = ResearchPlan.model_validate(plan).model_dump()
        names = {x['name'] for x in plan['variables']}
        for name in names:
            if any(ord(c) < 32 for c in name) or name.startswith(('=', '+', '-', '@')):
                raise ValueError('欄名不可含控制字元或試算表公式前綴。')
        for analysis in plan['analyses']:
            analysis['options'] = normalize(analysis['method'], analysis['options'])
            if set(used_columns(analysis['options'])) - names:
                raise ValueError('分析中引用的欄位必須先列入資料字典。')
            if analysis['method'] in ('ttest_paired', 'wilcoxon') and plan['design'] != 'paired':
                raise ValueError('成對方法需要明確的 paired 設計。')
            if plan['design'] == 'paired' and analysis['method'] in ('ttest_independent', 'anova', 'mann_whitney', 'kruskal', 'linear_regression', 'logistic_regression'):
                raise ValueError('本版不將成對/重複量測直接套入獨立樣本模型。')
        identifier = uuid.uuid4().hex
        folder = self.folder('plans', identifier)
        folder.mkdir(parents=True)
        record = {'id': identifier, 'study_id': study_id, 'created_at': now(), 'plan': plan}
        write_json(folder / 'plan.json', record)
        with (folder / 'data-template.csv').open('w', encoding='utf-8-sig', newline='') as f:
            csv.writer(f).writerow([x['name'] for x in plan['variables']])
        with (folder / 'data-dictionary.csv').open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['欄位', '角色', '型態', '說明', '單位或編碼', '必要'])
            for v in plan['variables']:
                # Spreadsheet-safe descriptive text, while template preserves exact names.
                row = [v['name'], v['role'], v['kind'], v['description'], v['unit_or_codes'], v['required']]
                writer.writerow(["'" + x if isinstance(x, str) and x.startswith(('=', '+', '-', '@')) else x for x in row])
        return dict(record, template_path=str(folder / 'data-template.csv'), dictionary_path=str(folder / 'data-dictionary.csv'))

    def import_data(self, path):
        source = Path(path).expanduser().resolve()
        if not source.is_file() or not 0 < source.stat().st_size <= MAX_BYTES:
            raise ValueError('資料檔必須存在，且不超過 25 MB。')
        suffix = source.suffix.lower()
        if suffix not in ('.csv', '.tsv', '.xlsx', '.sav', '.zsav'):
            raise ValueError('支援 CSV、TSV、XLSX、SAV、ZSAV。')
        identifier = uuid.uuid4().hex
        folder = self.folder('datasets', identifier)
        folder.mkdir(parents=True)
        original = folder / ('original' + suffix)
        shutil.copyfile(source, original)
        native = folder / 'data.sav'
        notes = ['每次執行明確關閉 WEIGHT、FILTER、SPLIT FILE；本版不支援這些設定。']
        if suffix in ('.sav', '.zsav'):
            # Keep the original SPSS file bytes and dictionary, including user missings.
            shutil.copyfile(original, native)
            _, meta = pyreadstat.read_sav(str(native), metadataonly=True, user_missing=True)
            mapping = {name: name for name in meta.column_names}
            for name in mapping:
                variable(name)
            notes.append('保留原始 SAV 的變數標籤、值標籤與使用者定義缺失值；SPSS 原生程序處理缺失。')
        else:
            # Conversion is temporary; nesting a second persistent store here also
            # exceeds classic Windows path limits for ordinary long project paths.
            with tempfile.TemporaryDirectory(prefix='statstudio-convert-') as temp:
                staging = Store(temp)
                info = staging.import_bytes(source.name, original.read_bytes())
                frame = staging.frame(info['id'])
            mapping = {name: f'v{i + 1:03d}' for i, name in enumerate(frame.columns)}
            missing = {}
            for name in frame.columns:
                if pd.api.types.is_datetime64_any_dtype(frame[name]):
                    raise ValueError('日期欄請先明確轉換為所需的數值或類別。')
                if not pd.api.types.is_numeric_dtype(frame[name]):
                    if any(not isinstance(x, str) for x in frame[name].dropna()):
                        raise ValueError(f'{name} 含混合型態，請先明確清理。')
                    frame[name] = frame[name].fillna('')
                    missing[mapping[name]] = ['']
            converted = frame.rename(columns=mapping)
            pyreadstat.write_sav(converted, str(native), column_labels={mapping[x]: x for x in mapping}, missing_ranges=missing)
            notes += info['notes'] + ['CSV/XLSX 欄位映射為安全 SPSS 名稱，原欄名保留為標籤；文字空白設為使用者缺失值。']
        frame, meta = pyreadstat.read_sav(str(native), user_missing=False, apply_value_formats=False, row_limit=MAX_ROWS + 1)
        if frame.empty or len(frame) > MAX_ROWS or len(frame.columns) > MAX_COLUMNS:
            raise ValueError('資料需 1–100,000 列，最多 300 欄。')
        columns = []
        for name, alias in mapping.items():
            series = frame[alias]
            numeric = pd.api.types.is_numeric_dtype(series)
            if numeric and np.isinf(series.to_numpy(dtype=float, na_value=np.nan)).any():
                raise ValueError('資料包含無限值，請先清理。')
            columns.append({'name': name, 'spss_name': alias, 'type': 'numeric' if numeric else 'text',
                            'missing': int(series.isna().sum()), 'unique': int(series.nunique()),
                            'values': clean(series.dropna().unique().tolist()) if series.nunique() <= 12 else None})
        _, raw_meta = pyreadstat.read_sav(str(native), metadataonly=True, user_missing=True)
        info = {'id': identifier, 'name': source.name, 'created_at': now(), 'rows': len(frame), 'columns': columns,
                'mapping': mapping, 'source_sha256': sha(original), 'sha256': sha(native), 'notes': notes,
                'value_labels': raw_meta.variable_value_labels, 'missing_ranges': raw_meta.missing_ranges}
        write_json(folder / 'dataset.json', info)
        return info

    def data(self, identifier):
        folder = self.folder('datasets', identifier)
        info = read_json(folder / 'dataset.json')
        native = folder / 'data.sav'
        if sha(native) != info['sha256']:
            raise ValueError('資料 SHA-256 已改變；請重新匯入。')
        frame, _ = pyreadstat.read_sav(str(native), user_missing=False, apply_value_formats=False)
        frame.rename(columns={v: k for k, v in info['mapping'].items()}, inplace=True)
        return info, frame

    def check(self, plan_id, dataset_id):
        record = read_json(self.folder('plans', plan_id) / 'plan.json')
        plan = record['plan']
        info, frame = self.data(dataset_id)
        blockers = list(plan['unresolved_questions'])
        warnings = list(info['notes'])
        columns = set(frame.columns)
        for item in plan['variables']:
            if item['name'] not in columns:
                if item['required']:
                    blockers.append('缺少必要欄位：' + item['name'])
                continue
            series = frame[item['name']]
            if item['kind'] == 'numeric' and not pd.api.types.is_numeric_dtype(series):
                blockers.append('預期為數值欄位：' + item['name'])
            if item['role'] == 'id' and (series.isna().any() or series.duplicated().any()):
                blockers.append('ID 缺失或重複；需釐清一列是否一個獨立/配對單位：' + item['name'])
        if not any(x['role'] == 'id' for x in plan['variables']):
            warnings.append('未指定 ID；工具無法檢查是否一人一列，獨立性須由研究設計判斷。')
        diagnostics = []
        for analysis in plan['analyses']:
            method, o = analysis['method'], analysis['options']
            needed = used_columns(o)
            missing = set(needed) - columns
            if missing:
                blockers.append(analysis['id'] + ' 缺少分析欄位：' + ', '.join(sorted(missing)))
                continue
            subset = frame[needed]
            complete = subset.dropna()
            diagnostics.append({'id': analysis['id'], 'rows': len(frame), 'complete_rows': len(complete),
                                'missing_by_column': {c: int(subset[c].isna().sum()) for c in needed},
                                'note': 'complete_rows 是所有選定欄位完整列數；原生程序可能採逐變數/成對缺失排除，以 SPSS 表中的 N 為準。'})
            numeric = [] if method in ('frequencies', 'crosstabs') else needed
            for name in numeric:
                if not pd.api.types.is_numeric_dtype(frame[name]):
                    blockers.append(analysis['id'] + ' 需要數值欄位，請明確編碼（不自動轉碼）：' + name)
                elif frame[name].dropna().nunique() < 2 and method != 'descriptive':
                    blockers.append(analysis['id'] + ' 欄位無有效變異：' + name)
            if any(not pd.api.types.is_numeric_dtype(frame[x]) for x in numeric):
                continue
            if any(frame[x].dropna().empty for x in needed):
                blockers.append(analysis['id'] + ' 包含全部缺失的欄位。')
            if method in ('linear_regression', 'logistic_regression', 'pca', 'factor', 'reliability', 'kmeans', 'hierarchical', 'ttest_paired', 'wilcoxon') and len(complete) < max(3, len(o.get('predictors', [])) + 2):
                blockers.append(analysis['id'] + ' 完整資料不足以估計模型。')
            if method == 'logistic_regression' and set(complete[o['target']].unique()) != {0, 1}:
                blockers.append('二元邏輯斯迴歸結果欄目前必須明確編碼 0/1；事件為 1。')
            if method in ('linear_regression', 'logistic_regression') and len(complete):
                matrix = np.column_stack([np.ones(len(complete)), complete[o['predictors']].to_numpy(dtype=float)])
                if np.linalg.matrix_rank(matrix) < matrix.shape[1]:
                    blockers.append(analysis['id'] + ' 預測變數完全共線或為常數，需修改計畫。')
            if 'group' in o:
                values = set(frame[o['group']].dropna().unique())
                if len(values) < 2:
                    blockers.append(analysis['id'] + ' 分組少於兩個有效類別。')
                if 'group_values' in o:
                    codes = o['group_values']
                    if method == 'kruskal':
                        if any(x < codes[0] or x > codes[1] for x in values):
                            blockers.append('Kruskal 範圍未涵蓋全部組別；不自動排除資料。')
                    elif values != set(codes):
                        blockers.append(analysis['id'] + ' 實際組別必須恰好等於 group_values；不自動排除其他組。')
                for outcome in o.get('variables', []):
                    counts = frame.dropna(subset=[o['group'], outcome]).groupby(o['group'])[outcome].count()
                    if len(counts) != len(values) or any(counts < 2):
                        blockers.append(analysis['id'] + ' 每組至少需兩個有效結果值：' + outcome)
            if method == 'hierarchical' and len(frame) > 2000:
                blockers.append('本版階層分群限制 2,000 列；請先設計可審查的抽樣策略。')
            if 'clusters' in o and o['clusters'] >= len(complete):
                blockers.append('分群數必須小於完整資料列數。')
            if method == 'factor' and o['components'] >= len(o['variables']):
                blockers.append('主軸因子數須小於變數數。')
            if method in ('frequencies', 'crosstabs') and any(frame[x].nunique() > 100 for x in needed):
                blockers.append('類別超過 100；先釐清是否誤把連續值或 ID 作為類別。')
        return {'ready': not blockers, 'plan_id': plan_id, 'dataset_id': dataset_id,
                'blockers': list(dict.fromkeys(blockers)), 'warnings': warnings,
                'analyses': diagnostics, 'assumptions_requiring_review': plan['assumptions_to_check']}

    def installation(self):
        root = Path(os.environ.get('STATSTUDIO_SPSS_HOME', r'C:\Program Files\IBM\SPSS Statistics')).expanduser().resolve()
        python = root / 'Python3/python.exe'
        return {'available': python.is_file() and (root / 'spssengine.exe').is_file(),
                'spss_home': str(root), 'python': str(python), 'supported_platform': os.name == 'nt',
                'note': '僅檢查安裝檔案；授權與實際運作須執行研究驗證。每台電腦需要自己的可用 SPSS 安裝/授權。'}

    def run(self, plan_id, dataset_id, timeout=240):
        checked = self.check(plan_id, dataset_id)
        if not checked['ready']:
            raise ValueError('資料/計畫尚未就緒：' + '; '.join(checked['blockers']))
        installed = self.installation()
        if not installed['available'] or not installed['supported_platform']:
            raise ValueError('找不到支援的 Windows SPSS 安裝；可設定 STATSTUDIO_SPSS_HOME。')
        record = read_json(self.folder('plans', plan_id) / 'plan.json')
        info, _ = self.data(dataset_id)
        identifier = uuid.uuid4().hex
        folder = self.folder('runs', identifier)
        folder.mkdir(parents=True)
        # Freeze data and plan in this execution. No subsequent edits can change them.
        shutil.copyfile(self.folder('datasets', dataset_id) / 'data.sav', folder / 'input.sav')
        write_json(folder / 'plan.json', record)
        job = {'spss_home': installed['spss_home'],
               'setup': 'SET OLANG=ENGLISH OATTRS=BOTH PRINTBACK=OFF MPRINT=OFF THREADS=1.',
               'load': f'GET FILE={quote(folder / "input.sav")}.\nWEIGHT OFF.\nSPLIT FILE OFF.\nFILTER OFF.\nEXECUTE.',
               'spv_open': f'OMS /SELECT ALL /DESTINATION FORMAT=SPV OUTFILE={quote(folder / "native.spv")} VIEWER=NO /TAG="viewer".',
               'analyses': []}
        syntax = [job['setup'], job['spv_open']]
        for a in record['plan']['analyses']:
            item = {'id': a['id'], 'commands': build(a['method'], a['options'], info['mapping']),
                    'oms_open': f'OMS /SELECT ALL /DESTINATION FORMAT=OXML OUTFILE={quote(folder / (a["id"] + ".xml"))} VIEWER=NO IMAGES=YES CHARTFORMAT=IMAGE IMAGEFORMAT=PNG /TAG="analysis".'}
            job['analyses'].append(item)
            syntax.extend([job['load'], item['oms_open'], *item['commands'], 'OMSEND TAG="analysis".'])
        syntax.append('OMSEND TAG="viewer".')
        (folder / 'commands.sps').write_text('\n\n'.join(syntax), encoding='utf-8-sig')
        write_json(folder / 'job.json', job)
        worker = Path(__file__).with_name('spss_worker.py')
        # Retain the exact integration script used, just as we retain the syntax.
        shutil.copyfile(worker, folder / 'worker.py')
        status = {'ok': False}
        # All research instances for this OS user share the lock, even with different data roots.
        lock = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'StatStudioAI/spss-engine.lock'
        with engine_lock(lock):
            with (folder / 'worker.log').open('wb') as log:
                process = subprocess.Popen([installed['python'], str(folder / 'worker.py'), str(folder / 'job.json')],
                                           cwd=folder, stdout=log, stderr=subprocess.STDOUT,
                                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                                           env=dict(os.environ, PYTHONIOENCODING='utf-8'))
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    if os.name == 'nt':
                        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
                    else:
                        process.kill()
                    process.wait(timeout=15)
                    status = {'ok': False, 'error': 'SPSS execution timed out; only this worker process tree was terminated.'}
                else:
                    status_file = folder / 'worker-status.json'
                    status = read_json(status_file) if status_file.exists() else {'ok': False, 'error': 'Worker ended without a status file.'}
                    if process.returncode != 0:
                        status['ok'] = False
        analyses = []
        for a in record['plan']['analyses']:
            xml = folder / (a['id'] + '.xml')
            try:
                output = parse_output(xml, a['id']) if xml.exists() else {'tables': [], 'charts': [], 'messages': ['未產生原生 XML。']}
            except Exception as exc:
                # Preserve failed output and logs rather than losing the run record.
                output = {'tables': [], 'charts': [], 'messages': ['無法讀取 SPSS 輸出：' + str(exc)]}
            if not any(t['subtype'] not in ('Notes', 'Warnings') and any(c['number'] is not None for c in t['cells']) for t in output['tables']):
                status['ok'] = False
            analyses.append(dict(a, **output))
        result = {'id': identifier, 'study_id': record['study_id'], 'plan_id': plan_id, 'created_at': now(),
                  'status': 'completed' if status.get('ok') else 'failed', 'worker': status,
                  'dataset': {k: info[k] for k in ('id', 'name', 'rows', 'sha256', 'source_sha256', 'mapping')},
                  'plan': record['plan'], 'preflight': checked, 'analyses': analyses,
                  'provenance': {'engine': 'IBM SPSS Statistics (local licensed installation)', 'worker_sha256': sha(worker),
                                 'syntax_sha256': sha(folder / 'commands.sps'), 'input_sha256': sha(folder / 'input.sav')},
                  'paths': {'folder': str(folder), 'syntax': str(folder / 'commands.sps'), 'viewer': str(folder / 'native.spv'),
                            'json': str(folder / 'result.json'), 'report': str(folder / 'report.html'), 'log': str(folder / 'worker.log')}}
        write_json(folder / 'result.json', result)
        (folder / 'report.html').write_text(render_report(result), encoding='utf-8')
        return self.result(identifier, compact=True)

    def result(self, identifier, compact=False):
        result = read_json(self.folder('runs', identifier) / 'result.json')
        if compact:
            for a in result['analyses']:
                a['tables'] = [{k: v for k, v in t.items() if k != 'cells'} | {'cell_count': len(t['cells'])} for t in a['tables']]
        return result

    def table(self, run_id, table_id, offset=0, limit=150):
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 300:
            raise ValueError('offset >= 0; limit 1–300 required.')
        result = self.result(run_id)
        for a in result['analyses']:
            for table in a['tables']:
                if table['id'] == table_id:
                    return dict(table, cells=table['cells'][offset:offset + limit], total_cells=len(table['cells']),
                                next_offset=offset + limit if offset + limit < len(table['cells']) else None)
        raise ValueError('Unknown table ID.')

    def chart(self, run_id, chart_id):
        result = self.result(run_id)
        for a in result['analyses']:
            for chart in a['charts']:
                if chart['id'] == chart_id:
                    path = Path(chart['path']).resolve()
                    if not path.is_relative_to(self.folder('runs', run_id)) or path.suffix != '.png' or not path.is_file():
                        raise ValueError('Invalid chart path.')
                    return path
        raise ValueError('Unknown chart ID.')

    def save_interpretation(self, run_id, interpretation):
        result = self.result(run_id)
        if result['status'] != 'completed':
            raise ValueError('Failed runs cannot be presented as a completed analysis report.')
        interpretation = Interpretation.model_validate(interpretation).model_dump()
        evidence = {}
        for a in result['analyses']:
            for t in a['tables']:
                evidence[t['id']] = {'title': t['title'], 'notes': t['notes']}
                evidence.update({c['id']: c for c in t['cells']})
            evidence.update({c['id']: c for c in a['charts']})
        requested = {e for f in interpretation['findings'] for e in f['evidence']}
        if requested - evidence.keys():
            raise ValueError('Unknown evidence references: ' + ', '.join(sorted(requested - evidence.keys())))
        identifier = uuid.uuid4().hex
        folder = self.folder('runs', run_id) / 'interpretations' / identifier
        folder.mkdir(parents=True)
        write_json(folder / 'interpretation.json', dict(interpretation, created_at=now(), run_id=run_id,
                                                       evidence={k: evidence[k] for k in sorted(requested)}))
        report = folder / 'report.html'
        report.write_text(render_report(result, interpretation), encoding='utf-8')
        return {'id': identifier, 'run_id': run_id, 'report_path': str(report), 'json_path': str(folder / 'interpretation.json'),
                'validation': '來源 ID 存在已核對；未自動證明敘述、統計判斷或因果推論正確。'}
