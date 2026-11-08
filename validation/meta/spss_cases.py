"""Fixed synthetic inputs for native SPSS meta-analysis regression checks."""

HETEROGENEOUS = [
    ['S1', 12, 100, 18, 98], ['S2', 3, 40, 5, 42],
    ['S3', 0, 30, 2, 31], ['S4', 45, 500, 40, 490],
    ['S5', 8, 60, 19, 58], ['S6', 10, 150, 35, 148],
]
LOW_Q = [
    ['L1', 10, 100, 11, 100], ['L2', 12, 100, 13, 100],
    ['L3', 13, 100, 12, 100], ['L4', 8, 100, 9, 100],
]
DOUBLE_ZERO = [row[:] for row in HETEROGENEOUS]
DOUBLE_ZERO[2][3] = 0


def case(name, rows, measure='OR', tau2_method='DL', confidence=0.95):
    return {'id': name, 'rows': rows, 'options': {
        'measure': measure, 'tau2_method': tau2_method, 'confidence': confidence,
    }}


CASES = [
    case('heterogeneous_or_dl', HETEROGENEOUS),
    case('heterogeneous_or_reml', HETEROGENEOUS, tau2_method='REML'),
    case('low_q_or_dl', LOW_Q),
    case('low_q_or_reml', LOW_Q, tau2_method='REML'),
    case('heterogeneous_rr_dl', HETEROGENEOUS, measure='RR'),
    case('low_q_rr_dl', LOW_Q, measure='RR'),
    case('two_studies_or_dl', HETEROGENEOUS[:2]),
    case('three_studies_or_dl', HETEROGENEOUS[:3]),
    case('double_zero_or_dl', DOUBLE_ZERO),
    case('confidence90_or_dl', HETEROGENEOUS, confidence=0.90),
]
