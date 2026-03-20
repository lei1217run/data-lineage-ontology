#!/usr/bin/env python3
"""
Ontology graph operations: create, query, relate, validate.

Usage:
    python ontology.py create --type Person --props '{"name":"Alice"}'
    python ontology.py get --id p_001
    python ontology.py query --type Task --where '{"status":"open"}'
    python ontology.py relate --from proj_001 --rel has_task --to task_001
    python ontology.py related --id proj_001 --rel has_task
    python ontology.py list --type Person
    python ontology.py delete --id p_001
    python ontology.py validate
"""

import argparse
import json
from pathlib import Path

from helper import build_queries_md, build_schema_md, build_skill_md
from ontology_core import (
    append_schema,
    create_entity,
    create_relation,
    delete_entity,
    delete_relation,
    get_entity,
    get_related,
    list_entities,
    query_entities,
    resolve_safe_path,
    update_entity,
    validate_graph,
)

DEFAULT_GRAPH_PATH = "memory/ontology/graph.jsonl"
DEFAULT_SCHEMA_PATH = "memory/ontology/schema.yaml"



def main():
    parser = argparse.ArgumentParser(description="Ontology graph operations")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Create
    create_p = subparsers.add_parser("create", help="Create entity")
    create_p.add_argument("--type", "-t", required=True, help="Entity type")
    create_p.add_argument("--props", "-p", default="{}", help="Properties JSON")
    create_p.add_argument("--id", help="Entity ID (auto-generated if not provided)")
    create_p.add_argument("--graph", "-g", default=DEFAULT_GRAPH_PATH)
    
    # Get
    get_p = subparsers.add_parser("get", help="Get entity by ID")
    get_p.add_argument("--id", required=True, help="Entity ID")
    get_p.add_argument("--graph", "-g", default=DEFAULT_GRAPH_PATH)
    
    # Query
    query_p = subparsers.add_parser("query", help="Query entities")
    query_p.add_argument("--type", "-t", help="Entity type")
    query_p.add_argument("--where", "-w", default="{}", help="Filter JSON")
    query_p.add_argument("--graph", "-g", default=DEFAULT_GRAPH_PATH)
    
    # List
    list_p = subparsers.add_parser("list", help="List entities")
    list_p.add_argument("--type", "-t", help="Entity type")
    list_p.add_argument("--graph", "-g", default=DEFAULT_GRAPH_PATH)
    
    # Update
    update_p = subparsers.add_parser("update", help="Update entity")
    update_p.add_argument("--id", required=True, help="Entity ID")
    update_p.add_argument("--props", "-p", required=True, help="Properties JSON")
    update_p.add_argument("--graph", "-g", default=DEFAULT_GRAPH_PATH)
    
    # Delete
    delete_p = subparsers.add_parser("delete", help="Delete entity")
    delete_p.add_argument("--id", required=True, help="Entity ID")
    delete_p.add_argument("--graph", "-g", default=DEFAULT_GRAPH_PATH)
    
    # Relate
    relate_p = subparsers.add_parser("relate", help="Create relation")
    relate_p.add_argument("--from", dest="from_id", required=True, help="From entity ID")
    relate_p.add_argument("--rel", "-r", required=True, help="Relation type")
    relate_p.add_argument("--to", dest="to_id", required=True, help="To entity ID")
    relate_p.add_argument("--props", "-p", default="{}", help="Relation properties JSON")
    relate_p.add_argument("--graph", "-g", default=DEFAULT_GRAPH_PATH)

    # Unrelate
    unrelate_p = subparsers.add_parser("unrelate", help="Remove relation")
    unrelate_p.add_argument("--from", dest="from_id", required=True, help="From entity ID")
    unrelate_p.add_argument("--rel", "-r", required=True, help="Relation type")
    unrelate_p.add_argument("--to", dest="to_id", required=True, help="To entity ID")
    unrelate_p.add_argument("--graph", "-g", default=DEFAULT_GRAPH_PATH)
    
    # Related
    related_p = subparsers.add_parser("related", help="Get related entities")
    related_p.add_argument("--id", required=True, help="Entity ID")
    related_p.add_argument("--rel", "-r", help="Relation type filter")
    related_p.add_argument("--dir", "-d", choices=["outgoing", "incoming", "both"], default="outgoing")
    related_p.add_argument("--graph", "-g", default=DEFAULT_GRAPH_PATH)
    
    validate_p = subparsers.add_parser("validate", help="Validate graph")
    validate_p.add_argument("--graph", "-g", default=DEFAULT_GRAPH_PATH)
    validate_p.add_argument("--schema", "-s", default=DEFAULT_SCHEMA_PATH)

    schema_p = subparsers.add_parser("schema-append", help="Append/merge schema fragment")
    schema_p.add_argument("--schema", "-s", default=DEFAULT_SCHEMA_PATH)
    schema_p.add_argument("--data", "-d", help="Schema fragment as JSON")
    schema_p.add_argument("--file", "-f", help="Schema fragment file (YAML or JSON)")

    extend_p = subparsers.add_parser("extend-lineage", help="Apply schema extension and regenerate docs")
    extend_p.add_argument("--schema", "-s", default=DEFAULT_SCHEMA_PATH)
    extend_p.add_argument("--config", "-c", required=True, help="Extension config file (YAML or JSON)")

    args = parser.parse_args()
    workspace_root = Path.cwd().resolve()

    if hasattr(args, "graph"):
        args.graph = str(
            resolve_safe_path(args.graph, root=workspace_root, label="graph path")
        )
    if hasattr(args, "schema"):
        args.schema = str(
            resolve_safe_path(args.schema, root=workspace_root, label="schema path")
        )
    if hasattr(args, "file") and args.file:
        args.file = str(
            resolve_safe_path(
                args.file, root=workspace_root, must_exist=True, label="schema file"
            )
        )
    if hasattr(args, "config") and args.config:
        args.config = str(
            resolve_safe_path(
                args.config,
                root=workspace_root,
                must_exist=True,
                label="extension config",
            )
        )

    def handle_create(ns):
        props = json.loads(ns.props)
        entity = create_entity(ns.type, props, ns.graph, ns.id)
        print(json.dumps(entity, indent=2))

    def handle_get(ns):
        entity = get_entity(ns.id, ns.graph)
        if entity:
            print(json.dumps(entity, indent=2))
        else:
            print(f"Entity not found: {ns.id}")

    def handle_query(ns):
        where = json.loads(ns.where)
        results = query_entities(ns.type, where, ns.graph)
        print(json.dumps(results, indent=2))

    def handle_list(ns):
        results = list_entities(ns.type, ns.graph)
        print(json.dumps(results, indent=2))

    def handle_update(ns):
        props = json.loads(ns.props)
        entity = update_entity(ns.id, props, ns.graph)
        if entity:
            print(json.dumps(entity, indent=2))
        else:
            print(f"Entity not found: {ns.id}")

    def handle_delete(ns):
        if delete_entity(ns.id, ns.graph):
            print(f"Deleted: {ns.id}")
        else:
            print(f"Entity not found: {ns.id}")

    def handle_relate(ns):
        props = json.loads(ns.props)
        rel = create_relation(ns.from_id, ns.rel, ns.to_id, props, ns.graph)
        print(json.dumps(rel, indent=2))

    def handle_unrelate(ns):
        rel = delete_relation(ns.from_id, ns.rel, ns.to_id, ns.graph)
        print(json.dumps(rel, indent=2))

    def handle_related(ns):
        results = get_related(ns.id, ns.rel, ns.graph, ns.dir)
        print(json.dumps(results, indent=2))

    def handle_validate(ns):
        errors = validate_graph(ns.graph, ns.schema)
        if errors:
            print("Validation errors:")
            for err in errors:
                print(f"  - {err}")
        else:
            print("Graph is valid.")

    def handle_schema_append(ns):
        if not ns.data and not ns.file:
            raise SystemExit("schema-append requires --data or --file")

        incoming = {}
        if ns.data:
            incoming = json.loads(ns.data)
        else:
            path = Path(ns.file)
            if path.suffix.lower() == ".json":
                with open(path) as f:
                    incoming = json.load(f)
            else:
                import yaml

                with open(path) as f:
                    incoming = yaml.safe_load(f) or {}

        merged = append_schema(ns.schema, incoming)
        print(json.dumps(merged, indent=2))

    def handle_extend_lineage(ns):
        path = Path(ns.config)
        if path.suffix.lower() == ".json":
            with open(path) as f:
                ext_config = json.load(f)
        else:
            import yaml

            with open(path) as f:
                ext_config = yaml.safe_load(f) or {}
        if not isinstance(ext_config, dict):
            raise SystemExit("extension config must be an object")
        merged = append_schema(ns.schema, ext_config)
        default_skill = Path("references/default/default_skill.md")
        default_schema_md = Path("references/default/default_schema.md")
        default_queries_md = Path("references/default/default_queries.md")
        build_skill_md(
            default_skill,
            Path(ns.schema),
            Path("SKILL.md"),
            ext_config,
        )
        build_schema_md(
            default_schema_md,
            ext_config,
            Path("references/schema.md"),
        )
        build_queries_md(
            default_queries_md,
            ext_config,
            Path("references/queries.md"),
        )
        print(json.dumps({"schema": merged, "config": ns.config}, indent=2))

    handlers = {
        "create": handle_create,
        "get": handle_get,
        "query": handle_query,
        "list": handle_list,
        "update": handle_update,
        "delete": handle_delete,
        "relate": handle_relate,
        "unrelate": handle_unrelate,
        "related": handle_related,
        "validate": handle_validate,
        "schema-append": handle_schema_append,
        "extend-lineage": handle_extend_lineage,
    }

    handler = handlers.get(args.command)
    if not handler:
        raise SystemExit(f"Unknown command: {args.command}")
    handler(args)


if __name__ == "__main__":
    main()
