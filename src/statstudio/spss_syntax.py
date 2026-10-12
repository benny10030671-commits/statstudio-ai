"""Small, explicit SPSS command surface. No user-provided executable syntax."""
import math
import re

# Options deliberately differ from the independent engine. Never silently ignore any.
SPECS = {
    'descriptive': ('描述統計與分布', ['variables'], {}),
    'frequencies': ('次數與百分比', ['variables'], {}),
    'crosstabs': ('交叉表與卡方', ['row', 'column'], {}),
    'ttest_one': ('單樣本 t 檢定', ['variables'], {'test_value': 0.0, 'confidence': .95}),
    'ttest_independent': ('獨立樣本 t 檢定', ['variables', 'group', 'group_values'], {'confidence': .95}),
    'ttest_paired': ('成對樣本 t 檢定', ['before', 'after'], {'confidence': .95}),
    'anova': ('單因子 ANOVA 與 Welch', ['variables', 'group'], {}),
    'correlation': ('Pearson / Spearman 相關', ['variables'], {'coefficient': 'pearson'}),
    'linear_regression': ('線性迴歸', ['target', 'predictors'], {'confidence': .95}),
    'logistic_regression': ('二元邏輯斯迴歸', ['target', 'predictors'], {'confidence': .95}),
    'reliability': ('Cronbach alpha', ['variables'], {}),
    'mann_whitney': ('Mann–Whitney', ['variables', 'group', 'group_values'], {}),
    'wilcoxon': ('Wilcoxon 符號等級', ['before', 'after'], {}),
    'kruskal': ('Kruskal–Wallis', ['variables', 'group', 'group_values'], {}),
    'pca': ('主成分分析（不旋轉）', ['variables'], {'components': 2}),
    'factor': ('主軸因子分析（不旋轉）', ['variables'], {'components': 1}),
    'kmeans': ('K-means（原始尺度）', ['variables'], {'clusters': 3}),
    'hierarchical': ('平均連結階層分群（平方歐氏距離）', ['variables'], {'clusters': 3}),
}
LIST_ROLES = {'variables', 'predictors'}
SINGLE_ROLES = {'row', 'column', 'group', 'before', 'after', 'target'}


def methods():
    return [{'method': k, 'label': label, 'required_options': roles,
             'optional_defaults': dict(defaults, plots=True),
             'limitations': '未支援任意 syntax、權重、FILTER、SPLIT FILE；相關採 pairwise，其餘依原生語法記錄缺失處理。'}
            for k, (label, roles, defaults) in SPECS.items()]


def variable(value):
    # Conservative subset including Chinese identifiers, excluding syntax metacharacters.
    if not isinstance(value, str) or not re.fullmatch(r'[^\W\d]\w{0,63}', value) or len(value.encode('utf-8')) > 64:
        raise ValueError('SPSS variable name is outside the supported safe identifier subset.')
    return value


def quote(value):
    text = str(value).replace('\\', '/')
    if any(ord(c) < 32 for c in text):
        raise ValueError('SPSS paths cannot contain control characters.')
    return "'" + text.replace("'", "''") + "'"


