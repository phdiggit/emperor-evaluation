"""Package current contracts and settlements verbatim for temporary chat sessions.

Usage: python package_net_review.py
Default: .tmp/evaluation-packages/皇帝三体系评估包.zip
Reads the working tree without running scoring or rebuild commands.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile

import yaml


ROOT = Path(__file__).resolve().parent
PACKAGE_LABELS = {
    "all": "皇帝三体系评估包",
    "contracts": "皇帝三体系评估包-统治绩效合同",
    "settlements": "皇帝三体系评估包-统治绩效结算",
    "profile-contract": "皇帝三体系评估包-人物画像合同",
    "profile-settlements": "皇帝三体系评估包-人物画像结算",
    "historical-impact-contract": "皇帝三体系评估包-历史影响合同",
    "historical-impact-settlements": "皇帝三体系评估包-历史影响结算",
}
PACKAGE_KINDS = tuple(PACKAGE_LABELS)
PACKAGE_OUTPUT_NAMES = {key: f"{label}.zip" for key, label in PACKAGE_LABELS.items()}
NET_ROOT = "docs/评分结算/净收益"
PROFILE_ROOT = "docs/评分结算/人物画像"
ROUTER_SCHEMA = "formal-json-polity-router-v1"


def source_path(root: Path, relative: str) -> Path:
    """Reject missing sources, symlinks and paths outside the source tree."""
    path = root / relative
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError(f"来源路径非法：{relative}")
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"不接受符号链接或仓库外文件：{path}")
    if path.suffix.lower() not in {".md", ".json", ".yml", ".yaml"}:
        raise ValueError(f"不支持的来源类型：{path}")
    return path


def encode_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def collect(root: Path, package: str = "all") -> list[Path]:
    """Use current entry points and bounded directories, never arbitrary links."""
    if package not in PACKAGE_KINDS:
        raise ValueError(f"未知包类型：{package}")
    root = root.resolve()
    project = yaml.safe_load(source_path(root, "config/project.yml").read_text(encoding="utf-8-sig"))
    selected = {
        "config/project.yml",
        project["evaluation_systems"]["governing_document"],
        project["canonical_ruler_pool"]["json"],
        project["canonical_ruler_pool"]["markdown"],
    }

    def add_tree(relative: str, *, contracts: bool = False) -> None:
        directory = root / relative
        if not directory.is_dir():
            raise FileNotFoundError(directory)
        for path in directory.rglob("*"):
            if not path.is_file() or path.name == "README.md":
                continue
            if contracts:
                include = path.suffix == ".md"
            else:
                # Keep current adjudication/evidence notes; exclude process audits.
                include = path.suffix in {".md", ".json"} and not any(
                    token in part.lower()
                    for part in path.relative_to(directory).parts
                    for token in ("审计", "audit", "adjudicat", "迁移说明")
                )
            if include:
                selected.add(path.relative_to(root).as_posix())

    def item_directories(parent: str) -> list[str]:
        directories = []
        for item in ("第一项", "第二项", "第三项", "第四项"):
            matches = [p for p in (root / parent).iterdir()
                       if p.is_dir() and p.name.startswith(item)]
            if len(matches) != 1:
                raise ValueError(f"{parent}/{item}需要唯一目录，实际{len(matches)}个")
            directories.append(matches[0].relative_to(root).as_posix())
        return directories

    if package in {"all", "contracts"}:
        selected.add(project["scoring_contract"]["governing_document"])
        selected.add(project["scoring_contract"]["composite_governance_context"])
        selected.add("docs/分项规则/军事成本合同导航.md")
        for directory in item_directories("docs/分项规则"):
            add_tree(directory, contracts=True)
        add_tree("docs/证据规则", contracts=True)

    profile = project["profile_assessment"]
    if package in {"all", "profile-contract"}:
        selected.add(profile["contract"])
        add_tree("docs/分项规则/人物画像轴", contracts=True)
        selected.add("docs/证据规则/公共成果登记与人物画像规则.md")
        selected.update(axis["contract"] for axis in profile["settled_axes"].values())

    impact = project["historical_impact_assessment"]
    if package in {"all", "historical-impact-contract"}:
        selected.update((impact["contract"], impact["calibration_document"]))

    if package in {"all", "settlements"}:
        selected.add(project["scoring_contract"]["composite_governance_context"])
        selected.update(project["scoring_contract"][key]
                        for key in ("composite_ranking_json", "composite_ranking_markdown"))
        for item in project["formal_settlements"].values():
            selected.update(item[key] for key in ("json", "markdown") if key in item)
            selected.update(item.get("component_markdown", []))
            selected.update(item[key] for key in ("military_cost_adjudications", "d_json", "d_markdown")
                            if key in item)
        for directory in item_directories(NET_ROOT):
            add_tree(directory)

    if package in {"all", "profile-settlements"}:
        selected.update(profile[key] for key in ("manifest_json", "manifest_markdown", "summary_markdown"))
        manifest = json.loads(source_path(root, profile["manifest_json"]).read_text(encoding="utf-8-sig"))
        axes = manifest["axes"]
        if [axis["axis_code"] for axis in axes] != profile["axis_order"]:
            raise ValueError("画像正式入口轴序与config/project.yml不一致")
        for axis in axes:
            current = profile["settled_axes"][axis["axis_code"]]
            for key in ("json", "markdown"):
                name = (Path(PROFILE_ROOT) / axis[key]).as_posix()
                if name != current[key]:
                    raise ValueError(f"画像正式入口与config/project.yml不一致：{name}")
                selected.add(name)

    if package in {"all", "historical-impact-settlements"}:
        selected.update((impact["json"], impact["markdown"]))

    # Follow only formal JSON router shards. Missing shards must fail packaging.
    pending = list(selected)
    while pending:
        name = pending.pop()
        path = source_path(root, name)
        if path.suffix != ".json":
            continue
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict) and data.get("schema_version") == ROUTER_SCHEMA:
            for route in data["routes"]:
                relative = route["path"]
                if Path(relative).is_absolute() or ".." in Path(relative).parts:
                    raise ValueError(f"路由分片路径非法：{name} -> {relative}")
                target = (Path(name).parent / relative).as_posix()
                if target not in selected:
                    selected.add(target)
                    pending.append(target)
    return [source_path(root, name) for name in sorted(selected)]


def package_note(package: str) -> bytes:
    text = f"""# {PACKAGE_LABELS[package]}

