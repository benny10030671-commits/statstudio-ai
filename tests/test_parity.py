"""Saved SPSS numerical oracle regression tests; SPSS is not needed to run these."""
from pathlib import Path
import hashlib
import json
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'validation'))
from compare import CASES, compare_case


EXPECTED_CELLS={
    'descriptive':45,'frequencies':20,'crosstabs':28,
    'ttest_one':20,'ttest_independent':24,'ttest_paired':9,
    'anova':21,'correlation':15,'linear_regression':33,
    'logistic_regression':33,'reliability':16,'pca':21,
    'mann_whitney':8,'wilcoxon':6,'kruskal':9,'factor':13,
}


@pytest.mark.parametrize('fixture',['reference','reference_missing'])
@pytest.mark.parametrize('method',list(CASES))
def test_selected_cells_against_saved_spss(fixture,method):
    result=compare_case(fixture,method)
    expected=EXPECTED_CELLS.get(method)
    if expected is None:
        expected=237 if fixture=='reference' else 229
        if method=='kmeans':expected=69 if fixture=='reference' else 67
    assert len(result['checks'])==expected, 'The tested numerical scope must not silently shrink.'
    failures=[(c['metric'],c['actual'],c['expected'],c['abs_error'],c['threshold']) for c in result['checks'] if c['status']=='failed']
    assert failures==[],f'{fixture}/{method} differs from SPSS at selected cells: {failures}'


@pytest.mark.parametrize('fixture',['reference','reference_missing'])
def test_oracle_provenance_and_clean_execution(fixture):
    base=ROOT/'validation'/'spss30'/fixture
    metadata=json.loads((base/'metadata.json').read_text(encoding='utf-8'))
    raw=(ROOT/'tests'/'fixtures'/f'{fixture}.csv').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==metadata['fixture_sha256']
    assert len(metadata['cases'])==19 # 18 methods plus EXAMINE percentile/CI oracle.
    for case in metadata['cases']:
        assert case.get('error_level')==0,case
        assert 'exception' not in case,case
        assert hashlib.sha256((base/(case['id']+'.xml')).read_bytes()).hexdigest()==case['output_sha256']


def test_initial_540_cells_are_preserved():
    initial=json.loads((ROOT/'validation'/'parity-report-initial-540.json').read_text(encoding='utf-8'))
    latest=json.loads((ROOT/'validation'/'parity-report.json').read_text(encoding='utf-8'))
    original={(c['fixture'],c['method'],v['metric']):v for c in initial['cases'] for v in c['checks']}
    current={(c['fixture'],c['method'],v['metric']):v for c in latest['cases'] for v in c['checks']}
    assert len(original)==540
    assert original.keys()<=current.keys()
    for key,value in original.items():
        assert current[key]['expected']==value['expected']
        assert current[key]['status']=='passed'
