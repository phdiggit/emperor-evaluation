"""Explicit public wording for civilian outcomes; never delete unknown prose."""
from __future__ import annotations

import json
import re
from pathlib import Path

TRANSLATIONS = json.loads(Path(__file__).with_name('second_item_c_public_translations.json').read_text(encoding='utf-8'))
TERMS = {
    'A': '制度建设', 'D': '军事战略结果',
    'C1': '民生', 'C2': '经济财政', 'C3': '社会安全', 'C4': '恢复与额外代价',
    'C5': '军事成本第五级', 'C6': '军事成本第六级',
    'P': '生产', 'M': '市场与货币', 'F': '财政', 'R': '储备',
    'L': '低谷损害', 'DA': '额外民力成本',
    'S0': '接手状态', 'S_0': '接手状态', 'S_main': '主要阶段状态', 'S_end': '任期结束状态',
    'FULL': '本人独立决定或主导', 'SHARED': '本人和其他掌权者共同承担',
    'NONE': '未确认足够的本人责任', 'LIMITED': '有限', 'UNKNOWN': '证据不足',
    'HIGH': '高位', 'MEDIUM': '中等', 'LOW': '低位',
    'F3': '主要兵团组织严重毁损', 'WAR': '战争损害',
    'raw': '初步判断', 'formal': '正式结果', 'V4': '现行规则',
    'Cambridge': '剑桥相关研究',
    'M2-LSM-E010': '所引江南官署与征发材料',
}
WORDING = {
    '第四项A': '第四项国家共同体与社会整合',
    '第四项B': '第四项教育可及与人才流动',
    '第四项C': '第四项知识生产与文化生态',
    'V4消费核对：': '与已经计入的结果分别核对：',
    '按当前已证责任窗口保留必要安全/治理基线排除；现有正式证据未闭合另一个可选择民力增量。': '本人掌权时期维持基本安全和治理所需的投入已排除；现有证据不足以证明除此之外还有可选择的新增民力负担。',
    '不按L扣分大小另加成本': '不会因低谷扣分较多就另加成本扣分',
    '低起点不单扣': '接手时状态较差本身不另外扣分',
    '继承严刑不倒算': '继承的严刑不直接算作本人新增损害',
    '不以政策名补低谷': '不能仅凭政策名称推定低谷损害',
    '三轴状态链': '民生、经济财政与社会安全结果',
    '三轴之外': '民生、经济财政与社会安全之外',
    '民力对象': '民力负担', '民役对象': '民役负担',
    '实际最高权力窗口': '实际掌权时期',
    '不把自然灾害归责本人': '不把自然灾害认定为本人造成',
    '不归责于皇帝本人': '不认定为皇帝本人造成',
    '不归责本人': '不认定为本人造成',
    '本人是否归责': '本人是否应承担责任',
    '共享期不独占归责': '共同掌权时期的责任不全部归于本人',
    '可归责恶化': '本人造成或放大的恶化',
    '可归责部分': '应由本人承担责任的部分',
    '可归责军费': '应由本人承担责任的军费',
    '归责FULL': '由本人主导并承担责任',
    '归责': '责任归属',
    'general prosperity': '普遍繁荣',
    '主态': '主要阶段状态', '主档': '主要状态等级', '低谷修正': '低谷损害',
    '消费': '计入', '去重': '避免重复计算', '净恢复': '保留的恢复',
    '净账': '净结果', '净分': '净得分', '闭合': '证实', '门槛': '条件',
    '父链': '完整事件链', '本人实际窗口': '本人实际掌权时期',
    '本人窗口': '本人掌权时期', '本人责任期': '本人掌权时期',
    '交班': '任期结束', '本轮': '当前', '恢复原': '恢复此前',
    '未过健康档门': '尚不足以评为健康稳定',
    '宏观锚': '宏观证据', '总锚': '总体证据', '强锚': '有力证据',
    '主态锚': '主要阶段状态依据', '交班锚': '任期结束状态依据',
    '双锚': '两端状态依据', '三锚': '接手、主要阶段与任期结束的状态',
    '硬门': '必要条件', '不转DA': '不另外计为民力成本',
    '正式结算': '正式结果',
}
TOKEN = re.compile(r'[A-Za-z][A-Za-z0-9_]*(?:-[A-Za-z0-9_]+)*')


def translate(text: str, *, states: dict, losses: dict, costs: dict) -> str:
    for source, public in sorted(TRANSLATIONS.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace(source, public)
    for source, public in sorted(WORDING.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace(source, public)
    def token(match: re.Match[str]) -> str:
        value = match.group()
        state = re.fullmatch(r'(C[123])-([1-6])', value)
        if state:
            return TERMS[state[1]]+'“'+states[state[1]][int(state[2])]+'”'
        if value in losses:
            return losses[value]
        if value in costs:
            return costs[value]
        if value in TERMS:
            return TERMS[value]
        raise ValueError(f'公开文案存在未明确转述的术语 {value}：{text}')
    text = TOKEN.sub(token, text)
    if re.search(r'审计|重裁|重审|字段|版本史|\{\{', text):
        raise ValueError(f'公开文案需要按原句明确转述：{text}')
    return text
