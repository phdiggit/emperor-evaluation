"""Build a data-only review ZIP from the current working tree.

Usage: codex-win run -- python package_net_review.py [--output PATH] [--list]
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
ITEMS = ("第一项", "第二项", "第三项", "第四项")
SUFFIXES = {".md", ".json", ".yml", ".yaml"}
FORBIDDEN = ("第五项", "人物画像", "profile", "tests", "test", "src", ".codex")
GOVERNING = "docs/项目总纲/皇帝综合评价体系评分标准.md"
FIXED = (
    GOVERNING,
    "docs/项目总纲/正式评价对象范围.md",
    "docs/证据规则/军事成本评估合同.md",
    "docs/证据规则/军事对手战争机器O档合同.md",
    "docs/证据规则/战争成本安全收益与战争回报档位.md",
    "docs/评分结算/00-皇帝功业与治理净收益榜.json",
    "docs/评分结算/00-皇帝功业与治理净收益榜.md",
    "config/common/canonical-ruler-pool.json",
    "config/common/canonical-ruler-admission-adjudications.yml",
    "config/military/opponent-system-contract.json",
)
CONFIG_DIRS = ("config/first-item", "config/second-item", "config/third-item")


def allowed(name: str) -> bool:
    path = Path(name)
    return path.suffix.lower() in SUFFIXES and not any(
        token in part.lower() for part in path.parts for token in FORBIDDEN
    )


def collect(root: Path) -> list[Path]:
    """Whitelist current rule/settlement roots; never chase arbitrary evidence links."""
    selected = {root / name for name in FIXED}
    directories = [root / name for name in CONFIG_DIRS]
    for parent in ("docs/分项规则", "docs/评分结算"):
        for item in ITEMS:
            matches = [p for p in (root / parent).iterdir()
                       if p.is_dir() and p.name.startswith(item)]
            if len(matches) != 1:
                raise ValueError(f"{parent}/{item}: 需要唯一当前目录，实际{len(matches)}个")
            directories.extend(matches)
    for directory in directories:
        if not directory.is_dir():
            raise FileNotFoundError(directory)
        selected.update(p for p in directory.rglob("*") if p.is_file()
                        and allowed(p.relative_to(root).as_posix()))
    for path in selected:
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
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


def prepare(root: Path) -> tuple[dict[str, bytes], dict]:
    entries: dict[str, bytes] = {}
    inventory = []
    for path in collect(root):
        name = path.relative_to(root).as_posix()
        original = path.read_bytes()
        original.decode("utf-8-sig")  # Reject unreadable text before opening the output.
        content = governing_excerpt(original) if name == GOVERNING else original
        entries[name] = content
        inventory.append({
            "path": name, "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "source_sha256": hashlib.sha256(original).hexdigest(),
            "transformation": "NET_BENEFIT_EXCERPT" if name == GOVERNING else "VERBATIM",
        })
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
        "format": "net-benefit-review-package-v1",
        "source": "CURRENT_WORKING_TREE_INCLUDING_UNCOMMITTED_CHANGES",
        "scope": list(ITEMS),
        "file_count": len(inventory),
        "uncompressed_source_bytes": sum(item["bytes"] for item in inventory),
        "router_count": routers,
        "exclusions": ["代码与测试", "第五项专用文件", "人物画像专用文件",
                       "公共成果和史料全文", "运行配置与本地临时产物"],
        "files": inventory,
    }
    entries["文件清单.json"] = encode_json(manifest)
    entries["00-审查说明.md"] = (
        "# 净收益体系审查包\n\n"
        "## 范围与读取顺序\n\n"
        "1. 阅读 `docs/项目总纲/皇帝综合评价体系评分标准.md`（净收益节选）与正式评价对象范围。\n"
        "2. 阅读 `docs/分项规则/` 中前四项合同与 `docs/证据规则/` 中军事合同。\n"
        "3. 阅读 `docs/评分结算/00-皇帝功业与治理净收益榜.json`，再沿对应分项检查正式结算。\n"
        "4. 需要核对起点、窗口、信用、扣分和跨项去重时，读取 `config/` 中的裁决数据。\n\n"
        "## 数据含义\n\n"
        "本包读取打包时的工作树，包含未提交的当前修改，不运行重建、不修改分数。"
        "除注明的总纲节选外，文件内容逐字节保留；文件清单记录源文件和入包内容的SHA-256。\n\n"
        "JSON是机器读取入口，Markdown是阅读视图；第一项存在Markdown结算权威模式，"
        "发现分叉应依上位合同和具体裁决审查，不机械指定修补方向。"
        "分片JSON入口包含 `payload_metadata`、`collections` 和 `routes`；"
        "请读取routes中每个分片的相对path，各分片的collections记录中包含positions与records，"
        "按positions可还原原始顺序；不要把路由索引误认为空结果。\n\n"
        "综合评价对象以 `config/common/canonical-ruler-pool.json` 为准，"
        "综合排名只消费COMPOSITE_READY对象；各项候选池可能更大。"
        "第四项的语义验收状态应读取其当前正式声明，结构完整不代表语义复审已闭合。\n\n"
        "本包不含公共成果及史料全文，结算内已有的证据、引文与lineage保留。"
        "引用包外资料不等于证据不存在，也不等于已核验原文；无法核对时标记为包外材料待查。"
        "第五项及人物画像专用文件不入包，前四项规则内的跨项边界提及不删。\n\n"
        "## 可直接使用的审查要求\n\n"
        "请仅分析本包前四项净收益规则与结算，不审查代码、测试、第五项或人物画像。"
        "先核对合同、公式、对象范围、本人实权窗口、归责、去重和上下游同值，"
        "再审查裁决依据是否支持实际档位和分数。逐条列出问题、文件路径、人物ID、"
        "字段、适用规则和实际计分影响；区分明确错误、语义疑点和包外材料待查，"
        "不要凭材料缺失推断零分，也不要把结构通过当作全池语义通过。\n"
    ).encode("utf-8")
    return entries, manifest


def build(root: Path, output: Path) -> dict:
    entries, manifest = prepare(root)
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
    return {"output": str(output), "source_files": manifest["file_count"],
            "archive_entries": len(entries), "zip_bytes": output.stat().st_size,
            "uncompressed_source_bytes": manifest["uncompressed_source_bytes"],
            "router_count": manifest["router_count"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="前四项净收益规则与结算审查包（不含代码、测试、第五项、画像）")
    parser.add_argument("--output", type=Path, default=ROOT / ".tmp/review-packages/net-benefit-review.zip",
                        help="输出ZIP路径；默认项目根.tmp/review-packages/net-benefit-review.zip")
    parser.add_argument("--list", action="store_true", help="只列出源文件，不生成ZIP")
    args = parser.parse_args()
    if args.list:
        for path in collect(ROOT):
            print(path.relative_to(ROOT).as_posix())
    else:
        print(json.dumps(build(ROOT, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
