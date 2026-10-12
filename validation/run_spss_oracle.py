"""Developer-only SPSS 30 oracle. The standalone product never imports this script.

Run with the Python supplied by a separately installed/licensed SPSS. A new
engine belongs to this process; StartSPSS/StopSPSS do not operate the user's GUI.
All input is the synthetic CSV generated beside this script. Outputs stay here.
"""
import argparse
import csv
import configparser
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
CASES={
 'descriptive':'DESCRIPTIVES VARIABLES=x y z /MISSING=VARIABLE /STATISTICS=ALL.',
 'frequencies':'FREQUENCIES VARIABLES=group binary /FORMAT=AVALUE.',
 'crosstabs':'CROSSTABS /TABLES=group BY binary /FORMAT=AVALUE TABLES /STATISTICS=CHISQ PHI /CELLS=COUNT EXPECTED ROW COLUMN TOTAL.',
 'ttest_one':'T-TEST /TESTVAL=0.25 /VARIABLES=x y /MISSING=ANALYSIS /CRITERIA=CI(.95).',
 'ttest_independent':'T-TEST GROUPS=binary(0 1) /VARIABLES=y /MISSING=ANALYSIS /CRITERIA=CI(.95).',
 'ttest_paired':'T-TEST PAIRS=paired_a WITH paired_b (PAIRED) /MISSING=ANALYSIS /CRITERIA=CI(.95).',
 'anova':'ONEWAY y BY group /STATISTICS DESCRIPTIVES HOMOGENEITY /MISSING ANALYSIS.',
 'correlation':'CORRELATIONS VARIABLES=x y z /MISSING=PAIRWISE /PRINT=TWOTAIL NOSIG /STATISTICS DESCRIPTIVES /CI=BIAS(FALSE) CILEVEL(95).',
 'linear_regression':'REGRESSION /MISSING LISTWISE /STATISTICS COEFF R ANOVA CI(95) /NOORIGIN /DEPENDENT y /METHOD=ENTER x z.',
 'logistic_regression':'LOGISTIC REGRESSION VARIABLES binary /METHOD=ENTER x z /PRINT=CI(95) /CRITERIA=BCON(0.0000000001) LCON(0) ITERATE(100) CUT(.5).',
 'reliability':'RELIABILITY /VARIABLES=item1 item2 item3 /SCALE(\'All Items\') ALL /MODEL=ALPHA /STATISTICS=DESCRIPTIVE SCALE CORR /SUMMARY=TOTAL.',
 'pca':'FACTOR /VARIABLES=item1 item2 item3 /MISSING=LISTWISE /ANALYSIS=item1 item2 item3 /PRINT=INITIAL EXTRACTION /CRITERIA=FACTORS(2) ITERATE(25) /EXTRACTION=PC /ROTATION=NOROTATE /METHOD=CORRELATION.',
 'examine':'EXAMINE VARIABLES=x y z /PLOT NONE /STATISTICS DESCRIPTIVES /PERCENTILES(25,50,75) HAVERAGE /CINTERVAL 95 /MISSING PAIRWISE.',
 'mann_whitney':'NPAR TESTS /M-W=y BY binary(0 1) /MISSING ANALYSIS.',
 'wilcoxon':'NPAR TESTS /WILCOXON=paired_b WITH paired_a (PAIRED) /MISSING ANALYSIS.',
 'kruskal':'NPAR TESTS /K-W=y BY group(1 3) /MISSING ANALYSIS.',
 'factor':'FACTOR /VARIABLES=item1 item2 item3 /MISSING=LISTWISE /ANALYSIS=item1 item2 item3 /PRINT=INITIAL EXTRACTION KMO /CRITERIA=FACTORS(1) ITERATE(100) ECONVERGE(.000001) /EXTRACTION=PAF /ROTATION=NOROTATE /METHOD=CORRELATION.',
 'hierarchical':'CLUSTER x z /METHOD=BAVERAGE /MEASURE=SEUCLID /PRINT=SCHEDULE CLUSTER(3) /PLOT=NONE.',
 'kmeans':'QUICK CLUSTER x z /MISSING=LISTWISE /CRITERIA=CLUSTER(3) NOINITIAL MXITER(300) CONVERGE(0) /METHOD=KMEANS(NOUPDATE) /PRINT=INITIAL CLUSTER.',
}


