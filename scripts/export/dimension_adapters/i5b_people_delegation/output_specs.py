from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


DATA_DIR = ROOT / "data"


OUTPUT_LAYOUT_CANONICAL = "canonical"


OUTPUT_LAYOUT_SPLIT = "split"


MARKDOWN_VIEW_ROOT = ROOT / "exports" / "markdown_views"


I5B_MARKDOWN_VIEW_ROOT = MARKDOWN_VIEW_ROOT / "第五项B"


I5B_HUMAN_REVIEW_ROOT = I5B_MARKDOWN_VIEW_ROOT / "人工审核"


AUTO_ADJUDICATION_HUMAN_ROOT = I5B_HUMAN_REVIEW_ROOT / "自动裁判链"


AUTO_DRAFT_DIR = AUTO_ADJUDICATION_HUMAN_ROOT / "自动结算草案"


AUTO_DRAFT_DETAIL_DIR = AUTO_DRAFT_DIR / "人物详情"


AUTO_DRAFT_APPENDIX_DIR = AUTO_DRAFT_DIR / "附录"


RULE_SENSITIVE_DIR = AUTO_ADJUDICATION_HUMAN_ROOT / "规则敏感点"


FORMAL_DRAFT_DIR = AUTO_ADJUDICATION_HUMAN_ROOT / "正式定档草案"


TRIAL_CLOSURE_DIR = AUTO_ADJUDICATION_HUMAN_ROOT / "试点闭环"


REVIEW_ENTRY_DIR = I5B_HUMAN_REVIEW_ROOT / "入口"


LEGACY_WORKFLOW_SUBJECT = "第五项B三人"


def auto_export_path(workflow_subject: str) -> Path:
    return AUTO_DRAFT_DIR / f"{workflow_subject}自动结算草案.md"


RULES_EXPORT_PATH = RULE_SENSITIVE_DIR / "第五项B自动结算规则敏感点清单.md"


def formal_export_path(workflow_subject: str) -> Path:
    return FORMAL_DRAFT_DIR / f"{workflow_subject}正式定档落地表.md"


SCORE_MAP_DRAFT_EXPORT_PATH = FORMAL_DRAFT_DIR / "第五项B评分标尺与档位映射草案.md"


def closure_export_path(workflow_subject: str) -> Path:
    return TRIAL_CLOSURE_DIR / f"{workflow_subject}内部闭环收尾.md"


def review_entry_export_path(workflow_subject: str) -> Path:
    return REVIEW_ENTRY_DIR / f"{workflow_subject}专人审核入口.md"


def review_workbench_export_path(workflow_subject: str) -> Path:
    return REVIEW_ENTRY_DIR / f"{workflow_subject}人工复核工作台.md"


def review_matrix_export_path(workflow_subject: str) -> Path:
    return REVIEW_ENTRY_DIR / f"{workflow_subject}矩阵说明.md"


REVIEW_PLAN_EXPORT_PATH = REVIEW_ENTRY_DIR / "第五项B试点计划.md"


EXPORT_PATH = auto_export_path(LEGACY_WORKFLOW_SUBJECT)
FORMAL_EXPORT_PATH = formal_export_path(LEGACY_WORKFLOW_SUBJECT)
CLOSURE_EXPORT_PATH = TRIAL_CLOSURE_DIR / "第五项B三人试点内部闭环收尾.md"
REVIEW_ENTRY_EXPORT_PATH = review_entry_export_path(LEGACY_WORKFLOW_SUBJECT)
REVIEW_WORKBENCH_EXPORT_PATH = REVIEW_ENTRY_DIR / "第五项B三人试点人工复核工作台.md"
REVIEW_MATRIX_EXPORT_PATH = REVIEW_ENTRY_DIR / "第五项B三人试点矩阵说明.md"


LEGACY_FLAT_EXPORT_PATHS = (
    MARKDOWN_VIEW_ROOT / "第五项B三人自动结算草案.md",
    MARKDOWN_VIEW_ROOT / "第五项B自动结算规则敏感点清单.md",
    MARKDOWN_VIEW_ROOT / "第五项B三人正式定档落地表.md",
    MARKDOWN_VIEW_ROOT / "第五项B评分标尺与档位映射草案.md",
    MARKDOWN_VIEW_ROOT / "第五项B三人试点内部闭环收尾.md",
)


LEGACY_NESTED_SUBJECT_EXPORT_PATHS = (
    EXPORT_PATH,
    FORMAL_EXPORT_PATH,
    CLOSURE_EXPORT_PATH,
    REVIEW_ENTRY_EXPORT_PATH,
    REVIEW_WORKBENCH_EXPORT_PATH,
    REVIEW_MATRIX_EXPORT_PATH,
)


def person_detail_export_path(person: str) -> Path:
    return AUTO_DRAFT_DETAIL_DIR / f"{person}.md"


def person_appendix_export_path(person: str) -> Path:
    return AUTO_DRAFT_APPENDIX_DIR / f"{person}_长字段附录.md"


def person_detail_relative_link(person: str) -> str:
    return f"./人物详情/{person_detail_export_path(person).name}"


def person_detail_backlink() -> str:
    return f"../{EXPORT_PATH.name}"
