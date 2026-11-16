"""Shared reading notes for the ranking and evidence views."""

SCORE_INTERVAL_BASIS = '依低置信逐轴终裁的合法端点计算现有史料审慎区间；不是统计置信区间或未来史料的绝对界。'
PARTIAL_SCORE_SUFFIX = ' 另有明确未量化缺口；本区间只覆盖可量化部分，不是全部证据解释的完整边界。'
ASSESSMENT_BASIS = ('正式分数和名次采用当前裁决。现有史料审慎区间按逐人条件档位与联动另列；'
                    '候选端点并非已采信的替代分数，亦不生成候选名次。新增史料可以重开。')
PARTIAL_ASSESSMENT_SUFFIX = ' 未量化事项不作零分差，不据已列区间宣称完整分数或名次范围。'

GUIDE = {
    'interval': ('审慎分数区间',
                 '按现有史料可定位的条件档位及其联动重算，沿用现行权重。上下端是这些条件下的保守界限，概率未估计。'
                 '单点表示已登记材料还未支持可计价的异档。新增史料可重开；完整替代情景另按实际证据验证。'),
    'projection': ('仅重算本人的名次',
                   '把本人区间的两端分别代入正式榜，其他人的正式分数照常采用。只有部分争议可量化时，名次范围也限于这部分。'),
    'scenarios': ('已成立的替代情景',
                  '证据与全部依赖均成立的替代裁决，才列出相应的分数和名次。涉及关联人物时，按完整情景同时重算。'),
    'weights': ('调权情景',
                '沿用正式裁决和评价对象，只变动表列权重。名次范围取所列组合中的最好与最差位置。'),
}


def metadata():
    return {
        'guide': {code: {'label': label, 'text': text} for code, (label, text) in GUIDE.items()},
        'shared_interval_basis': [SCORE_INTERVAL_BASIS, SCORE_INTERVAL_BASIS + PARTIAL_SCORE_SUFFIX],
        'shared_assessment_basis': [ASSESSMENT_BASIS, ASSESSMENT_BASIS + PARTIAL_ASSESSMENT_SUFFIX],
    }
