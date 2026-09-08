"""Build the GPT scoring-contract package and the settlement review package.

Usage: python package_net_review.py [--package {all,contracts,settlements}]
The default output lives in .tmp/review-packages/. No scoring command is run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from textwrap import dedent
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PACKAGE_KINDS = ("contracts", "settlements")
PACKAGE_LABELS = {"contracts": "GPT前四项评分合同", "settlements": "结算摘要"}
PACKAGE_OUTPUT_NAMES = {
    "contracts": "净收益体系合同精简版.md",
    "settlements": "净收益体系-结算审查包.zip",
}
NET_BENEFIT_ITEMS = ("第一项", "第二项", "第三项", "第四项")
SUFFIXES = {".md", ".json", ".yml", ".yaml"}
FORBIDDEN = ("第五项", "人物画像", "profile", "tests", "test", "src", ".codex")
GOVERNING = "docs/项目总纲/皇帝综合评价体系评分标准.md"

SETTLEMENT_FIXED = (
    "docs/评分结算/00-皇帝统治成效综合评分榜.md",
)
CONFIG_DIRS = ("config/first-item", "config/second-item", "config/third-item")
PACKAGE_FIXED = {"settlements": SETTLEMENT_FIXED}
PACKAGE_ITEM_PARENTS = {"settlements": ("docs/评分结算",)}
PACKAGE_EXTRA_DIRS = {"settlements": ()}
PACKAGE_EXCLUSIONS = {
    "contracts": (
        "正式结算数据、当前排名和人物池状态",
        "机器发布、schema、验证器、双跑和哈希门禁",
        "全池覆盖、就绪状态和正式结算门禁",
        "人物画像专用文件",
        "导航、README、代码、测试、公共成果和史料全文",
    ),
    "settlements": (
        "config/下的adjudications、机器配置和其他输入数据",
        "文件名含审计、audit或adjudication的审计文件",
        "第五项、人物画像、代码、测试、公共成果和史料全文",
    ),
}

# The contract package is a deliberately flat, derived reading package.  These
# are its formal sources; the sources themselves are not copied into the ZIP.
# Keeping this whitelist explicit prevents a Markdown link from pulling in
# settlement views or the full historical reading corpus.
CHAT_CONTRACT_SOURCES = (
    GOVERNING,
    "docs/分项规则/第一项政权奠基与统一贡献及能力/00-规则与计分合同.md",
    "docs/分项规则/第一项政权奠基与统一贡献及能力/07-军事成本计分合同.md",
    "docs/分项规则/第二项治国净收益/制度行政/00-规则与计分合同.md",
    "docs/分项规则/第二项治国净收益/政权交接稳定/00-规则与结算合同.md",
    "docs/分项规则/第二项治国净收益/财政民生/00-规则与结算合同.md",
    "docs/分项规则/第二项治国净收益/财政民生/01-主动民力成本与军事分账合同.md",
    "docs/分项规则/第二项治国净收益/财政民生/02-主态低谷与净恢复机制.md",
    "docs/分项规则/第三项军事与边疆净收益/00-合并计分与军事扣减合同.md",
    "docs/分项规则/第三项军事与边疆净收益/国防安全/00-规则与结算合同.md",
    "docs/分项规则/第三项军事与边疆净收益/军事体系有效性/00-规则与计分合同.md",
    "docs/分项规则/第四项文明与国家整合收益/00-规则与计分合同.md",
    "docs/证据规则/军事成本评估合同.md",
    "docs/证据规则/军事成本高档与证据裁决合同.md",
    "docs/证据规则/军事对手战争机器O档合同.md",
)

# (archive name, ((source path, section-heading regexes to omit), ...))
CHAT_CONTRACT_RECIPES = (
    (
        "00-评分执行总合同.md",
        ((
            GOVERNING,
            (
                r"^## 9\.",
                r"^### 4\.4 ",
                r"^### 5\.4 ",
                r"^### 6\.4 ",
                r"^### 7\.4 ",
                r"^### 8\.4 ",
            ),
        ),),
    ),
    (
        "01-第一项评分卡.md",
        (
            (
                "docs/分项规则/第一项政权奠基与统一贡献及能力/00-规则与计分合同.md",
                (r"^## 8\. 执行与审计",),
            ),
            (
                "docs/分项规则/第一项政权奠基与统一贡献及能力/07-军事成本计分合同.md",
                (),
            ),
        ),
    ),
    (
        "02-第二项评分卡.md",
        (
            (
                "docs/分项规则/第二项治国净收益/制度行政/00-规则与计分合同.md",
                (r"^## 九、", r"^## 十、"),
            ),
            (
                "docs/分项规则/第二项治国净收益/政权交接稳定/00-规则与结算合同.md",
                (r"^### 三、正式卡与校验",),
            ),
            (
                "docs/分项规则/第二项治国净收益/财政民生/00-规则与结算合同.md",
                (),
            ),
            (
                "docs/分项规则/第二项治国净收益/财政民生/01-主动民力成本与军事分账合同.md",
                (),
            ),
            (
                "docs/分项规则/第二项治国净收益/财政民生/02-主态低谷与净恢复机制.md",
                (r"^## 4\. 裁决与验收",),
            ),
        ),
    ),
    (
        "03-第三项评分卡.md",
        (
            (
                "docs/分项规则/第三项军事与边疆净收益/00-合并计分与军事扣减合同.md",
                (),
            ),
            (
                "docs/分项规则/第三项军事与边疆净收益/国防安全/00-规则与结算合同.md",
                (r"^## 五、正式输出与校验",),
            ),
            (
                "docs/分项规则/第三项军事与边疆净收益/军事体系有效性/00-规则与计分合同.md",
                (r"^## 六、最小输出",),
            ),
        ),
    ),
    (
        "04-第四项评分卡.md",
        (
            (
                "docs/分项规则/第四项文明与国家整合收益/00-规则与计分合同.md",
                (r"^## 3\. 结算单位与固定扫描", r"^## 9\."),
            ),
        ),
    ),
    (
        "06-跨项与军事成本附录.md",
        (
            ("docs/证据规则/军事成本评估合同.md", ()),
            ("docs/证据规则/军事成本高档与证据裁决合同.md", ()),
            ("docs/证据规则/军事对手战争机器O档合同.md", ()),
        ),
    ),
)

# A few long source contracts contain a second layer of machine/output detail.
# These selectors retain only the normative scoring sections for the chat view;
# an empty entry means that the exclusion list above is sufficient.
CHAT_SECTION_INCLUDES: dict[tuple[str, str], tuple[str, ...]] = {
    (
        "02-第二项评分卡.md",
        "docs/分项规则/第二项治国净收益/制度行政/00-规则与计分合同.md",
    ): (
        r"^## 一、",
        r"^## 二、",
        r"^### 3\.2 ", r"^### 3\.3 ", r"^### 3\.4 ",
        r"^### 3\.5 ", r"^### 3\.7 ", r"^### 3\.9 ",
        r"^## 四、", r"^## 五、", r"^## 六、",
        r"^### 7\.1 ", r"^### 7\.2 ", r"^## 八、",
    ),
    (
        "03-第三项评分卡.md",
        "docs/分项规则/第三项军事与边疆净收益/国防安全/00-规则与结算合同.md",
    ): (r"^## 一、", r"^## 二、", r"^## 三、", r"^## 四、"),
    (
        "03-第三项评分卡.md",
        "docs/分项规则/第三项军事与边疆净收益/军事体系有效性/00-规则与计分合同.md",
    ): (r"^## 一、", r"^## 二、", r"^## 三、", r"^## 四、", r"^## 五、"),
    (
        "04-第四项评分卡.md",
        "docs/分项规则/第四项文明与国家整合收益/00-规则与计分合同.md",
    ): (r"^## 1\.", r"^## 2\.", r"^## 4\.", r"^## 5\.", r"^## 6\.", r"^## 7\.", r"^## 8\."),
    (
        "06-跨项与军事成本附录.md",
        "docs/证据规则/战争成本安全收益与战争回报档位.md",
    ): (r"^## 一、", r"^## 二、", r"^## 三、", r"^## 四、", r"^## 五、", r"^## 六、", r"^## 七、"),
}


def allowed(name: str) -> bool:
    path = Path(name)
    return path.suffix.lower() in SUFFIXES and not any(
        token in part.lower() for part in path.parts for token in FORBIDDEN
    )


def validate_package_kind(package: str) -> str:
    if package not in PACKAGE_KINDS:
        raise ValueError(f"未知包类型：{package}")
    return package


def current_item_directories(root: Path, parent: str) -> list[Path]:
    base = root / parent
    if not base.is_dir():
        raise FileNotFoundError(base)
    directories = []
    for item in NET_BENEFIT_ITEMS:
        matches = [p for p in base.iterdir() if p.is_dir() and p.name.startswith(item)]
        if len(matches) != 1:
            raise ValueError(f"{parent}/{item}: 需要唯一当前目录，实际{len(matches)}个")
        directories.append(matches[0])
    return directories


def settlement_allowed(path: Path) -> bool:
    lower_name = path.name.lower()
    return (
        path.is_file()
        and path.suffix.lower() in {".md", ".json"}
        and "审计" not in path.name
        and "audit" not in lower_name
        and "adjudicat" not in lower_name
        and allowed(path.as_posix())
    )


def collect(root: Path, package: str) -> list[Path]:
    """Whitelist either the contract or settlement roots; never chase arbitrary links."""
    package = validate_package_kind(package)
    root = root.resolve()
    if package == "contracts":
        selected = {root / name for name in CHAT_CONTRACT_SOURCES}
        for path in selected:
            if not path.is_file():
                raise FileNotFoundError(path)
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise ValueError(f"不接受符号链接或仓库外文件：{path}")
            if path.suffix.lower() != ".md":
                raise ValueError(f"聊天合同源必须是Markdown：{path}")
        return sorted(selected, key=lambda p: p.relative_to(root).as_posix())

    selected = {root / name for name in PACKAGE_FIXED[package]}
    directories = [root / name for name in PACKAGE_EXTRA_DIRS[package]]
    for parent in PACKAGE_ITEM_PARENTS[package]:
        directories.extend(current_item_directories(root, parent))
    for directory in directories:
        if not directory.is_dir():
            raise FileNotFoundError(directory)
        selected.update(
            p
            for p in directory.rglob("*")
            if settlement_allowed(p)
        )
    for path in selected:
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError(f"不接受符号链接或仓库外文件：{path}")
        if not allowed(path.relative_to(root).as_posix()):
            raise ValueError(f"白名单中出现禁入文件：{path}")
    return sorted(selected, key=lambda p: p.relative_to(root).as_posix())


def _read_utf8(root: Path, relative: str) -> str:
    path = root / relative
    return path.read_text(encoding="utf-8-sig")


def _remove_markdown_sections(text: str, patterns: tuple[str, ...]) -> str:
    """Remove a heading and its descendants without changing other source text."""
    if not patterns:
        return text
    compiled = tuple(re.compile(pattern) for pattern in patterns)
    output: list[str] = []
    skip_level: int | None = None
    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            level = len(match.group(1))
            title = match.group(2)
            if skip_level is not None and level <= skip_level:
                skip_level = None
            if skip_level is None and any(pattern.search(line) or pattern.search(title)
                                          for pattern in compiled):
                skip_level = level
                continue
        if skip_level is None:
            output.append(line)
    return "\n".join(output).rstrip() + "\n"


def _select_markdown_sections(text: str, patterns: tuple[str, ...]) -> str:
    """Keep the preamble and only the selected heading subtrees."""
    if not patterns:
        return text
    compiled = tuple(re.compile(pattern) for pattern in patterns)
    lines = text.splitlines()
    first_heading = next(
        (index for index, line in enumerate(lines)
         if re.match(r"^#{1,6}\s+", line)),
        len(lines),
    )
    output = lines[:first_heading]
    active_level: int | None = None
    for line in lines[first_heading:]:
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            level = len(match.group(1))
            if active_level is not None and level <= active_level:
                active_level = None
            if any(pattern.search(line) or pattern.search(match.group(2))
                   for pattern in compiled):
                active_level = level
        if active_level is not None:
            output.append(line)
    return "\n".join(output).rstrip() + "\n"


def _strip_internal_links(text: str) -> str:
    """Flatten local Markdown links for the package's single-document layout."""
    pattern = re.compile(r"!?\[([^\]]+)\]\(([^)\n]+)\)")

    def replace(match: re.Match[str]) -> str:
        target = match.group(2).strip().lower()
        if target.startswith(("http://", "https://", "mailto:")):
            return match.group(0)
        return match.group(1)

    return pattern.sub(replace, text)


