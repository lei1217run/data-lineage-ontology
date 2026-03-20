from pathlib import Path

import yaml


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        return "", text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "", text
    frontmatter = parts[1].strip("\n")
    body = parts[2].lstrip("\n")
    return frontmatter, body


def _load_schema(schema_path: Path) -> dict:
    if not schema_path.exists():
        return {}
    with schema_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        return {}
    return data


def _compute_extension_phrase(schema: dict, ext_schema: dict | None) -> str:
    source: dict = {}
    if ext_schema:
        source = ext_schema
    elif schema:
        source = schema
    if not source:
        return ""
    types = source.get("types") or {}
    relations = source.get("relations") or {}
    if not isinstance(types, dict):
        types = {}
    if not isinstance(relations, dict):
        relations = {}
    type_names = sorted(str(name) for name in types.keys())
    relation_names = sorted(str(name) for name in relations.keys())
    if not type_names and not relation_names:
        return ""
    parts: list[str] = []
    if type_names:
        parts.append("实体类型 " + "、".join(type_names))
    if relation_names:
        parts.append("关系 " + "、".join(relation_names))
    phrase = "；扩展能力：新增" + "；".join(parts)
    acyclic_relations = 0
    for rel_name, rel_def in relations.items():
        if isinstance(rel_def, dict) and rel_def.get("acyclic"):
            acyclic_relations += 1
    if acyclic_relations:
        phrase += f"；其中 {acyclic_relations} 条关系声明为无环（acyclic），可用于依赖环路校验"
    phrase += "。"
    return phrase


def _replace_block(text: str, block: str, inner: str) -> str:
    start = f"<!-- helper:{block}:start -->"
    end = f"<!-- helper:{block}:end -->"
    start_index = text.find(start)
    end_index = text.find(end)
    if start_index == -1 or end_index == -1 or end_index < start_index:
        return text
    before = text[: start_index + len(start)]
    after = text[end_index:]
    middle = ""
    inner_stripped = inner.strip("\n")
    if inner_stripped:
        middle = "\n" + inner_stripped + "\n"
    return before + middle + after


def _strip_helper_markers(text: str) -> str:
    lines = text.splitlines()
    kept: list[str] = []
    for line in lines:
        if "<!-- helper:" in line or line.strip().startswith("# helper:"):
            continue
        kept.append(line)
    return "\n".join(kept)


def _dump_yaml_block(data: dict, header: str | None = None) -> str:
    if not data:
        return ""
    dumped = yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip()
    lines: list[str] = []
    if header:
        lines.append(header)
        lines.append("")
    lines.append("```yaml")
    lines.append(dumped)
    lines.append("```")
    return "\n".join(lines)


def _build_extensions_section(ext_schema: dict | None) -> str:
    if not ext_schema:
        return ""
    types = ext_schema.get("types") or {}
    relations = ext_schema.get("relations") or {}
    constraints = ext_schema.get("constraints") or []
    lines: list[str] = []
    lines.append("## Extensions")
    lines.append("")
    lines.append("This skill has additional schema elements defined in the reference docs.")
    lines.append("")
    if isinstance(types, dict) and types:
        lines.append(
            f"- See `references/schema.md` → Extension types ({len(types)} entries)."
        )
    if isinstance(relations, dict) and relations:
        lines.append(
            f"- See `references/schema.md` → Extension relations ({len(relations)} entries)."
        )
    if isinstance(constraints, list) and constraints:
        lines.append(
            f"- Extension constraints: {len(constraints)} rules (in `references/schema.md`)."
        )
    lines.append("- For example queries and usage patterns, see `references/queries.md`.")
    return "\n".join(lines)


