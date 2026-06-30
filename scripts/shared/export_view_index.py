from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path


I5B_HUMAN_AUTO_CHAIN_REQUIRED_DIRS = (
    Path("第五项B") / "人工审核" / "入口",
    Path("第五项B") / "人工审核" / "自动裁判链" / "自动结算草案",
    Path("第五项B") / "人工审核" / "自动裁判链" / "规则敏感点",
    Path("第五项B") / "人工审核" / "自动裁判链" / "正式定档草案",
    Path("第五项B") / "人工审核" / "自动裁判链" / "试点闭环",
)
I5B_HUMAN_EVIDENCE_CHAIN_REQUIRED_DIRS = (
    Path("第五项B") / "人工审核" / "证据链" / "净证据池",
    Path("第五项B") / "人工审核" / "证据链" / "证据卡",
    Path("第五项B") / "人工审核" / "证据链" / "证据簇",
    Path("第五项B") / "人工审核" / "证据链" / "附录",
)
I5B_MACHINE_EVIDENCE_CHAIN_REQUIRED_DIRS = (
    Path("第五项B") / "机器审计" / "证据链" / "净证据池",
    Path("第五项B") / "机器审计" / "证据链" / "证据卡",
    Path("第五项B") / "机器审计" / "证据链" / "证据簇",
    Path("第五项B") / "机器审计" / "证据链" / "检索包",
    Path("第五项B") / "机器审计" / "证据链" / "附录",
)


def ensure_i5b_human_readable_export_scaffold(markdown_view_root: Path) -> None:
    for relative_dir in (
        *I5B_HUMAN_AUTO_CHAIN_REQUIRED_DIRS,
        *I5B_HUMAN_EVIDENCE_CHAIN_REQUIRED_DIRS,
        *I5B_MACHINE_EVIDENCE_CHAIN_REQUIRED_DIRS,
    ):
        (markdown_view_root / relative_dir).mkdir(parents=True, exist_ok=True)


def _format_markdown_link(markdown_view_root: Path, target: Path) -> str:
    try:
        relative = target.relative_to(markdown_view_root)
    except ValueError:
        relative = target
    return f"./{relative.as_posix()}"


def write_export_view_index(
    markdown_view_root: Path,
    *,
    i5b_active_links: Sequence[tuple[str, Path]] | None = None,
) -> Path:
    markdown_view_root.mkdir(parents=True, exist_ok=True)
    index_path = markdown_view_root / "导出视图总索引.md"
    lines = [
        "# 导出视图总索引",
        "",
        "## 目录结构说明",
        "",
        "- [第五项B](./第五项B/)",
        "",
        "## 人工审核主入口",
        "",
        "- [第五项B自动裁判链](./第五项B/人工审核/自动裁判链/)",
        "- [第五项B证据链](./第五项B/人工审核/证据链/)",
        "- [第五项B审核入口](./第五项B/人工审核/入口/)",
        "",
    ]
    if i5b_active_links:
        lines.extend(
            [
                "## 第五项B当前活动产物",
                "",
                *[
                    f"- [{label}]({_format_markdown_link(markdown_view_root, path)})"
                    for label, path in i5b_active_links
                ],
                "",
            ]
        )
    lines.extend(
        [
            "## 机器审计入口",
            "",
            "- [第五项B机器审计证据链](./第五项B/机器审计/证据链/)",
            "",
            "## 待人工确认清单",
            "",
            "暂无。",
            "",
            "## 旧根目录平铺文件禁用说明",
            "",
            "根目录旧式平铺 Markdown 禁用；人工审核和机器审计视图必须归入对应目录。",
            "",
        ]
    )
    index_path.write_text("\n".join(lines), encoding="utf-8")
    return index_path