def normalize(method, options):
    if method not in SPECS:
        raise ValueError('Unsupported SPSS method: ' + str(method))
    _, required, defaults = SPECS[method]
    allowed = set(required) | set(defaults) | {'plots'}
    if not isinstance(options, dict) or set(options) - allowed or set(required) - set(options):
        raise ValueError(f'{method}: required={required}; allowed={sorted(allowed)}')
    result = dict(defaults, plots=True)
    result.update(options)
    if type(result['plots']) is not bool:
        raise ValueError('plots must be boolean.')
    for key in LIST_ROLES & result.keys():
        value = result[key]
        if not isinstance(value, list) or not 1 <= len(value) <= 30 or any(not isinstance(x, str) or not x for x in value) or len(set(value)) != len(value):
            raise ValueError(f'{key} needs 1–30 unique column names.')
    for key in SINGLE_ROLES & result.keys():
        if not isinstance(result[key], str) or not result[key]:
            raise ValueError(f'{key} needs one column name.')
    for key in ('confidence', 'test_value'):
        if key in result and (type(result[key]) not in (int, float) or not math.isfinite(result[key])):
            raise ValueError(f'{key} must be finite numeric.')
    if 'confidence' in result and not .5 < result['confidence'] < 1:
        raise ValueError('confidence must be between .5 and 1 (exclusive).')
    if 'group_values' in result:
        values = result['group_values']
        if not isinstance(values, list) or len(values) != 2 or any(type(x) not in (int, float) or not math.isfinite(x) for x in values) or values[0] == values[1]:
            raise ValueError('group_values must contain two different finite numeric codes (min/max for Kruskal).')
        if method == 'kruskal' and values[0] > values[1]:
            raise ValueError('Kruskal group range must be ascending.')
    if result.get('coefficient', 'pearson') not in ('pearson', 'spearman'):
        raise ValueError('coefficient must be pearson or spearman.')
    for key in ('components', 'clusters'):
        if key in result and (type(result[key]) is not int or not 1 <= result[key] <= 30):
            raise ValueError(f'{key} must be an integer from 1 to 30.')
    if method in ('correlation', 'reliability', 'pca', 'factor', 'kmeans', 'hierarchical') and len(result['variables']) < 2:
        raise ValueError('This method requires at least two variables.')
    if 'components' in result and result['components'] > len(result['variables']):
        raise ValueError('Components cannot exceed variables.')
    if 'clusters' in result and result['clusters'] < 2:
        raise ValueError('At least two clusters required.')
    if 'before' in result and result['before'] == result['after']:
        raise ValueError('Before/after must be different columns.')
    if 'target' in result and result['target'] in result['predictors']:
        raise ValueError('Target cannot also be a predictor.')
    if 'group' in result and result['group'] in result.get('variables', []):
        raise ValueError('Group cannot also be an outcome.')
    return result


def used_columns(options):
    return list(dict.fromkeys([x for k in LIST_ROLES if k in options for x in options[k]] +
                              [options[k] for k in sorted(SINGLE_ROLES) if k in options]))


