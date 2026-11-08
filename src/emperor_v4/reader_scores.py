"""Fixed public display scales. Never used for settlement, weights or ranking."""
from copy import deepcopy
import math

VERSION = 'public-performance-scales-v3-component-trial'
BANDS = ((98, 'S+'), (95, 'S'), (90, 'A'), (85, 'B'),
         (82, 'C+'), (78, 'C'), (75, 'C−'), (70, 'D+'),
         (65, 'D'), (60, 'D−'), (50, 'E+'), (40, 'E'), (0, 'E−'))
SCALES = {
    'total': dict(label='综合绩效（原方案对照）', anchors=((0,40),(120,60),(220,75),(320,85),(380,90),(450,95)), tail=140, negative=100),
    'total_trial': dict(label='综合绩效（五档十五级试读）', anchors=((0,20),(80,40),(220,60),(325,80),(400,90),(450,95)), tail=140, negative=100),
    'first': dict(label='政权奠基与统一', anchors=((0,40),(40,60),(80,75),(120,85),(155,90),(190,95)), tail=50, negative=100),
    'second': dict(label='治国成效', anchors=((0,40),(80,60),(130,75),(185,85),(225,90),(270,95)), tail=55, negative=100),
    'third': dict(label='军事与边疆', anchors=((0,40),(35,60),(65,75),(100,85),(130,90),(160,95)), tail=50, negative=100),
    # This is a signed incremental contribution, not a stock of governance.
    'fourth': dict(label='文明与国家整合', anchors=((0,60),(2,75),(5,85),(10,90),(20,95)), tail=20, negative=20),
}

# Provisional reading-layer bands, not formal adjudications or rank quotas.
# Preserve the original percentage scale and letter grade alongside the trial.
MERIT_TRIAL_BANDS = (
    (400, 'sheng', '圣', '综合成就卓越，处于很高水平'),
    (325, 'ming', '明', '综合成绩突出，明显超出一般水平'),
    (220, 'ping', '平', '普通至中等偏上，尚不足以获得突出评价'),
    (80, 'yong', '庸', '整体表现不佳'),
    (None, 'hun', '昏', '整体表现严重不佳'),
)
MERIT_BOUNDARY_DISTANCE = 1.0

# Display anchors are fixed reading conventions, not percentile quotas or new
# adjudications. The first item measures a bounded founder contribution; the
# next two include inherited states and signed losses. The fourth stays signed.
COMPONENT_SCALES = {
    'first': dict(label='政权奠基与统一', anchors=((0,0),(20,20),(40,40),(80,60),(140,80),(180,90),(210,95)), tail=30, negative=None),
    'second': dict(label='治国成效', anchors=((0,20),(100,40),(180,60),(240,80),(285,90),(330,95)), tail=57, negative=100),
    'third': dict(label='军事与边疆', anchors=((0,20),(20,40),(70,60),(120,80),(170,90),(220,95)), tail=30, negative=40),
}
COMPONENT_BANDS = ((90, '卓越'), (80, '突出'), (60, '中等'), (40, '不佳'), (0, '很差'))
FOUNDER_BANDS = ((90, '卓著'), (80, '突出'), (60, '中等'), (40, '有限'), (0, '很有限'))


def merit_levels(index):
    """Thirds of a band, with thresholds on the displayed tenth-point grid."""
    lower = MERIT_TRIAL_BANDS[index][0]
    low = convert(lower, 'total_trial') if lower is not None else 0
    high = convert(MERIT_TRIAL_BANDS[index-1][0], 'total_trial') if index else 100
    return tuple((math.ceil((low + (high-low)*part/3)*10)/10, name)
                 for part, name in enumerate(('下', '中', '上')))


def merit_trial(value):
    """Project a provisional label without changing scores or interpreting zero as neutrality."""
    precise = convert(value, 'total_trial')
    score = rating(value, 'total_trial')['score']
    for index, (lower, code, label, meaning) in enumerate(MERIT_TRIAL_BANDS):
        if lower is not None and value < lower:
            continue
        low_score = convert(lower, 'total_trial') if lower is not None else 0
        high_score = convert(MERIT_TRIAL_BANDS[index-1][0], 'total_trial') if index else 100
        subgrade = next(name for minimum, name in reversed(merit_levels(index)) if score >= minimum)
        boundaries = []
        if index:
            boundaries.append((high_score-precise, MERIT_TRIAL_BANDS[index-1][2]))
        if lower is not None:
            boundaries.append((precise-low_score, MERIT_TRIAL_BANDS[index+1][2]))
        distance, neighbor = min(boundaries)
        return dict(code=code, label=label, display_label=label+subgrade, meaning=meaning,
                    score=score,
                    position=subgrade,
                    boundary_neighbor=neighbor if distance<=MERIT_BOUNDARY_DISTANCE else None)
    raise AssertionError('Incomplete merit trial bands')


def convert(value, key='total'):
    return _convert(value, SCALES[key])