def _strip_chat_noise(text: str) -> str:
    """Drop operational path/output lines while retaining scoring semantics."""
    kept: list[str] = []
    for line in text.splitlines():
        if any(
            marker in line
            for marker in (
                "机器计分唯一读取",
                "正式机器入口",
                "当前正式输入与运行边界",
                "数据库写入",
                "canonical_status=FORMAL_CURRENT",
            )
        ):
            continue
        if re.search(r"^\s*入口：.*(?:正式裁决|阅读页|映射)", line):
            continue
        if "机器锚点" in line and "正式" in line:
            continue
        kept.append(line)
    return "\n".join(kept).rstrip() + "\n"


def _compact_governing_source(text: str) -> str:
    text = _remove_markdown_sections(
        text,
        (
            r"^## 9\.",
            r"^### 4\.4 ",
            r"^### 5\.4 ",
            r"^### 6\.4 ",
            r"^### 7\.4 ",
            r"^### 8\.4 ",
        ),
    )
    # The item formula is useful; the sensitivity matrix, ranking view and
    # result-file link are settlement/presentation concerns for this package.
    text = re.sub(r"\n基准排序唯一\。.*?(?=\n## 5\.)", "\n", text, flags=re.DOTALL)
    text = re.sub(r"^\s*展示共同项.*$", "", text, flags=re.MULTILINE)
    text = re.sub(
        r"^候选含皇帝.*$",
        "本包只处理用户指定人物，不要求全池覆盖或读取当前结算状态。",
        text,
        flags=re.MULTILINE,
    )
    return text