def build(method, options, mapping):
    o = normalize(method, options)
    def col(name):
        if name not in mapping:
            raise ValueError('Unknown column: ' + name)
        return variable(mapping[name])
    def cols(key='variables'):
        return ' '.join(col(x) for x in o[key])
    v = cols() if 'variables' in o else ''
    ci = o.get('confidence', .95)
    pct = format(ci * 100, '.12g')
    group = col(o['group']) if 'group' in o else ''
    codes = ' '.join(format(x, '.17g') for x in o.get('group_values', []))
    commands = []
    if method == 'descriptive':
        commands = [f'EXAMINE VARIABLES={v} /PLOT {"BOXPLOT HISTOGRAM NPPLOT" if o["plots"] else "NONE"} /STATISTICS DESCRIPTIVES /PERCENTILES(25,50,75) HAVERAGE /CINTERVAL 95 /MISSING PAIRWISE.']
    elif method == 'frequencies':
        commands = [f'FREQUENCIES VARIABLES={v} /FORMAT=AVALUE' + (' /BARCHART FREQ' if o['plots'] else '') + '.']
    elif method == 'crosstabs':
        commands = [f'CROSSTABS /TABLES={col(o["row"])} BY {col(o["column"])} /STATISTICS=CHISQ PHI /CELLS=COUNT EXPECTED ROW COLUMN TOTAL' + (' /BARCHART' if o['plots'] else '') + '.']
    elif method == 'ttest_one':
        commands = [f'T-TEST /TESTVAL={o["test_value"]:.17g} /VARIABLES={v} /MISSING=ANALYSIS /CRITERIA=CI({ci}).']
    elif method == 'ttest_independent':
        commands = [f'T-TEST GROUPS={group}({codes}) /VARIABLES={v} /MISSING=ANALYSIS /CRITERIA=CI({ci}).']
    elif method == 'ttest_paired':
        commands = [f'T-TEST PAIRS={col(o["after"])} WITH {col(o["before"])} (PAIRED) /MISSING=ANALYSIS /CRITERIA=CI({ci}).']
    elif method == 'anova':
        commands = [f'ONEWAY {v} BY {group} /STATISTICS DESCRIPTIVES HOMOGENEITY WELCH /MISSING ANALYSIS.']
    elif method == 'correlation':
        prefix = 'CORRELATIONS' if o['coefficient'] == 'pearson' else 'NONPAR CORR'
        extra = '/PRINT=TWOTAIL NOSIG /STATISTICS DESCRIPTIVES' if o['coefficient'] == 'pearson' else '/PRINT=SPEARMAN TWOTAIL NOSIG'
        commands = [f'{prefix} VARIABLES={v} {extra} /MISSING=PAIRWISE.']
    elif method == 'linear_regression':
        commands = [f'REGRESSION /MISSING LISTWISE /STATISTICS COEFF R ANOVA CI({pct}) COLLIN TOL /NOORIGIN /DEPENDENT {col(o["target"])} /METHOD=ENTER {cols("predictors")}' + (' /SCATTERPLOT=(*ZRESID,*ZPRED) /RESIDUALS HISTOGRAM(ZRESID) NORMPROB(ZRESID)' if o['plots'] else '') + '.']
    elif method == 'logistic_regression':
        commands = [f'LOGISTIC REGRESSION VARIABLES {col(o["target"])} /METHOD=ENTER {cols("predictors")} /PRINT=CI({pct}) GOODFIT /CRITERIA=ITERATE(100) CUT(.5).']
    elif method == 'reliability':
        commands = [f"RELIABILITY /VARIABLES={v} /SCALE('All Items') ALL /MODEL=ALPHA /STATISTICS=DESCRIPTIVE SCALE CORR /SUMMARY=TOTAL."]
    elif method in ('mann_whitney', 'kruskal'):
        test = 'M-W' if method == 'mann_whitney' else 'K-W'
        commands = [f'NPAR TESTS /{test}={v} BY {group}({codes}) /MISSING ANALYSIS.']
    elif method == 'wilcoxon':
        # NPAR labels its contrast second-minus-first, unlike T-TEST.
        commands = [f'NPAR TESTS /WILCOXON={col(o["before"])} WITH {col(o["after"])} (PAIRED) /MISSING ANALYSIS.']
    elif method in ('pca', 'factor'):
        extraction = 'PC' if method == 'pca' else 'PAF'
        commands = [f'FACTOR /VARIABLES={v} /MISSING=LISTWISE /ANALYSIS={v} /PRINT=INITIAL EXTRACTION KMO' + (' /PLOT=EIGEN' if o['plots'] else '') + f' /CRITERIA=FACTORS({o["components"]}) ITERATE(100) /EXTRACTION={extraction} /ROTATION=NOROTATE /METHOD=CORRELATION.']
    elif method == 'kmeans':
        commands = [f'QUICK CLUSTER {v} /MISSING=LISTWISE /CRITERIA=CLUSTER({o["clusters"]}) NOINITIAL MXITER(300) CONVERGE(0) /METHOD=KMEANS(NOUPDATE) /PRINT=INITIAL CLUSTER.']
    elif method == 'hierarchical':
        commands = [f'CLUSTER {v} /METHOD=BAVERAGE /MEASURE=SEUCLID /PRINT=SCHEDULE CLUSTER({o["clusters"]}) /PLOT={"DENDROGRAM" if o["plots"] else "NONE"}.']
    if o['plots']:
        if method in ('ttest_independent', 'anova', 'mann_whitney', 'kruskal'):
            commands.append(f'EXAMINE VARIABLES={v} BY {group} /PLOT BOXPLOT /STATISTICS DESCRIPTIVES /MISSING PAIRWISE /NOTOTAL.')
        elif method == 'ttest_one':
            commands.append(f'EXAMINE VARIABLES={v} /PLOT HISTOGRAM NPPLOT /STATISTICS DESCRIPTIVES /MISSING PAIRWISE.')
        elif method in ('ttest_paired', 'wilcoxon'):
            commands.append(f'GRAPH /SCATTERPLOT(BIVAR)={col(o["before"])} WITH {col(o["after"])}.')
            difference = 'SSDIFF'
            while difference.casefold() in {x.casefold() for x in mapping.values()}:
                difference += 'X'
            commands.extend([f'COMPUTE {difference}={col(o["after"])}-{col(o["before"])}.',
                             f"VARIABLE LABELS {difference} 'After minus before (paired difference)'.",
                             f'EXAMINE VARIABLES={difference} /PLOT BOXPLOT HISTOGRAM NPPLOT /STATISTICS DESCRIPTIVES /MISSING LISTWISE.'])
        elif method == 'correlation':
            commands.append(f'GRAPH /SCATTERPLOT(BIVAR)={col(o["variables"][0])} WITH {col(o["variables"][1])}.')
        elif method in ('linear_regression', 'logistic_regression'):
            commands.append(f'GRAPH /SCATTERPLOT(BIVAR)={col(o["predictors"][0])} WITH {col(o["target"])}.')
    return commands
