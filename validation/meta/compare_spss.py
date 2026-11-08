"""Compare named engine fields with retained native SPSS numeric cells."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'validation'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from statstudio.engine import analyze
from oxml import extract
from spss_cases import CASES

ORACLE = Path(__file__).with_name('spss30_reference')
ROLES = {'study': 'study', 'event_exp': 'e1', 'n_exp': 'n1', 'event_ctrl': 'e2', 'n_ctrl': 'n2'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare_case(case):
    data = pd.DataFrame(case['rows'], columns=['study', 'e1', 'n1', 'e2', 'n2'])
    result = analyze(data, 'meta_binary', {**ROLES, **case['options']})
    native = extract(ORACLE / (case['id'] + '.xml'))

    def rows(title):
        table = next(t for t in result['tables'] if t['title'] == title)
        return [dict(zip(table['columns'], r)) for r in table['rows']]

    def cell(subtype, path):
        matches = [c for t in native if t['subtype'] == subtype for c in t['cells'] if c['path'] == path]
        if len(matches) != 1:
            raise AssertionError(f'{case["id"]}: expected one {subtype}/{path}, found {len(matches)}')
        return matches[0]

    checks = []
    reml = case['options']['tau2_method'] == 'REML'

    def add(metric, actual, subtype, path, exact=False, probability=False, iterative=False):
        reference = cell(subtype, path)
        expected = reference['number']
        # Predeclared tolerances: REML solvers have different stopping rules.
        if exact:
            atol, rtol = 0.0, 0.0
        elif reml and iterative:
            atol, rtol = 1e-6, 1e-5
        elif probability:
            atol, rtol = 0.0, 1e-7
        else:
            atol, rtol = 1e-9, 1e-8
        error = abs(actual - expected) if actual is not None else None
        threshold = atol + rtol * abs(expected)
        checks.append({'metric': metric, 'actual': actual, 'expected': expected,
                       'abs_error': error, 'threshold': threshold,
                       'status': 'passed' if error is not None and error <= threshold else 'failed',
                       'subtype': subtype, 'path': path, 'number_raw': reference['number_raw']})

    pooled = rows('Pooled estimates')[1]
    label = case['options']['measure']
    level = f'{case["options"]["confidence"] * 100:g}%'
    for field, path in [(label, ['Exp. Effect Size']), (f'{label} lower', [f'Exp. {level} Confidence Interval', 'Lower']),
                        (f'{label} upper', [f'Exp. {level} Confidence Interval', 'Upper']),
                        (f'log {label}', ['Effect Size']), ('SE', ['Std. Error']),
                        ('Test statistic', ['Z']), ('p', ['Sig. (2-tailed)'])]:
        add('random.' + field, pooled[field], 'Effect Size Estimates', ['Overall'] + path,
            probability=field == 'p', iterative=True)
    add('k', pooled['k'], 'Case Processing Summary', ['Included', 'N'], exact=True)
    het = rows('Heterogeneity')[0]
    # The pre-change report derives H² from the original H because it did not expose H².
    for field, name in [('tau²', 'Tau-squared'), ('I² %', 'I-squared (%)'), ('H²', 'H-squared')]:
        value = het.get(field, het['H'] ** 2 if het['H'] is not None else None)
        add(field, value, 'Heterogeneity Measures', ['Overall', name], iterative=True)
    for field, name in [('Q', 'Chi-square (Q statistic)'), ('df', 'df'), ('p (Q)', 'Sig.')]:
        add(field, het[field], 'Test of Homogeneity', ['Overall', name], exact=field == 'df', probability=field == 'p (Q)')
    if pooled['k'] >= 3:
        for end in ('lower', 'upper'):
            add('prediction.' + end, het[f'Prediction interval {end} ({label})'], 'Effect Size Estimates',
                ['Overall', f'Exp. {level} Prediction Interval', end.title()], iterative=True)
    else:
        for end in ('lower', 'upper'):
            assert het[f'Prediction interval {end} ({label})'] is None
        assert not any('Prediction Interval' in str(c['path']) for t in native for c in t['cells'])
    included = [r for r in rows('Study estimates') if r['Pooled'] == 'yes']
    for index, study in enumerate(included, 1):
        for field, path in [(label, ['Exp. Effect Size']), (f'{label} lower', [f'Exp. {level} Confidence Interval', 'Lower']),
                            (f'{label} upper', [f'Exp. {level} Confidence Interval', 'Upper']),
                            (f'log {label}', ['Effect Size']), ('SE', ['Std. Error']), ('Weight random %', ['Weight (%)'])]:
            add(study['Study'] + '.' + field, study[field], 'Effect Size Estimates for Individual Studies',
                [str(index)] + path, iterative=field == 'Weight random %')
    return {'case': case['id'], 'options': result['details']['options'],
            'oracle_sha256': sha(ORACLE / (case['id'] + '.xml')), 'checks': checks,
            'counts': dict(Counter(c['status'] for c in checks))}


def run(output):
    reports = [compare_case(case) for case in CASES]
    report = {'generated_at_utc': datetime.now(timezone.utc).isoformat(),
              'engine_sha256': sha(ROOT / 'src/statstudio/engine.py'),
              'meta_sha256': sha(ROOT / 'src/statstudio/meta.py'),
              'counts': dict(Counter(c['status'] for r in reports for c in r['checks'])),
              'scope': '10 fixed synthetic cases; selected META BINARY random-effects fields only. No whole-product equivalence.',
              'policies': {'continuous': 'atol=1e-9, rtol=1e-8', 'p_values': 'atol=0, rtol=1e-7',
                           'counts_and_df': 'exact', 'REML_solver_dependent_fields': 'atol=1e-6, rtol=1e-5'},
              'cases': reports}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(output), 'counts': report['counts']}))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('spss-parity-report.json'))
    args = parser.parse_args()
    report = run(args.output)
    raise SystemExit(bool(report['counts'].get('failed')))