供聊天版临时会话读取当前合同、结算数据与记录中已有的裁决依据。先读本说明和
`config/project.yml`，再按人物、体系和具体问题定位文件，无需先检索GitHub。
本次选择：`{package}`；只有`all`包含三个体系的全部合同与结算。

## 阅读入口

- 共同上位合同：`docs/项目总纲/皇帝综合评价体系合同.md`。
- 统治绩效：从`config/project.yml`的`scoring_contract`及`formal_settlements`进入总榜与四项结算。
- 总榜治理规模／复杂度是非计分背景，逐人分档与依据见`scoring_contract.composite_governance_context`。
- 人物画像：从`profile_assessment`进入九轴合同、轴入口与九轴汇总。
- 历史影响：从`historical_impact_assessment`进入总则、校准依据和正式结算。
- 人物身份、适用范围及综合榜就绪状态：从`canonical_ruler_pool`进入正式人物池。

## 文件与数据约定

所有入包源文件逐字节照搬当前工作树（包含未提交改动）；合同不删节、不改写、不合并。
原仓库目录保持不变，便于引用原路径，避免重名，并保持JSON路由与分片关系。
文件清单记录来源路径、字节数和SHA-256；包内只额外生成本说明与文件清单。

第一项以其Markdown结算源为准；其余按项目配置读取正式JSON，Markdown为阅读视图。
JSON若标记`formal-json-polity-router-v1`，必须按`routes[].path`读取相对该文件的分片；
路由自身不等于人物数据。包内已包含全部所选路由的分片，无需运行仓库Python代码。
统治绩效、人物画像、历史影响分别解释，不合并为三体系总分，不以一个体系反推另一个体系。

