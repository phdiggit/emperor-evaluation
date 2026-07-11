from __future__ import annotations

from pathlib import Path

from scripts.dev import retrieval_v3_target_alias_backfill as tool


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_alias_rows_include_canonical_name_and_seed_aliases(tmp_path: Path) -> None:
    emperor_list = tmp_path / "emperors.yml"
    alias_file = tmp_path / "aliases.yml"
    write(emperor_list, "- 刘邦\n- 李世民\n")
    write(
        alias_file,
        """
刘邦:
  - alias: 汉高祖
    alias_type: temple_name
李世民:
  - alias: 太宗
    alias_type: temple_name
    scopes: [李渊, 李世民]
""".lstrip(),
    )

    names = tool.load_emperor_names(emperor_list)
    aliases = tool.load_alias_seed(alias_file)
    rows = tool.alias_rows_for_emperors(names, aliases)

    assert names == ["刘邦", "李世民"]
    assert {"emperor_name": "刘邦", "alias": "刘邦", "alias_type": "name", "source": "canonical_list", "scopes": []} in rows
    assert any(row["emperor_name"] == "刘邦" and row["alias"] == "汉高祖" for row in rows)
    assert any(row["emperor_name"] == "李世民" and row["alias"] == "太宗" and row["scopes"] == ["李世民"] for row in rows)


def test_alias_seed_rejects_unknown_emperor(tmp_path: Path) -> None:
    emperor_list = tmp_path / "emperors.yml"
    alias_file = tmp_path / "aliases.yml"
    write(emperor_list, "- 刘邦\n")
    write(alias_file, "李渊:\n  - alias: 唐高祖\n    alias_type: temple_name\n")

    try:
        tool.alias_rows_for_emperors(tool.load_emperor_names(emperor_list), tool.load_alias_seed(alias_file))
    except tool.TargetAliasBackfillError as exc:
        assert "unknown emperor name" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("unknown alias owner should be rejected")


def test_default_alias_plan_covers_all_configured_emperors() -> None:
    names = tool.load_emperor_names(tool.DEFAULT_EMPEROR_LIST)
    rows = tool.alias_rows_for_emperors(names, tool.load_alias_seed(tool.DEFAULT_ALIAS_FILE))
    plan = tool.build_plan(emperor_names=names, alias_rows=rows, schema_name="retrieval_v3")

    assert plan["totals"]["emperor_count"] == 185
    assert plan["totals"]["name_alias_count"] == 185
    assert plan["totals"]["extra_alias_count"] > 0
    assert any(row["emperor_name"] == "李治" and row["alias"] == "高宗" for row in rows)
