from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import io
import json
import math
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import __version__

MAX_BYTES = 25 * 1024 * 1024
MAX_ROWS = 100_000
MAX_COLUMNS = 300


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [clean(v) for v in value]
    if isinstance(value, np.generic):
        return clean(value.item())
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def dumps(value):
    return json.dumps(clean(value), ensure_ascii=False, allow_nan=False, indent=2)


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value):
    # A unique temporary file also permits separate web/MCP processes to share storage.
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(dumps(value), encoding='utf-8')
    temporary.replace(path)


class Store:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or os.environ.get('STATSTUDIO_HOME') or Path.home() / '.statstudio').resolve()
        self.datasets = self.root / 'datasets'
        self.results = self.root / 'results'
        self.datasets.mkdir(parents=True, exist_ok=True)
        self.results.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def valid_id(identifier):
        if not isinstance(identifier, str) or not re.fullmatch(r'[0-9a-f]{32}', identifier):
            raise ValueError('無效的資料或結果識別碼。')
        return identifier

    def import_bytes(self, filename: str, content: bytes):
        if not content or len(content) > MAX_BYTES:
            raise ValueError('請匯入 25 MB 以內的非空檔案。')
        name = Path(filename.replace('\\', '/')).name
        suffix = Path(name).suffix.lower()
        notes = []
        metadata = {}
        if suffix in ('.csv', '.tsv'):
            try:
                text = content.decode('utf-8-sig')
            except UnicodeDecodeError:
                raise ValueError('CSV / TSV 請存成 UTF-8 編碼。')
            delimiter = '\t' if suffix == '.tsv' else ','
            headers = next(csv.reader(io.StringIO(text), delimiter=delimiter), [])
            if not headers or any(not h.strip() for h in headers) or len(headers) != len(set(headers)):
                raise ValueError('欄名不可空白或重複。')
            frame = pd.read_csv(io.StringIO(text), sep=delimiter, keep_default_na=False, na_values=[''], nrows=MAX_ROWS + 1, float_precision='round_trip')
            notes.append('CSV 空欄位視為缺失；NA、N/A 等文字保留原值。')
        elif suffix == '.xlsx':
            frame = pd.read_excel(io.BytesIO(content), sheet_name=0, engine='openpyxl', keep_default_na=False, na_values=[''], nrows=MAX_ROWS + 1)
            notes.append('匯入第一個工作表；公式使用檔案中已儲存的計算結果。')
        elif suffix in ('.sav', '.zsav'):
            import pyreadstat
            with tempfile.TemporaryDirectory() as temp:
                source = Path(temp) / ('input' + suffix)
                source.write_bytes(content)
                frame, meta = pyreadstat.read_sav(str(source), user_missing=True, apply_value_formats=False, row_limit=MAX_ROWS + 1)
            if meta.missing_ranges:
                raise ValueError('此 SAV 含使用者定義缺失值。本版尚未實作各程序的 INCLUDE / EXCLUDE 規則，請先明確轉為系統缺失後再匯入。')
            metadata = {'variable_labels': meta.column_names_to_labels, 'value_labels': meta.variable_value_labels}
            notes.append('保留原始數值編碼及標籤中繼資料；不套用 SPSS 的篩選、加權或 SPLIT FILE。')
        else:
            raise ValueError('支援 CSV、TSV、XLSX、SAV、ZSAV。')
        return self.add_frame(frame, name, hashlib.sha256(content).hexdigest(), notes, metadata)

    def import_path(self, path: str):
        source = Path(path).expanduser().resolve()
        if not source.is_file() or source.stat().st_size > MAX_BYTES:
            raise ValueError('資料檔不存在或超過 25 MB。')
        return self.import_bytes(source.name, source.read_bytes())

    def add_frame(self, frame, name, source_sha256=None, notes=None, metadata=None):
        if frame.empty or len(frame) > MAX_ROWS or len(frame.columns) > MAX_COLUMNS:
            raise ValueError('資料必須包含 1–100,000 列，且不超過 300 欄。')
        frame = frame.copy()
        frame.columns = [str(x) for x in frame.columns]
        if frame.columns.duplicated().any() or any(not x.strip() for x in frame.columns):
            raise ValueError('欄名不可空白或重複。')
        for col in frame.select_dtypes(include='number'):
            if np.isinf(frame[col].to_numpy(dtype=float, na_value=np.nan)).any():
                raise ValueError(f'{col} 含無限值；請先清理，避免被誤當成有效數值。')
        identifier = uuid.uuid4().hex
        folder = self.datasets / identifier
        folder.mkdir()
        content = {'columns': list(frame.columns), 'rows': clean(frame.to_numpy().tolist())}
        data_hash = hashlib.sha256(dumps(content).encode('utf-8')).hexdigest()
        columns = [{'name': col, 'type': 'numeric' if pd.api.types.is_numeric_dtype(frame[col]) else 'text',
                    'missing': int(frame[col].isna().sum()), 'unique': int(frame[col].nunique(dropna=True))}
                   for col in frame.columns]
        info = {'id': identifier, 'name': name, 'rows': len(frame), 'columns': columns,
                'preview': clean(frame.head(10).to_dict(orient='records')), 'created_at': now(),
                'source_sha256': source_sha256, 'data_sha256': data_hash, 'notes': notes or [], 'metadata': metadata or {}}
        write_json(folder / 'data.json', content)
        write_json(folder / 'metadata.json', info)
        return info

    def dataset(self, identifier):
        path = self.datasets / self.valid_id(identifier) / 'metadata.json'
        if not path.exists():
            raise ValueError('找不到資料集。')
        return json.loads(path.read_text(encoding='utf-8'))

    def frame(self, identifier):
        info = self.dataset(identifier)
        path = self.datasets / identifier / 'data.json'
        content = json.loads(path.read_text(encoding='utf-8'))
        if hashlib.sha256(dumps(content).encode('utf-8')).hexdigest() != info['data_sha256']:
            raise ValueError('資料內容與匯入時的 SHA-256 不一致，請重新匯入。')
        frame = pd.DataFrame(content['rows'], columns=content['columns'])
        for column in info['columns']:
            if column['type'] == 'numeric':
                frame[column['name']] = pd.to_numeric(frame[column['name']])
        return frame

    def list_datasets(self):
        return [json.loads(p.read_text(encoding='utf-8')) for p in sorted(self.datasets.glob('*/metadata.json'), key=lambda p: p.stat().st_mtime, reverse=True)]

    def demo(self):
        source = Path(__file__).parent / 'resources' / 'demo.csv'
        return self.import_bytes('示範資料.csv', source.read_bytes())

    def analyze(self, dataset_id, method, options):
        from .engine import analyze
        from . import engine
        from .report import report_html
        dataset = self.dataset(dataset_id)
        result = clean(analyze(self.frame(dataset_id), method, options))
        identifier = uuid.uuid4().hex
        result.update({'id': identifier, 'method': method, 'created_at': now(),
                       'dataset': {key: dataset[key] for key in ('id', 'name', 'rows', 'data_sha256')},
                       'provenance': {'app_version': __version__, 'engine_source_sha256': hashlib.sha256(Path(engine.__file__).read_bytes()).hexdigest(), 'options_requested': clean(options),
                                      'libraries': {x: importlib.metadata.version(x) for x in ('numpy', 'scipy', 'pandas', 'statsmodels', 'scikit-learn')},
                                      'runtime': 'Independent Python engine; no SPSS dependency'},
                       'compatibility': {'status': 'unverified_for_this_dataset',
                                         'description': '獨立實作。固定測試樣本的比對結果見 docs/validation；本次資料與所有選項尚未經 SPSS 逐項驗證，不代表與 SPSS 完全一致。'}})
        result.setdefault('warnings', []).extend(dataset['notes'])
        folder = self.results / identifier
        folder.mkdir()
        write_json(folder / 'result.json', result)
        (folder / 'report.html').write_text(report_html(result), encoding='utf-8')
        return result

    def result(self, identifier):
        path = self.result_file(identifier, 'result.json')
        return json.loads(path.read_text(encoding='utf-8'))

    def result_file(self, identifier, filename):
        if filename not in ('result.json', 'report.html'):
            raise ValueError('無效的結果格式。')
        path = self.results / self.valid_id(identifier) / filename
        if not path.exists():
            raise ValueError('找不到結果。')
        return path

    def list_results(self):
        return [{k: r[k] for k in ('id', 'title', 'method', 'created_at')} for r in
                [json.loads(p.read_text(encoding='utf-8')) for p in sorted(self.results.glob('*/result.json'), key=lambda p: p.stat().st_mtime, reverse=True)]]
