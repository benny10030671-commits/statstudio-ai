"""Developer-only SPSS 30 oracle for the bundled synthetic meta-analysis cases.

Use IBM's bundled Python and a separately licensed SPSS installation. This
script starts its own engine and does not use the user's open SPSS dataset.
It never imports the independent engine or changes expected numeric values.
"""
import argparse
import configparser
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

from spss_cases import CASES


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(home, output):
    home, output = home.resolve(), output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('Oracle output directory must be new or empty; retain the previous baseline.')
    output.mkdir(parents=True, exist_ok=True)
    os.environ['SPSS_HOME'] = str(home)
    os.environ['PATH'] = str(home) + os.pathsep + str(home / 'JRE/bin') + os.pathsep + os.environ.get('PATH', '')
    handles = [os.add_dll_directory(str(p)) for p in (home, home / 'JRE/bin') if p.is_dir()]
    import spss

    config = configparser.ConfigParser()
    config.read(str(home / 'spssdxcfg.ini'), encoding='utf-8')
    metadata = {'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'synthetic_data_only': True,
                'spss_version': config.get('version', 'SpssdxVersion'), 'python': sys.version,
                'engine_sha256': sha(home / 'spssengine.exe'),
                'fixture_sha256': sha(Path(__file__).with_name('spss_cases.py')), 'cases': [], 'ok': False}
    setup = 'SET OLANG=ENGLISH OATTRS=BOTH PRINTBACK=OFF MPRINT=OFF THREADS=1.'
    syntax = [setup]
    started = False
    try:
        spss.StartSPSS()
        started = True
        spss.Submit(setup)
        for case in CASES:
            opts = case['options']
            data = '\n'.join([
                'DATA LIST FREE /study (A8) e1 n1 e2 n2.', 'BEGIN DATA',
                *[' '.join(map(str, row)) for row in case['rows']], 'END DATA.',
                'COMPUTE b=n1-e1.', 'COMPUTE d=n2-e2.',
                'WEIGHT OFF.', 'SPLIT FILE OFF.', 'FILTER OFF.', 'EXECUTE.',
            ])
            path = output / (case['id'] + '.xml')
            capture = f"OMS /SELECT ALL /DESTINATION FORMAT=OXML OUTFILE='{path.as_posix().replace(chr(39), chr(39)*2)}' VIEWER=NO /TAG='meta'."
            estimator = {'DL': 'DERSIMONIAN_LAIRD', 'REML': 'REML'}[opts['tau2_method']]
            command = ('META BINARY\n'
                       f'/CRITERIA CILEVEL={opts["confidence"]*100:g} MAXITER=1000 CONVERGENCE=1E-10 ZEROCOUNTS=ONLY ADD=0.5 DROP=TRUE\n'
                       f'/DATA TREATMENT=SUCCESS(e1) FAILURE(b) CONTROL=SUCCESS(e2) FAILURE(d) ESTYPE=LOG{opts["measure"]} STUDY=study\n'
                       f'/INFERENCE MODEL=RANDOM ESTIMATE={estimator} ADJUSTSE=NONE\n'
                       '/PRINT HOMOGENEITY HETEROGENEITY INDIVIDUAL PREDICTION EFORM(TRUE).')
            close = "OMSEND TAG='meta'."
            syntax.extend([data, capture, command, close])
            spss.Submit(data)
            spss.Submit(capture)
            record = {'id': case['id'], 'options': opts, 'input_rows': case['rows']}
            try:
                spss.Submit(command)
                record.update(error_level=spss.GetLastErrorLevel(), message=spss.GetLastErrorMessage())
            finally:
                spss.Submit(close)
                record['output_sha256'] = sha(path) if path.exists() else None
                metadata['cases'].append(record)
            if record['error_level'] >= 3:
                raise RuntimeError(f'{case["id"]}: {record["message"]}')
        metadata['ok'] = True
    finally:
        if started:
            spss.StopSPSS()
        (output / 'commands.sps').write_text('\n\n'.join(syntax), encoding='utf-8')
        (output / 'metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print(json.dumps({'ok': metadata['ok'], 'cases': len(metadata['cases'])}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spss-home', type=Path, default=Path(r'C:\Program Files\IBM\SPSS Statistics'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.spss_home, args.output)