def _compact_source(root: Path, archive_name: str, relative: str,
                    exclusions: tuple[str, ...]) -> str:
    text = _read_utf8(root, relative)
    if relative == GOVERNING:
        text = _compact_governing_source(text)
    else:
        text = _remove_markdown_sections(text, exclusions)
    includes = CHAT_SECTION_INCLUDES.get((archive_name, relative), ())
    if includes:
        text = _select_markdown_sections(text, includes)
    return _strip_chat_noise(_strip_internal_links(text))


def _compact_military_appendix() -> bytes:
    text = """# 06-跨项与军事成本附录

> 仅在人物材料出现军事投入、战争损害、对手压力或主动民力负担时读取；这是聊天评分摘要，不含机器结算门禁。

## 一、军事成本归责

主要估计本人掌权阶段已经发生的本方军事投入和损失。军人损失、征兵、驻屯、调军、军用劳役、运输、军马、舰船、军械、军粮、工程和灾后补充都可纳入；敌军、盟军、平民、失地、亡国、财政恶化不直接当作军事成本。

第一项消费创业、复国、统一和取得政权父链的成果与成本；第三项消费本人正式主政窗口内、未被第一项消费的军事链。第二项DA只消费独立且未被C1—C4或第三项成本吸收的主动民力负担。同一后果不得跨项重复扣分。

## 二、军事成本档位 `C0—C7`及普通扣分

数值均为扣分；第一项与第三项不共用映射。第三项普通成本与ML不相加，取绝对值较大者。

| 档位 | 最小含义 | 第一项扣分 L/M/H/HIGHEST | 第三项普通扣分 L/M/H/HIGHEST |
|---:|---|---:|---:|
| C0 | 通常没有明显军事投入或毁损；资料少不自动等于C0。 | 0/0/0/— | 0/0/0/— |
| C1 | 局部、短期、常规投入，无显著军资或兵团毁损。 | 0.5/1/1.5/— | 0/0.4/0.8/— |
| C2 | 有限方向投入，或轻度、易恢复的人员、军资、编组损害。 | 2/2.5/3/— | 1.2/1.6/2.0/— |
| C3 | 明显方向级投入或可见累计负担，但未达显著兵团毁损或国家级长期承载。 | 4/5/6/— | 2.8/4.0/5.2/— |
| C4 | 大规模/持续区域或国家行动，或有实质兵团毁损、显著战争准备和后勤工程。 | 8.8/10/12.5/— | 7.5/10/12.5/— |
| C5 | 主要野战力量、重要兵团或军事资产严重毁损，或长期反复高强度战争形成国家尺度负担。 | 18/22.5/27/— | 16.2/20.4/24.6/— |
| C6 | 极端人员损失，或国家核心军事能力实际中断/必须重大替代。 | 35/42/49/— | 30.1/36.4/44.1/— |
| C7 | 先有独立C6，随后发生再次C6并持续非常补充，或至少两个相互关联的国家军事功能广泛失效并持续耗竭。 | 60/68/76/80 | 52/60.8/70.4/80 |

多个低档事件不要机械相加。C6大致对应十万人级人员损失或核心军力失能；普通受伤、被俘、失踪、溃散、倒戈不直接当死亡。核心能力路径看是否真的需要重大替代；C7不要把首灾和后灾重复计算。

档内位置按人员/资产、核心角色、动员后勤、持续时间、战区和重建强度粗分LOW/MID/HIGH；人数、败战数和任期长度不单独升位。

## 三、有效对手战争机器 `O1—O6`

| 档位 | 当前竞争窗口中的最小含义 |
|---:|---|
| O1 | 零散地方力量、残余据点或短时低压武装。 |
| O2 | 能局部大会战或稳定袭扰，但缺稳定国家机器。 |
| O3 | 有统一指挥并能持续压迫一个主要方向。 |
| O4 | 有稳定区域、行政征补、财政兵员和持续独立作战能力。 |
| O5 | 与评价主体大体同级，具成熟中枢、跨区主力和真实战略竞争机会。 |
| O6 | 在当前窗口明显占战略优势，持续危及主体生存、核心根据地或主要目标。 |

主要看本人实际竞争窗口，不看对手历史巅峰、后来发展、母体国号、潜力或本方弱小。偏师、残部和短期联盟不自动继承母体高档；同一持续压力链可合并。O只用于描述对手压力，不单独增加胜利、成果或成本收益。

## 四、ML：军事净毁损扣分

ML只作军事净毁损的粗略负尾估计：没有明显的本人重大军事自损时取ML0；不要求GPT拆战略链、判EN等级或填写成本档案。

| ML档 | 扣分 | 粗略含义 |
|---:|---:|---|
| ML0 | 0 | 普通失败、一般战争损失或本人责任不明显。 |
| ML1 | -20 | 单一主要方向重大净损害。 |
| ML2 | -40 | 多次失败/再动员造成跨阶段严重损害。 |
| ML3 | -60 | 全国或多个主要方向的军事体系严重崩坏。 |
| ML4 | -80 | 本人反复推动全国级军事自损，造成近乎系统性崩溃。 |

全任期只裁一个ML，不逐战相加；第三项使用`max(普通成本扣分, |ML|)`，不把两者相加。

## 五、DA：主动民力成本

DA是第二项C4的“破坏性制造/放大”扣分，只计本人可选择行为留下的、尚未被其他子项消费的家庭/生产/民间财产/非军事公共用途挤占或平民伤害。

先排除必要防御/平乱、普通维护、正常陵寝、灾后修复和最低重建基线，再剔除C1—C3、L或C4恶化已经消费的后果。军人伤亡、军资军粮、军运和再动员归第一/第三项，不再折入DA；责任窗口内整体只定一档、扣一次。

DA1可由超必要动员的大致民力负担推断；DA2以上最好有较明确的民力范围、强度或持续性判断。军事规模、次数、距离、金额或战损本身不要直接推出高DA。

| DA档 | 扣分 | 精华门槛 |
|---:|---:|---|
| DA0 | 0 | 无可归责额外成本，或只有必要/普通基线。 |
| DA1 | 4.5 | 剩余负担有限，或仅达到主动动员的保守推断下限。 |
| DA2 | 9.0 | 国家/主要区域显著额外负担，已有实质资源占用或民生传导。 |
| DA3 | 13.5 | 极重资源/财政占用，或严重生产、家庭损害；一次灾难性选择也可成立。 |
| DA4 | 18.0 | 严重全国性或多通道成本，明显挤压正常财政民生。 |
| DA5 | 22.5 | 接近全国总动员或长期系统汲取，正常财政民生显著受破坏。 |
| DA6 | 27.0 | 罕见灾难级，主动成本体系直接驱动政权级系统崩坏或近崩坏。 |

第二项C4使用：`C4=恢复-恶化-DA`，范围`[-40,27]`；DA与普通军事成本、ML不重复。

## 六、快速用法

只需根据人物整体历史表现给出成本档、ML/DA档和一句理由；不要求书卷引文、史源编号、精确人数或逐条成本清单。
"""
    return text.encode("utf-8")