## 范围与追溯边界

保留完整合同、结算JSON/Markdown、必要入口、人物池及总榜治理背景分类源；不含代码、测试、展示素材、
退役归档、过程审计、其他配置裁决输入及完整史料库。结算中保留的史源、归责、去重依据和引用原文不改动。
配置和原合同也可能引用包外文件；引用存在不表示该文件已入包。
需要包外证据时，明确列出缺失的原路径或史料位置，请用户补充，不能把包内阅读当作完整史料复核。
本包用于解释和讨论当前结算，不是离线重建环境，也不宣称完成新的历史语义审查。
"""
    return text.encode("utf-8")


def prepare(root: Path, package: str = "all") -> tuple[dict[str, bytes], dict]:
    root = root.resolve()
    entries: dict[str, bytes] = {}
    inventory = []
    routers = 0
    for path in collect(root, package):
        name = path.relative_to(root).as_posix()
        content = path.read_bytes()
        content.decode("utf-8-sig")
        entries[name] = content
        inventory.append({"path": name, "bytes": len(content),
                          "sha256": hashlib.sha256(content).hexdigest(),
                          "transformation": "VERBATIM"})
    for name, content in entries.items():
        if not name.endswith(".json"):
            continue
        data = json.loads(content)
        if isinstance(data, dict) and data.get("schema_version") == ROUTER_SCHEMA:
            routers += 1
            for route in data["routes"]:
                target = (Path(name).parent / route["path"]).as_posix()
                if target not in entries:
                    raise ValueError(f"路由分片未入包：{name} -> {target}")
    manifest = {
        "format": "emperor-three-system-evaluation-package-v1",
        "package": package,
        "package_label": PACKAGE_LABELS[package],
        "source": "CURRENT_WORKING_TREE_INCLUDING_UNCOMMITTED_CHANGES",
        "file_count": len(inventory),
        "uncompressed_source_bytes": sum(item["bytes"] for item in inventory),
        "router_count": routers,
        "files": inventory,
    }
    entries["文件清单.json"] = encode_json(manifest)
    entries["00-使用说明.md"] = package_note(package)
    return entries, manifest


def build(root: Path, output: Path, package: str = "all") -> dict:
    entries, manifest = prepare(root, package)
    output = output.resolve()
    if output.suffix.lower() != ".zip":
        raise ValueError("输出路径必须以.zip结尾；合同也以原文件收入ZIP")
    output.parent.mkdir(parents=True, exist_ok=True)
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
                if archive.read(name) != content:
                    raise ValueError(f"入包内容校验失败：{name}")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return {"package": package, "output": str(output),
            "source_files": manifest["file_count"], "archive_entries": len(entries),
            "zip_bytes": output.stat().st_size,
            "uncompressed_source_bytes": manifest["uncompressed_source_bytes"],
            "router_count": manifest["router_count"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="原样打包三个体系的合同和结算，供聊天版临时会话读取")
    parser.add_argument("--package", choices=PACKAGE_KINDS, default="all",
                        help="默认生成一个完整三体系包；也可单选某体系合同或结算")
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".tmp/evaluation-packages",
                        help="输出目录")
    parser.add_argument("--output", type=Path, help="指定ZIP输出路径")
    parser.add_argument("--list", action="store_true", help="只列出入包源文件，不生成文件")
    args = parser.parse_args()
    if args.list:
        for path in collect(ROOT, args.package):
            print(path.relative_to(ROOT).as_posix())
        return
    output = args.output if args.output is not None else args.output_dir / PACKAGE_OUTPUT_NAMES[args.package]
    print(json.dumps(build(ROOT, output, args.package), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