def build_skill_md(
    default_skill_path: Path,
    schema_path: Path | None,
    output_skill_path: Path,
    ext_schema: dict | None,
) -> None:
    text = _read(default_skill_path)
    frontmatter_text, body = _split_frontmatter(text)
    base_meta: dict = {}
    if frontmatter_text:
        loaded = yaml.safe_load(frontmatter_text) or {}
        if isinstance(loaded, dict):
            base_meta = loaded
    name = base_meta.get("name", "ontology")
    base_description = base_meta.get("description", "")
    schema: dict = {}
    if schema_path is not None:
        schema = _load_schema(schema_path)
    extension_phrase = _compute_extension_phrase(schema, ext_schema)
    final_description = (
        base_description + extension_phrase if extension_phrase else base_description
    )
    meta = dict(base_meta)
    meta["name"] = name
    meta["description"] = final_description
    yaml_text = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    out_lines: list[str] = ["---", yaml_text, "---"]
    body_with_extensions = body
    if ext_schema:
        extensions_section = _build_extensions_section(ext_schema)
        body_with_extensions = _replace_block(
            body_with_extensions, "extensions-section", extensions_section
        )
    clean_body = _strip_helper_markers(body_with_extensions)
    result = "\n".join(out_lines) + "\n" + clean_body
    _write(output_skill_path, result)


def build_schema_md(
    default_schema_md_path: Path,
    ext_schema: dict | None,
    output_schema_md_path: Path,
) -> None:
    text = _read(default_schema_md_path)
    if ext_schema:
        types = ext_schema.get("types") or {}
        relations = ext_schema.get("relations") or {}
        constraints = ext_schema.get("constraints") or {}
        types_block = _dump_yaml_block(types, "# Extension types") if types else ""
        relations_block = (
            _dump_yaml_block(relations, "# Extension relations") if relations else ""
        )
        constraints_block = (
            _dump_yaml_block(constraints, "# Extension constraints")
            if constraints
            else ""
        )
        if types_block:
            text = _replace_block(text, "schema-types-ext", types_block)
        if relations_block:
            text = _replace_block(text, "schema-relations-ext", relations_block)
        if constraints_block:
            text = _replace_block(
                text, "schema-constraints-ext", constraints_block
            )
    clean = _strip_helper_markers(text)
    _write(output_schema_md_path, clean)


def build_queries_md(
    default_queries_md_path: Path,
    ext_schema: dict | None,
    output_queries_md_path: Path,
) -> None:
    text = _read(default_queries_md_path)
    queries = []
    if ext_schema:
        q = ext_schema.get("queries")
        if isinstance(q, list):
            queries = q
    if queries:
        lines: list[str] = []
        lines.append("## Extension Queries")
        lines.append("")
        for item in queries:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or item.get("id") or "")
            cli = str(item.get("cli") or "")
            description = str(item.get("description") or "")
            if title:
                lines.append(f"### {title}")
                lines.append("")
            if description and description != "None":
                lines.append(description)
                lines.append("")
            if cli and cli != "None":
                lines.append("```bash")
                lines.append(cli)
                lines.append("```")
                lines.append("")
        block = "\n".join(line for line in lines if line is not None).strip("\n")
        text = _replace_block(text, "queries-extensions", block)
    clean = _strip_helper_markers(text)
    _write(output_queries_md_path, clean)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Helper for generating SKILL.md and reference docs from templates and schema.",
    )
    parser.add_argument(
        "--default-skill",
        type=Path,
        default=Path("references/default/default_skill.md"),
    )
    parser.add_argument(
        "--default-schema-md",
        type=Path,
        default=Path("references/default/default_schema.md"),
    )
    parser.add_argument(
        "--default-queries-md",
        type=Path,
        default=Path("references/default/default_queries.md"),
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path("memory/ontology/schema.yaml"),
    )
    parser.add_argument(
        "--ext-config",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--output-skill",
        type=Path,
        default=Path("SKILL.md"),
    )
    parser.add_argument(
        "--output-schema-md",
        type=Path,
        default=Path("references/schema.md"),
    )
    parser.add_argument(
        "--output-queries-md",
        type=Path,
        default=Path("references/queries.md"),
    )

    args = parser.parse_args()

    ext_schema: dict | None = None
    if args.ext_config is not None:
        ext_schema = _load_schema(args.ext_config)

    build_skill_md(args.default_skill, args.schema, args.output_skill, ext_schema)
    build_schema_md(args.default_schema_md, ext_schema, args.output_schema_md)
    build_queries_md(args.default_queries_md, ext_schema, args.output_queries_md)


if __name__ == "__main__":
    main()