def _manual_chat_card(archive_name: str) -> bytes | None:
    """Return the intentionally terse scoring cards used by the chat package."""
    cards = {
        "00-评分执行总合同.md": """
# 前四项人物评分执行总合同（聊天试用版）

> 只评用户指定人物，不读取正式结算数据，不要求全池覆盖。本文用于历史知识快速估计，不要求逐条史料引文、史料回源或正式证据审计。

## 一、前四项结构

| 项目 | 评价核心 | 范围/上限 |
|---|---|---:|
| 第一项 | 建国、复国、统一主链及创业能力 | 0—240，条件附加 |
| 第二项 | 正式统治期治理、民生、经济、社会安全与交接 | -27.5—387 |
| 第三项 | 战略安全、边疆控制、军事体系和军事成本 | -80—250 |
| 第四项 | 共同体、教育人才、知识文化的本人净变化 | -67.5—+67.5 |

## 二、共同规则

1. 按大致实际掌权阶段和整体历史表现估计；称帝、名义在位、后世寿命不能简单代替本人表现。
2. 不要求逐事件重建证据链；只需概括本人行为、主要结果和整体影响。
3. 名望、政策名称、国家结果、材料数量和“未发现负面”都不能直接换分。
4. 同一事实可因不同独立命题被引用，但同一结果、同一损害、同一战争成本不得重复消费。
5. 第一项消费创业/统一/取得政权整链；第二项消费治理与民生后果；第三项消费主政期安全、控制和军事成本；第四项消费文明整合结果。

## 三、综合公式（需要总分时才使用）

```text
S1 = max(0, A+B1+B2+C-第一项军事成本)
S2 = 治理手段165 + 治理结果(-27.5—202) + 交接质量20
S3 = A120+B80+C50-max(普通军事成本, |ML|)
F  = 0.15 × 637 × (S1/240)^1.25；第一项不适用时F=0
CIV4 = 第四项有符号调整
T = S2 + S3 + F + CIV4
```

聊天评分输出：逐项给“适用性—子项档/分—一两句理由—大致不确定性”。
""",
        "01-第一项评分卡.md": """
# 第一项：政权奠基与统一贡献及能力

适用于建国、复国、共同奠基和未闭合统一链；单纯继承、成熟扩张或王朝内部夺权不适用。窗口从本人实际参与贡献起算。

| 子项 | 满分 | 判分核心 |
|---|---:|---|
| A 统一主链客观贡献 | 120 | 最终稳定控制成果 |
| B1 创业难度与效率 | 50 | 起点、对手、速度 |
| B2 组织与政治整合 | 30 | 并行、专业、异质整合 |
| C 本人军事解题 | 40 | 本人战略、指挥、纠偏 |

## A（120）

只计主链最终稳定控制，称帝/受禅/形式建国不产生A。共同创业先合成A池再分账：

```text
U = 新增稳定控制 + 0.5×恢复稳定控制
A池 = 120×(min(1000,U)/1000)^0.65
```

基线扣除入链前已稳定控制；终点看退出前仍保留的大致控制，不取短时峰值。下属成果不自动转本人C。

## B1（50）

`B1=起点15+对手15+效率20`。

| 起点R档 | R0 | R1 | R2 | R3 | R4 | R5 | R6 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 分值 | 15 | 13 | 11 | 8 | 5 | 2 | 0 |

O档按实际竞争窗口：O6/O5/O4/O3/O2/O1分别取10/8/6/4/2/1分，最强两个独立对手第一强全值、第二强50%。

完成效率以最早达到约90%有效成果、无O5/O6可争主链、剩余仅尾项的`T_core`计时：

```text
期望年 = 4+8×sqrt(效率阶段有效控制/1000)
速度比 = 实际阶段年数/期望年
```

| 速度比 | ≤0.75 | ≤1 | ≤1.25 | ≤1.5 | ≤2 | ≤2.5 | ≤3 | ≤4 | >4 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 效率分 | 20 | 18 | 16 | 14 | 11 | 8 | 5 | 2 | 0 |

## B2（30）

并行执行、专业覆盖、异质整合各0/2/4/6/8/10分（L0—L5）。

- L0：本人逐项处理/集团不能共同执行；L1：有助手但不能独立闭合；L2：一个稳定责任中心/吸收一类力量；
- L3：两个责任中心或多类力量能共同工作；L4：至少三个责任中心、多异质集团稳定承担核心任务；L5：多中心体系化并长期独立兑现高难任务。

按组织实际运作表现估计，不按名将、官位、人数或国家成果机械计分；下属成果不复制为本人C。

## C（40）

| 档 | C0 | C1 | C2 | C3 | C4 | C5 |
|---|---:|---:|---:|---:|---:|---:|
| 区间 | 0 | 4—10 | 12—18 | 20—26 | 28—34 | 36—40 |

C1基础、C2重要、C3优秀、C4顶级、C5历史级；档内LOW/MID/HIGH分别按表定值。按本人角色、主要决定、难度、结果和整体成败快速估计；重大失败、同错复发或明显未纠偏下调。

## 边界

第一项成果、成本和创业整链退出第三项A/B；成熟扩张、防务和独立后续战争归第三项；C与第一项成果分开估计。成本按附录判C0—C7后扣除。
""",
        "02-第二项评分卡.md": """
# 第二项：治国净收益

`S2=治理手段165+治理结果(-27.5—202)+交接质量20`。按制度运行、治理结果和交班表现快速估计；政策名称、名望和结果规模不能单独代替实际表现。

## 一、治理手段（165）

分析顺序可参考“举措—运行—结果—纠正”，不要求逐事件重建；A/B1/B2/D1方向指数不直接相加：

```text
method = round1(0.8×[max(A,B1)+0.5×min(A,B1)]) + round1(45/80×B2)
```

同档基准映射（A、B1、B2均处于同一G档；档内位置不同则按上式重算）：

| G档 | A/B1指数区间 | B2指数区间 | 治理手段165分区间 |
|---:|---:|---:|---:|
| G0 | 0—19.9 | 0—15.9 | 0—32.8 |
| G1 | 20—39.9 | 16—31.9 | 33.0—65.8 |
| G2 | 40—54.9 | 32—43.9 | 66.0—90.6 |
| G3 | 55—69.9 | 44—55.9 | 90.8—115.3 |
| G4 | 70—84.9 | 56—67.9 | 115.5—140.1 |
| G5 | 85—100 | 68—80 | 140.3—165.0 |

D1不进入165分；D1与D3另合成交接质量20分。

### A制度建设、B1行政执行、B2反馈纠错

| 子项 | 低档到高档的精华门槛 |
|---|---|
| A | G0无运行/纸面；G1未完成尝试；G2局部或次级真实接口；G3净建设≥2或一条M3/两条独立M2；G4有过R3耐久门的核心S；G5净值≥6且至少3条独立S跨2领域，或2条S++重定核心接口。 |
| B1 | G0多核心行政广域终局失灵；G1主要阶段/广域失灵主导；G2有真实交付但覆盖/替补不足；G3主要阶段可用且有core M3或多条独立机制链；G4 core M3+独立第二验证；G5再有独立第三系统链、跨阶段保持或高压下不间断/恢复。 |
| B2 | G0反馈/监督被系统封闭；G1形式渠道或拒谏报复主导；G2一条反馈—处置—纠偏链；G3主要阶段反馈、监督和纠错实际运行；G4至少两种独立渠道反复约束高官/最高权力且有外朝/基层上达；G5达到G4并具多渠道、广覆盖、罕见重复性。 |

A看核心制度是否真正改变并持续使用；普通维护/换名不抬档。B1不以官名、人数、盛世或单一结果计档；B2单次纳谏通常不直接推到高档。

### D1继任行政连续性

主要看实际失去最高治理权后通常三年内行政机器是否继续运行。

| H档 | 核心边界 |
|---:|---|
| H0 | 主要官署/命令链和基本行政停止。 |
| H1 | 只残存零散旧资产，未成持续核心链。 |
| H2 | 需紧急接管、显著换血或结构重建后恢复。 |
| H3 | 可识别旧人员/官署/命令链实际继续。 |
| H4 | 两个独立核心领域，或一条覆盖中枢—执行—结果的广域连续链。 |
| H5 | 满足H4，且至少三个领域高压持续交付，或定向留下的行政资产长期验证有价值。 |

### D3政权交接

| 档 | 交接结果 |
|---:|---|
| 0 | 无有效继承/中央延续完全中断。 |
| 1 | 两个以上现实中枢争位、继承战争或大范围分裂。 |
| 2 | 暴力接管/弑废/强制改立，但中央较快接续。 |
| 3 | 承接完成，但一年内出现源于交接结构的现实威胁或权力悬置。 |
| 4 | 安全承接，一年内无现实继承威胁。 |
| 5 | 安排明确、关键力量接受，风险检验后仍平稳接续。 |

交接质量：`raw=2×(D1_level+D3_level)`，按较弱一侧低侧上限0/4/8/12/16/20封顶。

## 二、治理结果（C1—C4）

三锚只作粗略参照：`S0`接手、`S_main`任内主要状态、`S_end`交班；政策不代结果，战争/安全收益归第三项。

治理结果的三条绝对状态轴是：`C1`民生福祉（80）、`C2`经济活力与财政健康（35）、`C3`社会安全（60）；`C4`不是第四条绝对状态轴，而是动态恢复/恶化/DA轴。C1内部再看三类结果：家庭温饱与物质余量、税赋徭役落到家庭的净承受、家庭形成与人口再生产。

| 子项 | 低→高档位说明 | 固定分/公式 |
|---|---|---|
| C1民生80 | C1-1家庭生计广泛崩溃；-2长期困顿；-3基本维持；-4普遍温饱；-5广域长期富庶；-6三轴罕见极盛且有家庭余量强锚。 | 5.7/17.1/32.0/54.9/74.3/80 |
| C2经济财政35 | -1系统崩解；-2至少一柱长期脆弱；-3两柱基本运行；-4民间与财政均健康；-5两柱广域强健；-6生产、市场、税基、储备四面长期顶峰。 | 1.8/7.0/14.9/23.6/29.8/35 |
| C3社会安全60 | -1广域暴力/秩序崩解；-2至少两面持续脆弱；-3主要区可运行；-4安全、秩序、司法总体稳定；-5多轴长期高位；-6多阶段多区域罕见顶峰。 | 5/16/28/40/52/60 |

### C4恢复、恶化与DA

只估计动态恢复、恶化和主动成本，不重复C1—C3绝对状态：

```text
恢复 = round_half_up_1(min(27,(0.5×C1恢复+0.2×C2恢复+0.3×C3恢复)×10))
恶化 = min(1, (0.5×C1下降+0.2×C2下降+0.3×C3下降)/2)×13
C4 = 恢复 - 恶化 - 破坏性DA，范围[-40,27]
```

本人明显造成的低谷回升主要算止损；外因、本人放大和主动动员按整体历史印象粗略区分。DA只计未被其他子项消费的主动民力负担；DA0—DA6按0/4.5/9/13.5/18/22.5/27扣入C4。
""",
        "03-第三项评分卡.md": """
# 第三项：军事与边疆净收益

`S3=A120+B80+C50-max(普通成本,|ML|)`。第一项已消费整链退出A/B；本人主政窗口内独立军事链才进入本项。

## 一、A战略安全（A1/A2各60）

| 档 | A1战略威胁 | A2战略边界 |
|---:|---|---|
| 0 | 核心区/国家军事存续现实受威胁 | 核心区长期直接暴露 |
| 1 | 主要威胁具国家级危机能力 | 主要防线/缓冲破裂 |
| 2 | 主要方向反复被动但未即时存亡 | 有孤立关隘/边镇，未成体系 |
| 3 | 攻守制衡 | 一个主要方向形成可运行但有缺口的体系 |
| 4 | 威胁总体受控、保留未决方向 | 主要门户、纵深、补给总体协同 |
| 5 | 存亡级威胁被结构性压低 | 全国防御纵深成形、无显著结构缺口 |

先看接班与交班安全状态，再按本人整体改善、保全和恶化表现估计；不以面积、胜利、和平或一次反击单独代替安全体系。保全压力可参考O4/O5/O6对应4/8/12分，重大逆转和明显恶化下调。

```text
每轴轨迹T=10×终点档+14×可归责档差+专项信用-负向调整
每轴分=0.6×T；A=A1+A2
```

## 二、B控制（B1/B2/B4）

第三项B只作定性估计：B1按本人窗口的边疆/控制空间净新增规模和交班保留程度粗分0—5档；本聊天版不提供空间当量、锚点、覆盖率或数值映射，由GPT按整体历史常识估计。B2看战略价值，B4看交班成熟度；B1约占B基础权重55%、B2约45%，B4只作成熟度修正，不计算精确B80。

| B2战略价值 | B4交班成熟度 |
|---|---|
| 0无实际价值；1单点有限；2局部交通/防御/资源作用；3重要区域门户/走廊/缓冲；4关键战略方向；5国家存续/核心安全决定性价值。 | 0丧失/名义；1战时占领随时失控；2结构未完备且依赖临时资源；3常态但有脆弱包/缺口；4主要成果均闭合可常态运行；5全部主要成果均闭合并可正常移交、无显著缺口。 |

主要看本人新建、收复或重大保全的控制成果；纯继承不抬B2/B4。本人造成且未恢复的主要方向退控，通常把B4限制在3档以内。

## 三、C军事体系（50）

| C档 | C1实战兑现 | C2持续作战 | C3体系可靠性 |
|---:|---|---|---|
| 0 | 核心任务整体失能 | 动员/补充/后勤崩溃 | 国家级组织全面崩溃未恢复 |
| 1 | 普通任务反复失败 | 只能短期行动 | 中央组织长期严重失灵 |
| 2 | 胜负混杂偏弱 | 有限作战、保障常断 | 依赖单将/临时拼凑 |
| 3 | 普通中等任务总体可兑现 | 可支撑普通战争 | 通常有效但复制有限 |
| 4 | 高难任务多数兑现 | 多路/长期战争稳定 | 多将多方向可运行但有缺口 |
| 5 | 多个O4—O6体系下长期顶级 | 多方向长期顶级保障 | 跨将领战场历史顶级且至少两名高等级武将独立兑现 |

`C总体=min(C1,C2,C3)`；C2/C3只能压低C1，不能抬高。C档按整体军事体系表现、持续作战能力和跨将领可靠性快速估计；C5需要明显的多方向高难表现和重大胜绩，不做逐任务证据门禁。

军事体系C档到50分的映射（档内位置仍按父周期结果质量和LOW/MID/HIGH确定）：

| C档 | 得分率 | C项分值范围 |
|---:|---:|---:|
| C0 | 0%—29% | 0—14.5 |
| C1 | 30%—44% | 15—22 |
| C2 | 45%—59% | 22.5—29.5 |
| C3 | 60%—74% | 30—37 |
| C4 | 75%—89% | 37.5—44.5 |
| C5 | 90%—100% | 45—50 |

## 四、成本提示

成本、C6/C7、O档和DA只在人物明显涉及军事成本时参考`06-跨项与军事成本附录`；第三项成本不与民生、名望或战争胜负重复加减。
""",
        "04-第四项评分卡.md": """
# 第四项：文明与国家整合收益

三轴均看相对继承基线的本人影响；不比学校、著作、人数裸数量，不设时代系数。后世只作耐久参考，国家机器和军事控制不在本项重复计。

| 轴 | 范围 | 判分核心 |
|---|---:|---|
| A共同体整合 | -22.5—+22.5 | 群体参与、认同、接纳、排斥和强制同化的实际社会后果 |
| B教育人才 | -22.5—+22.5 | 稳定教育供给、学习机会、跨身份/地域流动和文明再生产 |
| C知识文化 | -22.5—+22.5 | 知识生产、保存、可访问、传播、采用及表达生态 |

## 聊天版粗档

第四项只给三轴方向和粗略档位，不拆影响包、不做R0—R4、正负包合成、硬负向门或LOW/MID/HIGH带位：

| 粗档 | 快速含义 |
|---:|---|
| 0 | 没有明显本人文明/整合变化，或正负大致抵消。 |
| 1 | 局部、短期、有限变化。 |
| 2 | 清晰但有限的扩张、修复、收缩或破坏。 |
| 3 | 主要领域出现稳定、显著变化。 |
| 4 | 跨多个场景形成明显新范式，或出现系统性破坏。 |

每轴只需给`正向/中性/负向 + 粗档0—4 + 一句理由`；总分按方向和大致幅度估计，不追求精确带位。
""",
    }
    text = cards.get(archive_name)
    return None if text is None else dedent(text).strip().encode("utf-8") + b"\n"


