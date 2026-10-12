"""Compare independent calculations with saved numeric SPSS 30 OXML cells.

This module and its tests run without SPSS. Only run_spss_oracle.py needs SPSS.
No rounding, sign flips, cluster permutations, or fitted tolerances are applied.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import pandas as pd
from statstudio.engine import analyze
from oxml import extract

CASES={
 'descriptive':{'variables':['x','y','z'],'missing':'available','confidence':0.95,'quantile':'weibull'},
 'frequencies':{'variables':['group','binary']},
 'crosstabs':{'x':'group','y':'binary'},
 'ttest_one':{'variables':['x','y'],'test_value':0.25,'confidence':0.95},
 'ttest_independent':{'variables':['y'],'group':'binary','variance':'both','confidence':0.95},
 'ttest_paired':{'x':'paired_a','y':'paired_b','confidence':0.95},
 'anova':{'variables':['y'],'group':'group'},
 'correlation':{'variables':['x','y','z'],'coefficient':'pearson','missing':'pairwise','confidence':0.95},
 'linear_regression':{'target':'y','predictors':['x','z'],'intercept':'yes','confidence':0.95},
 'logistic_regression':{'target':'binary','predictors':['x','z'],'event':'last','max_iter':100,'confidence':0.95},
 'reliability':{'variables':['item1','item2','item3']},
 'pca':{'variables':['item1','item2','item3'],'components':2,'matrix':'correlation','rotation':'none'},
 'mann_whitney':{'x':'y','group':'binary','continuity':'no'},
 'wilcoxon':{'x':'paired_a','y':'paired_b','continuity':'no'},
 'kruskal':{'x':'y','group':'group'},
 'factor':{'variables':['item1','item2','item3'],'factors':1,'rotation':'none','max_iter':100,'tolerance':0.000001},
 'hierarchical':{'variables':['x','z'],'clusters':3,'standardize':'no','linkage':'average','distance':'sqeuclidean','label_order':'native'},
 'kmeans':{'variables':['x','z'],'clusters':3,'standardize':'no','initialization':'first','seed':42,'max_iter':300,'label_order':'native'},
}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Comparator:
    def __init__(self,fixture,method):
        self.fixture,self.method=fixture,method
        self.input=ROOT/'tests'/'fixtures'/f'{fixture}.csv'
        self.oracle=ROOT/'validation'/'spss30'/fixture/f'{method}.xml'
        self.tables=extract(self.oracle)
        if method=='descriptive':self.tables+=extract(self.oracle.with_name('examine.xml'))
        self.result=analyze(pd.read_csv(self.input),method,CASES[method])
        self.checks=[]

    def rows(self,title):
        tables=[t for t in self.result['tables'] if t['title']==title]
        if len(tables)!=1:raise AssertionError(f'Expected one independent table {title!r}, got {len(tables)}')
        table=tables[0]
        return [dict(zip(table['columns'],row)) for row in table['rows']]

    def cell(self,subtype,*tokens,last=None,title=None):
        # Use explicit source-cell context, never nearest numeric value.
        candidates=[]
        for table in self.tables:
            if table['subtype']!=subtype or (title and table['title']!=title):continue
            for cell in table['cells']:
                path=[p.strip() for p in cell['path']]
                if all(token in path for token in tokens) and (last is None or path[-1]==last):
                    candidates.append((table,cell))
        if len(candidates)!=1:raise AssertionError(f'{self.method}: expected unique {subtype} tokens={tokens} last={last}; got {len(candidates)}')
        table,cell=candidates[0]
        return {'subtype':subtype,'title':table['title'],**cell}

    def add(self,metric,actual,source,exact=False,pvalue=False):
        expected=source['number']
        # Fixed in advance: never adjusted to force a failure to pass.
        atol,rtol=(0.,0.) if exact else ((0.,1e-7) if pvalue else (1e-10,1e-8))
        delta=abs(float(actual)-expected) if actual is not None else math.inf
        threshold=atol+rtol*abs(expected)
        passed=actual is not None and math.isfinite(float(actual)) and delta<=threshold
        self.checks.append({'metric':metric,'actual':actual,'expected':expected,'abs_error':delta if math.isfinite(delta) else None,'relative_error':delta/abs(expected) if expected and math.isfinite(delta) else None,'atol':atol,'rtol':rtol,'threshold':threshold,'status':'passed' if passed else 'failed','oracle_cell':source})


def compare_case(fixture,method):
    c=Comparator(fixture,method)
    if method=='descriptive':
        mapping={'N':'N','Mean':'Mean','Std. deviation':'Std. Deviation','Variance':'Variance','Minimum':'Minimum','Maximum':'Maximum','Sum':'Sum','Skewness':'Skewness','Excess kurtosis':'Kurtosis'}
        for row in c.rows('描述統計'):
            for column,label in mapping.items():
                c.add(f'{row["Variable"]}.{column}',row[column],c.cell('Descriptive Statistics',row['Variable'],label,last='Statistic'),exact=column=='N')
            c.add(f'{row["Variable"]}.Std. error',row['Std. error'],c.cell('Descriptive Statistics',row['Variable'],'Mean',last='Std. Error'))
            for col,percent in [('Q25','25'),('Median','50'),('Q75','75')]:
                c.add(f'{row["Variable"]}.{col}',row[col],c.cell('Percentiles','Weighted Average(Definition 1)',row['Variable'],last=percent))
            for col,side in [('CI lower','Lower Bound'),('CI upper','Upper Bound')]:
                c.add(f'{row["Variable"]}.{col}',row[col],c.cell('Descriptives',row['Variable'],'95% Confidence Interval for Mean',side,last='Statistic'))
    elif method=='frequencies':
        for var in ['group','binary']:
            for row in c.rows(f'{var} 次數分配'):
                label=format_level(row['Value'])
                for column,sp in [('Frequency','Frequency'),('Percent','Percent'),('Valid percent','Valid Percent'),('Cumulative valid percent','Cumulative Percent')]:
                    c.add(f'{var}[{row["Value"]}].{column}',row[column],c.cell('Frequencies',label,last=sp,title=var),exact=column=='Frequency')
    elif method=='crosstabs':
        for table,stat in [('觀察次數','Count'),('期望次數','Expected Count'),('列百分比','% within group'),('欄百分比','% within binary')]:
            for row in c.rows(table):
                level=row['group / binary']
                for binary in [0,1]:
                    # Position distinguishes row category 1 from column category 1.
                    candidates=[cell for t in c.tables if t['subtype']=='Crosstabulation' for cell in t['cells'] if cell['path']==['group',format_level(level),stat,'binary',format_level(binary)]]
                    if len(candidates)!=1:raise AssertionError('Crosstab cell identity not unique')
                    c.add(f'{stat}[{level},{binary}]',row[str(binary)],{'subtype':'Crosstabulation',**candidates[0]},exact=stat=='Count')
        rows=c.rows('關聯檢定')
        for row in rows:
            if row['Test']=='Pearson chi-square':
                for col,sp in [('Statistic','Value'),('df','df'),('p (two-sided where applicable)','Asymptotic Significance (2-sided)')]:
                    c.add('Pearson.'+col,row[col],c.cell('Chi Square Tests','Pearson Chi-Square',last=sp),exact=col=='df',pvalue=col.startswith('p '))
            elif row['Test']=="Cramér's V":
                c.add('CramerV',row['Statistic'],c.cell('Symmetric Measures',"Cramer's V",last='Value'))
    elif method=='ttest_one':
        for row in c.rows('單一樣本 t 檢定'):
            var=row['Variable']
            for col,sp in [('N','N'),('Mean','Mean'),('Std. deviation','Std. Deviation'),('Std. error difference','Std. Error Mean')]:
                c.add(f'{var}.{col}',row[col],c.cell('One Sample Statistics',var,last=sp),exact=col=='N')
            for col,sp in [('t','t'),('df','df'),('p (two-sided)','Two-Sided p'),('Mean difference','Mean Difference'),('CI lower','Lower'),('CI upper','Upper')]:
                c.add(f'{var}.{col}',row[col],c.cell('One Sample Test',var,last=sp),exact=col=='df',pvalue=col.startswith('p '))
    elif method=='ttest_independent':
        for row in c.rows('組別統計'):
            for col,sp in [('N','N'),('Mean','Mean'),('Std. deviation','Std. Deviation'),('Std. error mean','Std. Error Mean')]:
                c.add(f'group{row["Group"]}.{col}',row[col],c.cell('Group Statistics','y',format_level(row['Group']),last=sp),exact=col=='N')
        for row in c.rows('Levene（中心為平均數）'):
            for col,sp in [('F','F'),('p','Sig.')]:
                c.add('Levene.'+col,row[col],c.cell('Independent Samples Test',"Levene's Test for Equality of Variances",last=sp),pvalue=col=='p')
        for row in c.rows('獨立樣本 t 檢定'):
            for col,sp in [('t','t'),('df','df'),('p (two-sided)','Two-Sided p'),('Mean difference','Mean Difference'),('Std. error difference','Std. Error Difference'),('CI lower','Lower'),('CI upper','Upper')]:
                exact=col=='df' and row['Assumption']=='Equal variances assumed'
                c.add(row['Assumption']+'.'+col,row[col],c.cell('Independent Samples Test',row['Assumption'],'t-test for Equality of Means',last=sp),exact=exact,pvalue=col.startswith('p '))
    elif method=='ttest_paired':
        row=c.rows('成對差值 t 檢定')[0]
        c.add('N',row['N'],c.cell('Paired Samples Statistics','paired_a',last='N'),exact=True)
        for col,sp in [('Std. deviation difference','Std. Deviation'),('t','t'),('df','df'),('p (two-sided)','Two-Sided p'),('Mean difference','Mean'),('Std. error difference','Std. Error Mean'),('CI lower','Lower'),('CI upper','Upper')]:
            c.add(col,row[col],c.cell('Paired Samples Test',last=sp),exact=col=='df',pvalue=col.startswith('p '))
    elif method=='anova':
        for row in c.rows('y ANOVA'):
            group=row['Source'].title()
            for col,sp in [('Sum of squares','Sum of Squares'),('df','df'),('Mean square','Mean Square'),('F','F'),('p','Sig.')]:
                if row[col] is not None:c.add(group+'.'+col,row[col],c.cell('ANOVA',group,last=sp),exact=col=='df',pvalue=col=='p')
        row=[r for r in c.rows('y 效果量與同質性') if r['Statistic']=='Levene (mean)'][0]
        c.add('Levene.F',row['Value'],c.cell('Test of Homogeneity of Variance','Based on Mean',last='Levene Statistic'))
        c.add('Levene.p',row['p'],c.cell('Test of Homogeneity of Variance','Based on Mean',last='Sig.'),pvalue=True)
        for row in c.rows('y 各組摘要'):
            for col,sp in [('N','N'),('Mean','Mean'),('Std. deviation','Std. Deviation')]:
                c.add(f'group{row["Group"]}.{col}',row[col],c.cell('Descriptives',format_level(row['Group']),last=sp),exact=col=='N')
    elif method=='correlation':
        for row in c.rows('相關檢定（未做多重比較校正）'):
            a,b=row['Variable 1'],row['Variable 2']
            for col,sp in [('N','N'),('Coefficient','Pearson Correlation'),('p (two-sided)','Sig. (2-tailed)')]:
                c.add(f'{a}-{b}.{col}',row[col],c.cell('Correlations',a,sp,last=b),exact=col=='N',pvalue=col.startswith('p '))
            for col,sp in [('Pearson CI lower','Lower'),('Pearson CI upper','Upper')]:
                c.add(f'{a}-{b}.{col}',row[col],c.cell('Confidence Intervals',f'{a} - {b}',last=sp))
    elif method=='linear_regression':
        for row in c.rows('迴歸係數'):
            term='(Constant)' if row['Term']=='(Intercept)' else row['Term']
            for col,sp in [('B','B'),('Std. error','Std. Error'),('Standardized beta','Beta'),('t','t'),('p (two-sided)','Sig.'),('CI lower','Lower Bound'),('CI upper','Upper Bound')]:
                if row[col] is not None:c.add(term+'.'+col,row[col],c.cell('Coefficients',term,last=sp),pvalue=col.startswith('p '))
        row=c.rows('模型摘要')[0]
        for col,sp in [('R squared','R Square'),('Adjusted R squared','Adjusted R Square'),('Residual std. error','Std. Error of the Estimate')]:
            c.add(col,row[col],c.cell('Model Summary',last=sp))
        for col,sp in [('F','F'),('F p','Sig.')]:c.add(col,row[col],c.cell('ANOVA','Regression',last=sp),pvalue=col=='F p')
        for row in c.rows('ANOVA'):
            group='Total' if row['Source'].startswith('Total') else row['Source']
            for col,sp in [('Sum of squares','Sum of Squares'),('df','df'),('Mean square','Mean Square')]:
                if row[col] is not None:c.add(group+'.'+col,row[col],c.cell('ANOVA',group,last=sp),exact=col=='df')
    elif method=='logistic_regression':
        for row in c.rows('邏輯斯係數'):
            term='Constant' if row['Term']=='(Intercept)' else row['Term']
            for col,sp in [('B','B'),('Std. error','S.E.'),('Wald chi-square','Wald'),('df','df'),('p','Sig.'),('Exp(B)','Exp(B)'),('OR CI lower','Lower'),('OR CI upper','Upper')]:
                if term=='Constant' and col.startswith('OR CI'):continue # SPSS does not print constant OR CI.
                c.add(term+'.'+col,row[col],c.cell('Variables in the Equation','Step 1',term,last=sp),exact=col=='df',pvalue=col=='p')
        row=c.rows('模型摘要')[0]
        for col,sp in [('−2 Log likelihood','-2 Log likelihood'),('Cox–Snell R squared','Cox & Snell R Square'),('Nagelkerke R squared','Nagelkerke R Square')]:
            c.add(col,row[col],c.cell('Model Summary',last=sp))
        for col,sp in [('LR chi-square','Chi-square'),('df','df'),('LR p','Sig.')]:c.add(col,row[col],c.cell('Omnibus Tests of Model Coefficients','Model',last=sp),exact=col=='df',pvalue=col=='LR p')
        c.add('N',row['N'],c.cell('Case Processing Summary','Included in Analysis',last='N'),exact=True)
        for row in c.rows('分類表（臨界值 0.5）'):
            for predicted in [0,1]:
                path=['Step 1','binary',format_level(row['Observed']),'binary',format_level(predicted)]
                cells=[cell for t in c.tables if t['subtype']=='Classification Table' for cell in t['cells'] if cell['path']==path]
                if len(cells)!=1:raise AssertionError('Classification source not unique')
                c.add(f'classification[{row["Observed"]},{predicted}]',row[f'Predicted {predicted}'],{'subtype':'Classification Table',**cells[0]},exact=True)
    elif method=='reliability':
        row=c.rows('信度摘要')[0]
        c.add('N',row['N'],c.cell('Case Processing Summary','Valid',last='N'),exact=True)
        for col,sp in [('Items','N of Items'),('Cronbach alpha',"Cronbach's Alpha"),('Standardized alpha',"Cronbach's Alpha Based on Standardized Items")]:
            c.add(col,row[col],c.cell('Reliability Statistics',last=sp),exact=col=='Items')
        for row in c.rows('項目總分統計'):
            for col,sp in [('Scale mean if deleted','Scale Mean if Item Deleted'),('Scale variance if deleted','Scale Variance if Item Deleted'),('Corrected item-total correlation','Corrected Item-Total Correlation'),('Alpha if deleted',"Cronbach's Alpha if Item Deleted")]:
                c.add(row['Item']+'.'+col,row[col],c.cell('Item Total Statistics',row['Item'],last=sp))
    elif method=='pca':
        for row in c.rows('初始特徵值'):
            for col,sp in [('Eigenvalue','Total'),('% variance','% of Variance'),('Cumulative %','Cumulative %')]:
                c.add(f'component{row["Component"]}.{col}',row[col],c.cell('Total Variance Explained',str(row['Component']),'Initial Eigenvalues',last=sp))
        for row in c.rows('成分負荷量'):
            for component in [1,2]:c.add(f'{row["Variable"]}.loading{component}',row[f'Component {component}'],c.cell('Factor Matrix',row['Variable'],last=str(component)))
        for row in c.rows('共同性'):
            for col in ['Initial','Extraction']:c.add(row['Variable']+'.'+col,row[col],c.cell('Communalities',row['Variable'],last=col))
    elif method in ('mann_whitney','kruskal'):
        ranktable='Mann Whitney Ranks' if method=='mann_whitney' else 'Kruskal Wallis Ranks'
        for row in c.rows('各組等級'):
            for col,sp in [('N','N'),('Mean rank','Mean Rank'),('Sum of ranks','Sum of Ranks')]:
                if method=='kruskal' and col=='Sum of ranks':continue
                c.add(f'group{row["Group"]}.{col}',row[col],c.cell(ranktable,format_level(row['Group']),last=sp),exact=col in ('N','Sum of ranks'))
        if method=='mann_whitney':
            row=c.rows('Mann–Whitney U')[0]
            for col,sp in [('Minimum U','Mann-Whitney U'),('p (two-sided)','Asymp. Sig. (2-tailed)')]:
                c.add(col,row[col],c.cell('Mann Whitney Test Statistics',sp,last='y'),exact=col=='Minimum U',pvalue=col.startswith('p '))
        else:
            row=c.rows('Kruskal–Wallis')[0]
            for col,sp in [('H','Kruskal-Wallis H'),('df','df'),('p','Asymp. Sig.')]:c.add(col,row[col],c.cell('Kruskal Wallis Test Statistics',sp,last='y'),exact=col=='df',pvalue=col=='p')
    elif method=='wilcoxon':
        row=c.rows('Wilcoxon 符號等級')[0]
        for col,category,stat in [('N paired','Total','N'),('Zero differences','Ties','N'),('Negative rank sum','Negative Ranks','Sum of Ranks'),('Positive rank sum','Positive Ranks','Sum of Ranks')]:
            c.add(col,row[col],c.cell('Wilcoxon Ranks',category,last=stat),exact=True)
        for col,sp in [('z','Z'),('p (two-sided)','Asymp. Sig. (2-tailed)')]:c.add(col,row[col],c.cell('Wilcoxon Test Statistics',sp),pvalue=col.startswith('p '))
    elif method=='factor':
        for row in c.rows('因素負荷量'):c.add(row['Variable']+'.loading',row['Factor 1'],c.cell('Factor Matrix',row['Variable'],last='1'))
        for row in c.rows('共同性'):
            for col,sp in [('Initial SMC','Initial'),('Extraction','Extraction')]:c.add(row['Variable']+'.'+col,row[col],c.cell('Communalities',row['Variable'],last=sp))
        for row in c.rows('KMO 與 Bartlett 球形檢定'):
            if row['Statistic']=='KMO':c.add('KMO',row['Value'],c.cell('KMO and Bartlett Test',last='Kaiser-Meyer-Olkin Measure of Sampling Adequacy.'))
            else:
                for col,sp in [('Value','Approx. Chi-Square'),('df','df'),('p','Sig.')]:c.add('Bartlett.'+col,row[col],c.cell('KMO and Bartlett Test',last=sp),exact=col=='df',pvalue=col=='p')
    elif method=='hierarchical':
        complete=pd.read_csv(c.input)[['x','z']].dropna()
        members={i:{int(idx)+1} for i,idx in enumerate(complete.index)}
        n=len(members)
        for row in c.rows('合併歷程（原始個案節點從 0 開始）'):
            stage=str(row['Step'])
            c.add('merge'+stage+'.distance',row['Distance'],c.cell('Agglomeration Schedule',stage,last='Coefficients'))
            left,right=members[int(row['Left node'])],members[int(row['Right node'])]
            reps=sorted([min(left),min(right)])
            for index,representative in enumerate(reps,1):
                c.add('merge'+stage+f'.representative{index}',representative,c.cell('Agglomeration Schedule',stage,'Cluster Combined',last=f'Cluster {index}'),exact=True)
            members[n+int(stage)-1]=left|right
        for row in c.rows('個案群別'):
            c.add(f'row{row["Data row (1-based)"]}.native_cluster_id',row['Cluster'],c.cell('Cluster Membership',str(row['Data row (1-based)']),last='3 Clusters'),exact=True)
    elif method=='kmeans':
        for row in c.rows('群中心（原始單位）'):
            cluster=str(row['Cluster'])
            for col in ['x','z']:c.add(f'cluster{cluster}.{col}',row[col],c.cell('Final Cluster Centers',col,last=cluster))
            c.add(f'cluster{cluster}.N',row['N'],c.cell('Number of Cases in each Cluster','Cluster',last=cluster),exact=True)
        for row in c.rows('個案群別'):
            c.add(f'row{row["Data row (1-based)"]}.native_cluster_id',row['Cluster'],c.cell('Cluster Membership',str(row['Data row (1-based)']),last='Cluster'),exact=True)
    if not c.checks:raise AssertionError('No checks generated')
    oracle_sources={c.oracle.name:sha(c.oracle)}
    if method=='descriptive':oracle_sources['examine.xml']=sha(c.oracle.with_name('examine.xml'))
    return {'fixture':fixture,'method':method,'options':CASES[method],'fixture_sha256':sha(c.input),'oracle_sha256':sha(c.oracle),'oracle_sources':oracle_sources,'checks':c.checks,'counts':dict(Counter(v['status'] for v in c.checks)),'scope':'Only these selected raw numeric cells; no whole-procedure parity claim.'}


def format_level(value):
    text=f'{value:.10f}'
    return text[1:] if text.startswith('0.') else text


def run():
    reports=[compare_case(fixture,method) for fixture in ['reference','reference_missing'] for method in CASES]
    summary={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'engine_sha256':sha(ROOT/'src'/'statstudio'/'engine.py'),'numeric_libraries':{name:importlib.metadata.version(name) for name in ['numpy','pandas','scipy','scikit-learn','statsmodels']},'policy':{'continuous':'atol=1e-10, rtol=1e-8','probabilities':'atol=0, rtol=1e-7','integer_counts_df':'exact; fractional Welch df uses continuous tolerance','source_precision':'OXML number attributes, generally 14 significant digits; unrounded display not a raw binary dump','alignment':'No rounding, PCA sign alignment or label permutations'},'counts':dict(Counter(check['status'] for result in reports for check in result['checks'])),'cases':reports}
    path=ROOT/'validation'/'parity-report.json'
    path.write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    (ROOT/'validation'/'analysis-specs.json').write_text(json.dumps(CASES,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for report in reports:
        print(report['fixture'],report['method'],report['counts'])
        for check in report['checks']:
            if check['status']=='failed':print('  FAILED',check['metric'],check['actual'],check['expected'],check['abs_error'])
    print('TOTAL',summary['counts'])
    return summary


if __name__=='__main__':
    raise SystemExit(1 if run()['counts'].get('failed',0) else 0)
