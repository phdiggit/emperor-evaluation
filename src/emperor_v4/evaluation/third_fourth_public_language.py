"""Lossless public wording: explicit translations, never deletion of tokens.

Whole-sentence translations are bound to the exact source text. Unknown notation
fails closed so that changing a source cannot silently damage its public meaning.
"""
from __future__ import annotations

import json
import re
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

TRANSLATIONS = json.loads(Path(__file__).with_name('third_fourth_public_translations.json').read_text(encoding='utf-8'))
TERMS = {
    'HIGH': '高位', 'MID': '中位', 'LOW': '低位', 'HIGHEST': '极端上沿',
    'CONFIRMED': '关键结构已证实', 'LOWER_BOUND': '已证实下界，仍有覆盖或上限缺口',
    'PROVISIONAL': '关键证据仍有缺口', 'NOT_APPLICABLE': '不适用',
    'NOT_CLOSED': '终点证据不足', 'UNKNOWN': '证据不足',
    'ML': '重大军事净毁损等级',
    'ML0': '当前未作重大军事净毁损追加', 'ML1': '有限重大军事净毁损',
    'ML2': '明显重大军事净毁损', 'ML3': '严重重大军事净毁损', 'ML4': '极严重重大军事净毁损',
    'EN': '负向安全结果', 'EN1': '局部方向净恶化',
    'EN2': '主要方向耐久恶化', 'EN3': '全国或多数核心防务体系崩溃',
    'E': '正向安全结果', 'E0': '没有净安全改善', 'E1': '止损或恢复原线',
    'E2': '区域方向稳定或恢复', 'E3': '重大阶段或区域终局成果',
    'E3_MAJOR_STAGE': '重大阶段成果', 'E3_REGIONAL_TERMINAL': '区域终局成果',
    'E4': '主要战略方向的耐久改善', 'E4_MAJOR_STRATEGIC': '主要战略方向的耐久改善',
    'E5': '全国防务威胁终结或跨方向战略体系重构',
    'E5A': '全国防务威胁体系终结或不可逆降级', 'E5B': '跨重要方向的长期战略体系重构',
    'F': '军队组织毁损', 'F2': '军队组织第二级毁损',
    'F3': '主要方向兵团组织严重毁损', 'F4': '国家主力组织瓦解',
    'A1': '主要安全威胁与战略主动', 'A2': '防线协同与战略纵深',
    'B1': '实际控制范围', 'B2': '战略成果价值', 'B4': '控制成果稳定性',
    'A': '安全态势', 'B': '控制成果', 'AB': '战略安全与边疆控制',
    'C': '军事体系', 'D': '战略安全净变化',
    'FULL': '本人承担主要责任', 'SHARED': '共同责任', 'NONE': '未确认本人责任',
    'MATERIAL': '本人负有实质责任', 'DIRECT_MAJOR_DRIVER': '本人直接主导',
    'MATERIAL_CONTRIBUTOR': '本人具有实质推动作用',
    'INHERITED_ONLY': '仅属继承状态', 'NEGATIVE': '负向', 'POSITIVE': '正向',
    'LOW_RETURN': '低回报', 'HIGH_RETURN': '高回报', 'NEGATIVE_RETURN': '负回报',
    'PROPORTIONATE_RETURN': '回报与投入相称',
}
DOMAIN = ContextVar('public_language_domain', default='military')

@contextmanager
def language_domain(domain):
    token = DOMAIN.set(domain)
    try:
        yield
    finally:
        DOMAIN.reset(token)

TERMS.update({
    'R03':'现行军事成本规则', 'current':'当前任务', 'provisional':'关键证据仍有缺口',
    'return_class':'任务回报类别', 'P':'正向变化', 'N':'负向变化',
    'capability-only':'仅作能力证据', 'cost_band':'军事成本等级', 'status':'证据状态',
    'CAPABILITY_ONLY':'仅作能力证据', 'TALENT-SUPPLEMENT':'军事人才补充材料',
    'closed':'已完成', 'campaign':'战役', 'parent':'所属完整行动',
    'S5':'第五级系统损害', 'gate':'准入条件', 'R':'相对变化',
    'W30_100':'三十万至一百万规模的动员', 'W10':'十万规模的动员',
    'raw':'初步评定', 'final':'最终评定', 'C-3':'军事体系整体第三级', 'C-1':'军事体系整体第一级',
    'PDF':'文献全文', 'campaign_group':'战役群', 'headline':'总体结果',
    'bonus':'额外加分', 'PROPORTIONATE':'回报与投入相称', 'factual':'事实评价', 'axes':'各方面',
    'ref':'证据引用', 'major_system_success_refs':'重大军事体系成功的证据数',
    'ROUTINE_MAINTENANCE':'既有体系的常规维持', 'handoff':'交班',
    'start':'起点值', 'end':'终点值', 'weighted':'加权值', 'rate':'采用比例',
    'net':'净变化', 'terminal':'终局', 'override':'强制修正', 'ID':'标识',
    'terminal_collapse_override':'按终局崩溃强制清零', 'scoring_end':'计分终点', 'carryout':'继承存量',
    'CAMPAIGN-FEISHUI-382-383':'382—383年淝水战争',
    'NC-SONG-YIZHOU-REBELLION-432-437':'432—437年益州民变',
    'NC-V133-LEAD-133-02':'刘彧死后幼主时期的军事行动',
    'NC-V133-LEAD-133-03':'474年桂阳王休范进攻建康',
    'PINGYANG-318':'318年平阳军事行动', 'WAR-LEAD-HAN-XIONGNU-162':'前162年汉匈战争',
    'LIANG-387':'387年凉州军事行动',
    'HAMI_GATEWAY':'哈密门户', 'HENAN_LUOYANG_FORWARD_CORRIDOR':'河南—洛阳前沿走廊',
    'HEXI_NINGXIA_ORDOS':'河西—宁夏—鄂尔多斯', 'HENAN_SHUOFANG':'河南—朔方',
    'GAOCHANG_XIZHOU':'高昌—西州', 'NORTHERN_FRONTIER':'北方边疆',
    'TANG_HEXI_LONGYOU':'唐代河西—陇右', 'HEXI_LONGYOU_CORRIDOR':'河西—陇右走廊',
    'SOUTHERN_MING_HONGGUANG_CORE':'南明弘光核心区', 'SOUTHERN_MING_YONGLI_CORE':'南明永历核心区',
    'HANZHONG_QINLING_FRONTIER':'汉中—秦岭北部门户边疆', 'SOUTHWEST_FRONTIER':'西南边疆',
})
for i in range(8):
    TERMS[f'C{i}'] = f'军事成本第{i}级'