def _convert(value, spec):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Public score requires a finite formal score')
    anchors = spec['anchors']
    if value < 0:
        if spec['negative'] is None:
            raise ValueError('Founder net contribution cannot be negative')
        return anchors[0][1] * math.exp(value / spec['negative'])
    if value >= anchors[-1][0]:
        return 100 - 5 * math.exp(-(value - anchors[-1][0]) / spec['tail'])
    for (x0,y0),(x1,y1) in zip(anchors,anchors[1:]):
        if x0 <= value < x1:
            return y0 + (value-x0)*(y1-y0)/(x1-x0)
    raise AssertionError('Incomplete display scale')


def component_rating(value, key):
    precise = _convert(value, COMPONENT_SCALES[key])
    score = min(99.9, max(0, math.floor(precise * 10) / 10))
    bands = FOUNDER_BANDS if key == 'first' else COMPONENT_BANDS
    grade = next(label for lower, label in bands if score >= lower)
    return dict(state='SCORED', score=score, grade=grade,
                kind='founder_contribution' if key == 'first' else 'performance')


def signed_increment(net, has_results):
    balances = [item['reader_signed_balance'] for item in net['component_details']['civilization']
                if 'reader_signed_balance' in item]
    if len(balances) != 1:
        raise ValueError('Civilization display needs the formal signed balance')
    balance = balances[0]
    positive, negative, count = (balance[k] for k in ('positive_gross', 'negative_gross', 'result_count'))
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0
           for v in (positive, negative)) or type(count) is not int or count < 0:
        raise ValueError('Invalid civilization signed balance')
    value = net['fourth_item_adjustment']
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Invalid civilization net increment')
    if not math.isclose(positive-negative, value, abs_tol=1e-9, rel_tol=0):
        raise ValueError('Civilization gross amounts must match the formal net increment')
    if bool(count) != has_results or bool(positive+negative) != bool(count):
        raise ValueError('Civilization result state and gross amounts disagree')
    return dict(state='SCORED' if count else 'NO_CONFIRMED_CHANGE',
                kind='signed_increment', score=value if count else None,
                grade=('净正向' if value > 0 else '净负向' if value < 0 else '正负相抵') if count else None,
                positive_gross=positive, negative_gross=negative, result_count=count)


def rating(value, key='total'):
    precise = convert(value, key)
    # Truncate rather than round across a boundary. Finite inputs never promise
    # perfection; displayed ties are not formal ranking ties.
    score = min(99.9, max(0, math.floor(precise * 10) / 10))
    band = next(label for lower,label in BANDS if score >= lower)
    return dict(state='SCORED', score=score, grade=band)


def project(net):
    result = {key: rating(net[field], key) for key,field in
              [('total','total_score'),('second','second_item_score'),('third','third_item_score')]}
    result['total']['trial_tier'] = merit_trial(net['total_score'])
    state = net.get('first_item_status')
    result['first'] = rating(net['first_item_raw_score'], 'first') if state == 'APPLICABLE' else dict(
        state='NOT_APPLICABLE' if state == 'NOT_APPLICABLE' else 'PENDING', score=None, grade=None)
    for key, field in [('first', 'first_item_raw_score'), ('second', 'second_item_score'), ('third', 'third_item_score')]:
        if result[key]['state'] == 'SCORED':
            result[key]['trial_rating'] = component_rating(net[field], key)
    readings = [item[key] for item in net['component_details']['civilization']
                for key in ('reader_public_fourth_a','reader_public_fourth_b','reader_public_fourth_c') if key in item]
    if len(readings) != 3:
        raise ValueError('Public civilization score needs all three current axes')
    has_results = any(reading['evidence_items'] for reading in readings)
    signed = signed_increment(net, has_results)
    if has_results:
        result['fourth'] = rating(net['fourth_item_adjustment'], 'fourth')
    else:
        if net['fourth_item_adjustment'] != 0:
            raise ValueError('Nonzero civilization score without established results')
        result['fourth'] = dict(state='NO_CONFIRMED_CHANGE', score=None, grade=None)
    result['fourth']['trial_rating'] = signed
    return result


def metadata():
    return dict(version=VERSION, bands=[dict(minimum=n, grade=g) for n,g in BANDS], scales=deepcopy(SCALES),
                component_trial=dict(status='READING_TRIAL', scales=deepcopy(COMPONENT_SCALES),
                                     bands=[dict(minimum=n, grade=g) for n,g in COMPONENT_BANDS],
                                     founder_bands=[dict(minimum=n, grade=g) for n,g in FOUNDER_BANDS],
                                     fourth=dict(kind='signed_increment', neutral=0, bounded=False)),
                merit_trial=dict(status='READING_TRIAL', boundary_distance=MERIT_BOUNDARY_DISTANCE,
                                 bands=[dict(minimum_raw=n, minimum_score=convert(n,'total_trial') if n is not None else None, code=c, label=l, meaning=m,
                                             levels=[dict(minimum_score=s, position=p, label=l+p) for s,p in merit_levels(i)])
                                 for i,(n,c,l,m) in enumerate(MERIT_TRIAL_BANDS)]))