def run(spss_home, fixture_name, only=None):
    if fixture_name not in ('reference','reference_missing'):
        raise ValueError('Only the two bundled synthetic fixtures may be submitted.')
    data_path=ROOT/'tests'/'fixtures'/f'{fixture_name}.csv'
    with data_path.open(encoding='utf-8',newline='') as handle:
        reader=csv.DictReader(handle);fields=reader.fieldnames;rows=list(reader)
    out=ROOT/'validation'/'spss30'/fixture_name
    out.mkdir(parents=True,exist_ok=True)
    os.environ['SPSS_HOME']=str(spss_home)
    os.environ['PATH']=str(spss_home)+os.pathsep+str(spss_home/'JRE'/'bin')+os.pathsep+os.environ.get('PATH','')
    dll_handles=[os.add_dll_directory(str(spss_home)),os.add_dll_directory(str(spss_home/'JRE'/'bin'))]
    import spss
    data='DATA LIST FREE /'+' '.join(f+' (F20.10)' for f in fields)+'.\nBEGIN DATA\n'+'\n'.join(' '.join(row[f] or '.' for f in fields) for row in rows)+'\nEND DATA.\nEXECUTE.\n'
    setup='SET OLANG=ENGLISH OATTRS=BOTH PRINTBACK=OFF MPRINT=OFF THREADS=1.\nWEIGHT OFF.\nSPLIT FILE OFF.\nFILTER OFF.\n'
    syntax=data+setup
    metadata={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'fixture':data_path.name,'fixture_sha256':hashlib.sha256(data_path.read_bytes()).hexdigest(),'python':sys.version,'platform':platform.platform(),'engine_owner':'new engine started and stopped by this standalone oracle process','cases':[]}
    if only and (out/'metadata.json').exists():
        prior=json.loads((out/'metadata.json').read_text(encoding='utf-8'))
        if prior['fixture_sha256']!=metadata['fixture_sha256']:raise ValueError('Fixture changed; cannot combine oracle runs.')
        metadata['cases']=[item for item in prior['cases'] if item['id'] not in only]
    cfg=configparser.ConfigParser();cfg.read(spss_home/'spssdxcfg.ini',encoding='utf-8')
    metadata['spss_version']=cfg.get('version','SpssdxVersion')
    started=False
    try:
        spss.StartSPSS();started=True
        metadata['spss_python_module']=str(spss.__file__)
        metadata['spss_executable_sha256']=hashlib.sha256((spss_home/'spssengine.exe').read_bytes()).hexdigest()
        bootstrap_path=str(out/'bootstrap.xml').replace(chr(92),'/')
        spss.Submit(f"OMS /DESTINATION FORMAT=OXML OUTFILE='{bootstrap_path}' VIEWER=NO /TAG='bootstrap'.")
        for stage,statement in [('data',data),('setup',setup)]:
            try:
                spss.Submit(statement)
                print('submitted',stage,flush=True)
            except Exception:
                metadata['bootstrap_error']={'stage':stage,'error_level':spss.GetLastErrorLevel(),'message':spss.GetLastErrorMessage()}
                print(json.dumps(metadata['bootstrap_error']),flush=True)
                raise
        spss.Submit("OMSEND TAG='bootstrap'.")
        for name,command in CASES.items():
            output=out/f'{name}.xml'
            capture=f"OMS /SELECT TABLES /DESTINATION FORMAT=OXML OUTFILE='{str(output).replace(chr(92),'/')}' VIEWER=NO /TAG='{name}'.\n{command}\nOMSEND TAG='{name}'.\n"
            syntax+=capture
            if only and name not in only:continue
            try:
                spss.Submit(capture)
                item={'id':name,'error_level':spss.GetLastErrorLevel(),'message':spss.GetLastErrorMessage(),'output_exists':output.exists()}
                if output.exists():item['output_sha256']=hashlib.sha256(output.read_bytes()).hexdigest()
            except Exception as exc:
                item={'id':name,'exception':repr(exc),'output_exists':output.exists()}
            metadata['cases'].append(item)
            print(json.dumps(item,ensure_ascii=False),flush=True)
    finally:
        if started:spss.StopSPSS()
        (out/'commands.sps').write_text(syntax,encoding='utf-8')
        (out/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('oracle complete:',out,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--spss-home',type=Path,default=Path(r'C:\Program Files\IBM\SPSS Statistics'))
    parser.add_argument('--fixture',choices=['reference','reference_missing'],default='reference')
    parser.add_argument('--only',nargs='+',choices=list(CASES))
    args=parser.parse_args();run(args.spss_home,args.fixture,args.only)
