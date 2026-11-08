"""SPSS-native synthetic references plus option and degrees-of-freedom boundaries."""
import hashlib
import json
import math
from pathlib import Path
import sys

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'validation/meta'))
from compare_spss import CASES, ORACLE, ROLES, compare_case
from statstudio.engine import METHODS, analyze


def table(result, title):
    return next(t for t in result['tables'] if t['title'] == title)


def heterogeneity(result):
    t = table(result, 'Heterogeneity')
    return dict(zip(t['columns'], t['rows'][0]))


def frame(case=CASES[0]):
    return pd.DataFrame(case['rows'], columns=['study', 'e1', 'n1', 'e2', 'n2'])


@pytest.mark.parametrize('case', CASES, ids=[c['id'] for c in CASES])
def test_against_native_spss(case):
    report = compare_case(case)
    k = len(case['rows']) - (1 if case['id'] == 'double_zero_or_dl' else 0)
    assert len(report['checks']) == 6 * k + (16 if k >= 3 else 14)
    failed = [c for c in report['checks'] if c['status'] != 'passed']
    assert failed == []


def test_oracle_integrity_and_historical_differences():
    metadata = json.loads((ORACLE / 'metadata.json').read_text(encoding='utf-8'))
    assert metadata['ok'] and metadata['spss_version'] == '30.0'
    assert metadata['synthetic_data_only']
    assert len(metadata['cases']) == len(CASES) == 10
    assert hashlib.sha256((ROOT / 'validation/meta/spss_cases.py').read_bytes()).hexdigest() == metadata['fixture_sha256']
    for reference, case in zip(metadata['cases'], CASES):
        assert reference['id'] == case['id']
        assert reference['input_rows'] == case['rows']
        assert reference['options'] == case['options']
        assert reference['error_level'] in (0, 2)
        assert hashlib.sha256((ORACLE / (case['id'] + '.xml')).read_bytes()).hexdigest() == reference['output_sha256']
    before = json.loads((ROOT / 'validation/meta/spss-parity-before-settings.json').read_text(encoding='utf-8'))
    current = json.loads((ROOT / 'validation/meta/spss-parity-report.json').read_text(encoding='utf-8'))
    assert before['counts'] == {'passed': 409, 'failed': 25}
    assert current['counts'] == {'passed': 434}
    old_cells = {(r['case'], c['metric']): (c['expected'], c['number_raw']) for r in before['cases'] for c in r['checks']}
    new_cells = {(r['case'], c['metric']): (c['expected'], c['number_raw']) for r in current['cases'] for c in r['checks']}
    assert old_cells == new_cells


def test_default_contract_and_separate_degrees_of_freedom():
    spec = next(m for m in METHODS if m['id'] == 'meta_binary')
    params = {p['key']: p for p in spec['parameters']}
    assert params['prediction_df']['default'] == 'k-2'
    assert params['heterogeneity_method']['default'] == 'tau2'
    res = analyze(frame(), 'meta_binary', ROLES)
    old = analyze(frame(), 'meta_binary', {**ROLES, 'prediction_df': 'k-1', 'heterogeneity_method': 'q'})
    for title in ('Pooled estimates', 'Study estimates', 'Event totals', 'Small-study effects (Egger regression)'):
        assert table(res, title) == table(old, title)
    het, previous = heterogeneity(res), heterogeneity(old)
    assert het['df'] == previous['df'] == 5  # Cochran Q still uses k-1.
    assert table(res, 'Pooled estimates')['rows'][2][-1] == 't(5)'  # HK CI also k-1.
    assert het['Prediction interval df'] == 4
    assert previous['Prediction interval df'] == 5
    assert het['Prediction interval lower (OR)'] < previous['Prediction interval lower (OR)']
    assert het['Prediction interval upper (OR)'] > previous['Prediction interval upper (OR)']
    assert res['details']['prediction_interval']['df'] == 4


def test_low_q_h_and_legacy_are_distinct():
    res = analyze(frame(CASES[2]), 'meta_binary', ROLES)
    old = analyze(frame(CASES[2]), 'meta_binary', {**ROLES, 'heterogeneity_method': 'q'})
    het, previous = heterogeneity(res), heterogeneity(old)
    assert het['tau²'] == het['I² %'] == 0
    assert het['H'] == het['H²'] == 1
    assert previous['H²'] == pytest.approx(previous['Q'] / previous['df'])
    assert 0 < previous['H'] < 1
    assert previous['H'] == pytest.approx(math.sqrt(previous['H²']))


@pytest.mark.parametrize('k', [1, 2])
@pytest.mark.parametrize('prediction_df', ['k-2', 'k-1'])
def test_too_few_studies_leave_prediction_undefined(k, prediction_df):
    res = analyze(frame().iloc[:k], 'meta_binary', {**ROLES, 'prediction_df': prediction_df})
    het = heterogeneity(res)
    assert het['Prediction interval df'] is None
    assert het['Prediction interval lower (OR)'] is None
    assert het['Prediction interval upper (OR)'] is None
    if k == 1:
        assert het['H²'] is None and het['H'] is None and het['I² %'] is None
    assert any('少於 3' in warning for warning in res['warnings'])
    json.dumps(res, allow_nan=False)


def test_exclusions_determine_prediction_df():
    data = frame(CASES[8]).astype({'e1': float})
    data.loc[len(data)] = ['missing', float('nan'), 25, 1, 25]
    res = analyze(data, 'meta_binary', ROLES)
    assert res['details']['k_pooled'] == 5
    assert res['details']['double_zero_excluded'] == ['S3']
    assert heterogeneity(res)['df'] == 4
    assert heterogeneity(res)['Prediction interval df'] == 3


@pytest.mark.parametrize('invalid', [{'prediction_df': 'k-3'}, {'prediction_df': 5}, {'heterogeneity_method': 'SPSS'}, {'k': 7}])
def test_unsupported_settings_rejected(invalid):
    with pytest.raises(ValueError):
        analyze(frame(), 'meta_binary', {**ROLES, **invalid})