def _indent_headings(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^(#{1,5})(\s+.*)$", line)
        if match:
            line = "#" + match.group(1) + match.group(2)
        lines.append(line)
    return "\n".join(lines).rstrip() + "\n"


def _compose_chat_document(root: Path, archive_name: str,
                           sources: tuple[tuple[str, tuple[str, ...]], ...]) -> bytes:
    manual = _manual_chat_card(archive_name)
    if manual is not None:
        return manual
    if archive_name == "06-跨项与军事成本附录.md":
        return _compact_military_appendix()
    title = Path(archive_name).stem
    parts = [
        f"# {title}",
        "",
        "> GPT聊天评分派生阅读版：面向用户指定人物的前四项综合评分试跑。",
        "> 本文件不替代正式合同，不读取正式结算数据；缺证必须保留为未决或有界观察。",
        "",
    ]
    for relative, exclusions in sources:
        parts.extend((f"## 来源规则：{Path(relative).stem}", ""))
        parts.append(_indent_headings(_compact_source(root, archive_name, relative, exclusions)))
    return ("\n".join(parts).rstrip() + "\n").encode("utf-8")


def _chat_review_note() -> bytes:
    text = (
        "# 净收益体系合同精简版（GPT聊天阅读版）\n\n"
        "本包用于对用户指定的一部分人物进行前四项综合评分的快速历史估计，不要求全池覆盖，"
        "不读取正式结算JSON、当前排名、人物池就绪状态或画像数据。\n\n"
        "## 读取顺序\n\n"
        "1. 先读 `00-评分执行总合同.md`，掌握总原则、分值结构、本人窗口和跨项去重。\n"
        "2. 再读 `01`—`04`，分别完成第一至第四项。\n"
        "3. 只有遇到军事成本、战争损害、对手O档或DA分账时，才查 `06-跨项与军事成本附录.md`。\n\n"
        "## 输出要求\n\n"
        "每个人逐项输出：适用性、档位或分数、简短历史理由和大致不确定性。"
        "不要求引文、史源编号或逐条举证；不确定时给近似档位或区间，不因缺少引文自动记零。\n\n"
        "## 使用边界\n\n"
        "本版只用于聊天中的快速比较，不运行结算、不修改正式结果；不要把它当作严格史料裁决。\n"
    )
    return text.encode("utf-8")


def _prepare_chat_contract_package(root: Path) -> tuple[dict[str, bytes], dict]:
    entries: dict[str, bytes] = {}
    generated_inventory = []
    for archive_name, sources in CHAT_CONTRACT_RECIPES:
        content = _compose_chat_document(root, archive_name, sources)
        entries[archive_name] = content
        generated_inventory.append(
            {
                "path": archive_name,
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "source_paths": [relative for relative, _ in sources],
                "transformation": "CHAT_SCORING_MANUAL_CORE",
            }
        )

    source_inventory = []
    for relative in CHAT_CONTRACT_SOURCES:
        raw = (root / relative).read_bytes()
        raw.decode("utf-8-sig")
        source_inventory.append(
            {
                "path": relative,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )

    manifest = {
        "format": "chat-scoring-contract-package-v1",
        "package": "contracts",
        "package_label": PACKAGE_LABELS["contracts"],
        "source": "CURRENT_WORKING_TREE_INCLUDING_UNCOMMITTED_CHANGES",
        "mode": "PARTIAL_RULER_FOUR_ITEM_SCORING",
        "file_count": len(generated_inventory),
        "source_file_count": len(source_inventory),
        "uncompressed_source_bytes": sum(item["bytes"] for item in source_inventory),
        "uncompressed_archive_content_bytes": sum(item["bytes"] for item in generated_inventory),
        "source_files": source_inventory,
        "files": generated_inventory,
        "exclusions": list(PACKAGE_EXCLUSIONS["contracts"]),
    }
    entries["文件清单.json"] = encode_json(manifest)
    entries["00-审查说明.md"] = _chat_review_note()
    return entries, manifest


def _compose_chat_contract_document(entries: dict[str, bytes]) -> bytes:
    sections = [entries["00-审查说明.md"].decode("utf-8")]
    for archive_name, _ in CHAT_CONTRACT_RECIPES:
        sections.append(entries[archive_name].decode("utf-8"))
    return ("\n\n---\n\n".join(section.rstrip() for section in sections) + "\n").encode("utf-8")


def encode_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def review_note(package: str) -> bytes:
    if package == "contracts":
        return _chat_review_note()
    else:
        text = (
            "# 净收益体系结算摘要包（聊天版）\n\n"
            "本包保留`docs/评分结算/`下按朝代/分项组织的正式JSON分片和结算Markdown；排除画像、配置输入及审计文件。\n\n"
            "## 使用边界\n\n"
            "被排除的adjudications和审计文件仍留在正式仓库，不代表正式结果不存在。"
            "本包不运行重建、不修改分数；正式JSON分片和Markdown阅读页保留。\n"
        )
    return text.encode("utf-8")


def prepare(root: Path, package: str) -> tuple[dict[str, bytes], dict]:
    package = validate_package_kind(package)
    root = root.resolve()
    if package == "contracts":
        return _prepare_chat_contract_package(root)

    entries: dict[str, bytes] = {}
    inventory = []
    for path in collect(root, package):
        name = path.relative_to(root).as_posix()
        original = path.read_bytes()
        original.decode("utf-8-sig")  # Reject unreadable text before opening the output.
        content = original
        entries[name] = content
        inventory.append(
            {
                "path": name,
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "source_sha256": hashlib.sha256(original).hexdigest(),
                "transformation": "VERBATIM",
            }
        )
    # Keep every router and its shards usable without the repository's Python loader.
    routers = 0
    for name, content in entries.items():
        if not name.endswith(".json"):
            continue
        data = json.loads(content)
        if not isinstance(data, dict) or data.get("schema_version") != "formal-json-polity-router-v1":
            continue
        routers += 1
        for shard in data["routes"]:
            target = (Path(name).parent / shard["path"]).as_posix()
            if target not in entries:
                raise ValueError(f"路由分片未入包：{name} -> {target}")
    manifest = {
        "format": "net-benefit-settlement-summary-package-v1",
        "package": package,
        "package_label": PACKAGE_LABELS[package],
        "source": "CURRENT_WORKING_TREE_INCLUDING_UNCOMMITTED_CHANGES",
        "scope": list(NET_BENEFIT_ITEMS),
        "file_count": len(inventory),
        "uncompressed_source_bytes": sum(item["bytes"] for item in inventory),
        "router_count": routers,
        "exclusions": list(PACKAGE_EXCLUSIONS[package]),
        "files": inventory,
    }
    entries["文件清单.json"] = encode_json(manifest)
    entries["00-审查说明.md"] = review_note(package)
    return entries, manifest


def build(root: Path, output: Path, package: str) -> dict:
    package = validate_package_kind(package)
    entries, manifest = prepare(root, package)
    output = output.resolve()
    if package == "contracts":
        if output.suffix.lower() != ".md":
            raise ValueError("合同精简版输出路径必须以.md结尾")
        content = _compose_chat_contract_document(entries)
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".md", delete=False) as tmp:
            tmp.write(content)
            temporary = Path(tmp.name)
        try:
            temporary.replace(output)
        finally:
            temporary.unlink(missing_ok=True)
        if output.read_bytes() != content:
            raise ValueError("合同精简版写入校验失败")
        return {
            "package": package,
            "package_label": PACKAGE_LABELS[package],
            "output": str(output),
            "source_files": manifest["source_file_count"],
            "document_sections": len(CHAT_CONTRACT_RECIPES),
            "document_bytes": len(content),
            "uncompressed_source_bytes": manifest["uncompressed_source_bytes"],
        }

    if output.suffix.lower() != ".zip":
        raise ValueError("输出路径必须以.zip结尾")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Fixed metadata/order makes identical snapshots byte-for-byte reproducible.
    with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".zip", delete=False) as tmp:
        temporary = Path(tmp.name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, content in sorted(entries.items()):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, content, compresslevel=9)
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None or set(archive.namelist()) != set(entries):
                raise ValueError("ZIP完整性校验失败")
            for name, content in entries.items():
                if not allowed(name) or archive.read(name) != content:
                    raise ValueError(f"入包内容或范围校验失败：{name}")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "package": package,
        "package_label": PACKAGE_LABELS[package],
        "output": str(output),
        "source_files": manifest.get("source_file_count", manifest["file_count"]),
        "archive_entries": len(entries),
        "zip_bytes": output.stat().st_size,
        "uncompressed_source_bytes": manifest.get(
            "uncompressed_source_bytes", manifest.get("uncompressed_archive_content_bytes", 0)
        ),
        "router_count": manifest.get("router_count", 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="生成GPT前四项合同精简文档和结算包（合同文档不含结算数据）"
    )
    parser.add_argument(
        "--package",
        choices=("all",) + PACKAGE_KINDS,
        default="all",
        help="生成的包；默认同时生成合同包和结算包",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / ".tmp/review-packages",
        help="同时生成两个包时的输出目录",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="只生成单个包时的输出路径；需同时指定--package，合同为.md、结算为.zip",
    )
    parser.add_argument("--list", action="store_true", help="只列出所选输出，不生成文件")
    args = parser.parse_args()
    if args.output is not None and args.package == "all":
        parser.error("--output 只适用于 --package contracts 或 --package settlements")

    packages = PACKAGE_KINDS if args.package == "all" else (args.package,)
    if args.list:
        for package in packages:
            if len(packages) > 1:
                print(f"[{PACKAGE_LABELS[package]}包]")
            if package == "contracts":
                print(PACKAGE_OUTPUT_NAMES[package])
            else:
                for path in collect(ROOT, package):
                    print(path.relative_to(ROOT).as_posix())
        return

    results = []
    for package in packages:
        output = args.output if args.output is not None else args.output_dir / PACKAGE_OUTPUT_NAMES[package]
        results.append(build(ROOT, output, package))
    payload = results[0] if len(results) == 1 else results
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
