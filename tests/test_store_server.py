import io
import json
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from statstudio.store import Store
from statstudio.server import create_app


def test_roundtrip_missing_and_precision(tmp_path):
    store = Store(tmp_path)
    source = pd.DataFrame({'x': [np.pi, None, 1e-19], 'category': ['NA', 'b', '']})
    info = store.add_frame(source, 'fixture')
    restored = store.frame(info['id'])
    assert restored.x.iloc[0] == np.pi
    assert restored.x.iloc[2] == 1e-19
    assert pd.isna(restored.x.iloc[1])
    assert restored.category.iloc[0] == 'NA'
    payload = store.datasets / info['id'] / 'data.json'
    payload.write_text(payload.read_text(encoding='utf-8').replace('3.141592653589793', '3.2'), encoding='utf-8')
    with pytest.raises(ValueError, match='SHA-256'):
        store.frame(info['id'])


def test_import_validation(tmp_path):
    store = Store(tmp_path)
    with pytest.raises(ValueError, match='重複'):
        store.import_bytes('a.csv', b'x,x\n1,2\n')
    with pytest.raises(ValueError):
        store.dataset('../../x')
    with pytest.raises(ValueError, match='無限'):
        store.import_bytes('a.csv', b'x\ninf\n')
    info = store.import_bytes('a.csv', b'x,s\n1,NA\n,hello\n')
    assert store.frame(info['id']).s.iloc[0] == 'NA'
    assert info['columns'][0]['missing'] == 1


def test_api_analysis_artifact_and_origin_guard(tmp_path):
    client = TestClient(create_app(tmp_path), base_url='http://127.0.0.1')
    assert client.get('/api/methods').status_code == 200
    assert client.post('/api/demo', headers={'origin': 'https://evil.example'}).status_code == 403
    assert client.get('/api/datasets', headers={'host': 'evil.example'}).status_code == 403
    loaded = client.post('/api/datasets/upload', files={'file': ('<script>alert(1)</script>.csv', b'x,y\n1,2\n2,5\n3,6\n4,8\n')})
    assert loaded.status_code == 200
    result = client.post('/api/analyze', json={'dataset_id': loaded.json()['id'], 'method': 'descriptive', 'options': {'variables': ['x', 'y']}})
    assert result.status_code == 200, result.text
    assert result.json()['compatibility']['status'] == 'unverified_for_this_dataset'
    identifier = result.json()['id']
    assert client.get(f'/api/results/{identifier}/json').json() == result.json()
    html = client.get(f'/api/results/{identifier}/report').text
    assert '<script>alert' not in html
    assert 'STATSTUDIO AI' in html
    assert '<svg' in html
    bad = client.post('/api/analyze', json={'dataset_id': loaded.json()['id'], 'method': 'descriptive', 'options': {'variables': ['x'], 'weight': 'y'}})
    assert bad.status_code == 400


def test_xlsx_and_sav_import(tmp_path):
    import pyreadstat
    store = Store(tmp_path / 'store')
    frame = pd.DataFrame({'x': [1., 2., 3.], 'group': [1., 1., 2.]})
    excel = io.BytesIO()
    frame.to_excel(excel, index=False)
    info = store.import_bytes('a.xlsx', excel.getvalue())
    assert info['rows'] == 3
    sav = tmp_path / 'fixture.sav'
    pyreadstat.write_sav(frame, str(sav), variable_value_labels={'group': {1: 'first', 2: 'second'}})
    info = store.import_path(str(sav))
    assert store.dataset(info['id'])['metadata']['value_labels']['group']['1.0'] == 'first'
    pyreadstat.write_sav(frame, str(sav), missing_ranges={'x': [3.]})
    with pytest.raises(ValueError, match='使用者定義缺失'):
        store.import_path(str(sav))