for i in range(7):
    TERMS[f'D{i}'] = f'战略安全净变化第{i}级'
    TERMS[f'O{i}'] = f'对手挑战第{i}级'
    TERMS[f'CIV{i}'] = f'文明影响幅度第{i}级'
    TERMS[f'R{i}'] = f'相对变化第{i}级'
    for code, label in [('M', '军事动员'), ('P', '人员损失'), ('N', '负向变化'), ('H', '交班稳定性'), ('SB', '阶段安全收益'), ('SN', '阶段安全损害'), ('BCP', '控制收益'), ('BCN', '控制损失'), ('BC', '控制变化')]:
        TERMS[f'{code}{i}'] = f'{label}第{i}级'
for i in (3,4,5):
    TERMS[f'A{i}'] = f'军事资产损失第{i}级'

TOKEN = re.compile(r'[A-Za-z][A-Za-z0-9_]*(?:-[A-Za-z0-9_]+)*')

def translate(text: str) -> str:
    if text in TRANSLATIONS:
        return TRANSLATIONS[text]
    # Resolve explicitly qualified cross-item codes before this module's local
    # military/civilization vocabulary; C3 and B2 have different constructs.
    for code, label in {
        'A': '制度建设', 'B1': '官僚治理与行政执行',
        'B2': '反馈纠错与权力约束', 'C1': '民生福祉',
        'C2': '经济活力与财政健康', 'C3': '社会安全',
        'C4': '社会恢复与可归责恶化',
    }.items():
        text = re.sub(r'第二项\s*'+code+r'(?![A-Za-z0-9])', '第二项'+label, text)
    text = re.sub(r'(?:人物|画像)M1(?![A-Za-z0-9])', '人物画像军事判断与统帅能力', text)
    # These are explicitly labelled provenance tails, not parts of a verdict.
    # The original record and reader source references retain the identifiers.
    text = re.sub(r'(?:依据链|依据)[:：](?=(?:[A-Z][A-Z0-9]*(?:-|_|::)|docs/))[^。]*(?:。|$)', '', text)
    text = re.sub(r'https://zh\.wikisource\.org/wiki/([^（）、，。\s]+)', r'《\1》', text)
    text = text.replace('P2-N3', '正向第二级与负向第三级合并').replace('P3-N2', '正向第三级与负向第二级合并')
    has_axis_list = bool(re.search(r'C[123]/C[123]', text))
    for axis, label in {'C1':'实战任务交付','C2':'持续作战与任务承载','C3':'军事体系可靠性'}.items():
        if has_axis_list:
            text = re.sub(axis+r'(?![\d-])', label, text)
    def token(match: re.Match[str]) -> str:
        value = match.group()
        if DOMAIN.get() == 'capability' and re.fullmatch(r'C[0-5]', value):
            return '军事体系整体第'+value[1]+'级'
        if DOMAIN.get() == 'civilization':
            if re.fullmatch(r'[PNH][0-4]', value):
                return {'P':'正向变化','N':'负向变化','H':'重大负向限制'}[value[0]]+'第'+value[1]+'级'
            if value in {'A','B','C'}:
                return {'A':'共同体与社会整合','B':'教育与人才流动','C':'知识与文化生态'}[value]
        numeric = re.fullmatch(r'(start|end|weighted|rate|HAMI_GATEWAY)([0-9]+)', value)
        if numeric:
            return TERMS[numeric[1]]+numeric[2]
        if value in TERMS:
            return TERMS[value]
        if value in TRANSLATIONS:
            return TRANSLATIONS[value]
        graded = re.fullmatch(r'(A[12]|B[124]|C[123])(?:-|S)([0-6])', value)
        if graded:
            label = {'C1':'实战任务交付','C2':'持续作战与任务承载','C3':'军事体系可靠性'}.get(graded[1], TERMS.get(graded[1]))
            return f'{label}第{graded[2]}级'
        positioned = re.fullmatch(r'(.+)-(LOW|MID|HIGH|HIGHEST)', value)
        if positioned and positioned[1] in TERMS:
            return TERMS[positioned[1]]+'、'+TERMS[positioned[2]]
        raise ValueError(f'公开文本需要明确中文转述，禁止删词：{value}；原文：{text}')
    return TOKEN.sub(token, text).replace('级级', '级').replace('级档', '级')
