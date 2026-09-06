"""Build separate data-only review ZIPs from the current working tree.

Usage: python package_net_review.py [--package {all,contracts,settlements}]
The default output lives in .tmp/review-packages/. No scoring command is run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PACKAGE_KINDS = ("contracts", "settlements")
PACKAGE_LABELS = {"contracts": "合同", "settlements": "结算"}
PACKAGE_OUTPUT_NAMES = {
    "contracts": "净收益体系-合同审查包.zip",
    "settlements": "净收益体系-结算审查包.zip",
}
ITEMS = ("第一项", "第二项", "第三项", "第四项")
SUFFIXES = {".md", ".json", ".yml", ".yaml"}
FORBIDDEN = ("第五项", "人物画像", "profile", "tests", "test", "src", ".codex")
GOVERNING = "docs/项目总纲/皇帝综合评价体系评分标准.md"

CONTRACT_FIXED = (
    GOVERNING,
    "docs/项目总纲/正式评价对象范围.md",
    "docs/分项规则/军事成本合同导航.md",
    "docs/证据规则/军事成本评估合同.md",
    "docs/证据规则/军事成本高档与证据裁决合同.md",
    "docs/证据规则/军事对手战争机器O档合同.md",
    "docs/证据规则/战争成本安全收益与战争回报档位.md",
    "config/military/opponent-system-contract.json",
    "config/project.yml",
)
SETTLEMENT_FIXED = (
    "docs/评分结算/00-皇帝统治成效综合评分榜.json",
    "docs/评分结算/00-皇帝统治成效综合评分榜.md",
    "config/common/canonical-ruler-pool.json",
    "config/common/canonical-ruler-admission-adjudications.yml",
)
CONFIG_DIRS = ("config/first-item", "config/second-item", "config/third-item")
PACKAGE_FIXED = {"contracts": CONTRACT_FIXED, "settlements": SETTLEMENT_FIXED}
PACKAGE_ITEM_PARENTS = {"contracts": ("docs/分项规则",), "settlements": ("docs/评分结算",)}
PACKAGE_EXTRA_DIRS = {"contracts": (), "settlements": CONFIG_DIRS}
PACKAGE_EXCLUSIONS = {
    "contracts": (
        "正式结算与裁决输入",
        "代码与测试",
        "第五项专用文件",
        "人物画像专用文件",
        "公共成果和史料全文",
        "服务运行配置与本地临时产物",
    ),
    "settlements": (
        "总纲、分项与证据合同正文",
        "代码与测试",
        "第五项专用文件",
        "人物画像专用文件",
        "公共成果和史料全文",
        "服务运行配置与本地临时产物",
    ),
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
    for item in ITEMS:
        matches = [p for p in base.iterdir() if p.is_dir() and p.name.startswith(item)]
        if len(matches) != 1:
            raise ValueError(f"{parent}/{item}: 需要唯一当前目录，实际{len(matches)}个")
        directories.append(matches[0])
    return directories


def collect(root: Path, package: str) -> list[Path]:
    """Whitelist either the contract or settlement roots; never chase arbitrary links."""
    package = validate_package_kind(package)
    root = root.resolve()
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
            if p.is_file() and allowed(p.relative_to(root).as_posix())
        )
    for path in selected:
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError(f"不接受符号链接或仓库外文件：{path}")
        if not allowed(path.relative_to(root).as_posix()):
            raise ValueError(f"白名单中出现禁入文件：{path}")
    return sorted(selected, key=lambda p: p.relative_to(root).as_posix())


def governing_excerpt(raw: bytes) -> bytes:
    """Remove only the dedicated fifth-item section and its summary-table rows."""
    text = raw.decode("utf-8-sig")
    pattern = r"^## [^\n]*第五项[^\n]*\n.*?(?=^## |\Z)"
    text, count = re.subn(pattern, "", text, flags=re.MULTILINE | re.DOTALL)
    if count != 1:
        raise ValueError("总纲第五项专章结构已变，请更新节选规则后打包")
    text = "\n".join(line for line in text.splitlines()
                     if not re.match(r"^\|\s*第五项", line)) + "\n"
    note = ("> 审查包节选：来源为仓库同路径总纲，移除第五项专章及其分值总表行。"
            "前四项与第五项之间的归责、去重边界原文保留；本节选不改写仓库原件。\n\n")
    return (note + text).encode("utf-8")


def encode_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def review_note(package: str) -> bytes:
    if package == "contracts":
        text = (
            "# 净收益体系合同审查包\n\n"
            "## 范围与读取顺序\n\n"
            "1. 先读 `config/project.yml` 确认当前正式入口，再阅读总纲净收益节选与正式评价对象范围。\n"
            "2. 按 `docs/分项规则/军事成本合同导航.md` 路由，阅读前四项分项合同及证据规则中的军事合同。\n"
            "3. 需要核对O档机器映射时，读取 `config/military/opponent-system-contract.json`；结算数据在配套结算包。\n\n"
            "## 数据含义\n\n"
            "本包读取打包时的工作树，包含未提交的当前修改，不运行重建、不修改分数。"
            "除注明的总纲节选外，文件内容逐字节保留；文件清单记录源文件和入包内容的SHA-256。\n\n"
            "本包只分析前四项净收益合同、对象范围和共享军事合同，不审查正式分值、第五项、人物画像或代码。"
            "合同变更须结合配套结算包检查正式入口、公式消费和上下游同值。\n"
        )
    else:
        text = (
            "# 净收益体系结算审查包\n\n"
            "## 范围与读取顺序\n\n"
            "1. 先读 `config/common/canonical-ruler-pool.json`，确认正式评价对象及 `COMPOSITE_READY` 状态。\n"
            "2. 阅读 `docs/评分结算/00-皇帝统治成效综合评分榜.json` 及其Markdown阅读视图。\n"
            "3. 再按前四项结算目录检查正式 JSON、Markdown、路由分片和对应裁决输入。\n"
            "4. 合同正文见配套合同包；本包不把结算快照反向当作规则。\n\n"
            "## 数据含义\n\n"
            "本包读取打包时的工作树，包含未提交的当前修改，不运行重建、不修改分数。"
            "文件内容逐字节保留；文件清单记录源文件和入包内容的SHA-256。\n\n"
            "JSON是机器读取入口，Markdown是阅读视图；第一项存在Markdown结算权威模式。"
            "分片JSON入口包含 `payload_metadata`、`collections` 和 `routes`；"
            "请读取routes中每个分片的相对path，各分片的collections记录中包含positions与records，"
            "按positions可还原原始顺序；不要把路由索引误认为空结果。\n\n"
            "本包只分析前四项正式结算、综合榜和结算输入，不审查代码、测试、合同正文、第五项或人物画像。"
            "第四项的语义验收状态应读取其当前正式声明，结构完整不代表语义复审已闭合。\n"
        )
    return text.encode("utf-8")


def prepare(root: Path, package: str) -> tuple[dict[str, bytes], dict]:
    package = validate_package_kind(package)
    root = root.resolve()
    entries: dict[str, bytes] = {}
    inventory = []
    for path in collect(root, package):
        name = path.relative_to(root).as_posix()
        original = path.read_bytes()
        original.decode("utf-8-sig")  # Reject unreadable text before opening the output.
        content = governing_excerpt(original) if name == GOVERNING else original
        entries[name] = content
        inventory.append(
            {
                "path": name,
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "source_sha256": hashlib.sha256(original).hexdigest(),
                "transformation": "NET_BENEFIT_EXCERPT" if name == GOVERNING else "VERBATIM",
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
        "format": "net-benefit-review-package-v2",
        "package": package,
        "package_label": PACKAGE_LABELS[package],
        "source": "CURRENT_WORKING_TREE_INCLUDING_UNCOMMITTED_CHANGES",
        "scope": list(ITEMS),
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
        "source_files": manifest["file_count"],
        "archive_entries": len(entries),
        "zip_bytes": output.stat().st_size,
        "uncompressed_source_bytes": manifest["uncompressed_source_bytes"],
        "router_count": manifest["router_count"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="分别生成前四项净收益合同包和结算包（不含代码、测试、第五项、画像）"
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
        help="只生成单个包时的ZIP输出路径；需同时指定--package",
    )
    parser.add_argument("--list", action="store_true", help="只列出所选包的源文件，不生成ZIP")
    args = parser.parse_args()
    if args.output is not None and args.package == "all":
        parser.error("--output 只适用于 --package contracts 或 --package settlements")

    packages = PACKAGE_KINDS if args.package == "all" else (args.package,)
    if args.list:
        for package in packages:
            if len(packages) > 1:
                print(f"[{PACKAGE_LABELS[package]}包]")
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
