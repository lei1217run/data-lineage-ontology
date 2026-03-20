import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

from storage_backend import (
    BaseStorage,
    Entity,
    Relation,
    FileStorage,
    SQLiteStorage,
    SupabaseStorage,
    SupabaseStorageRest,
)


STORAGE: BaseStorage | None = None


def get_storage() -> BaseStorage:
    global STORAGE
    if STORAGE is not None:
        return STORAGE
    backend = os.getenv("KG_BACKEND", "file")
    db_path = os.getenv("KG_DB_PATH", "memory/ontology/kg.db")
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    if backend == "sqlite":
        STORAGE = SQLiteStorage(db_path)
    elif backend == "supabase" or backend == "supabase_rest":
        if not supabase_url or not supabase_key:
            raise ValueError("请设置 SUPABASE_URL 和 SUPABASE_KEY 环境变量")
        if backend == "supabase":
            STORAGE = SupabaseStorage(supabase_url, supabase_key)
        else:
            STORAGE = SupabaseStorageRest(supabase_url, supabase_key)
    else:
        STORAGE = FileStorage()
    return STORAGE


def resolve_safe_path(
    user_path: str,
    *,
    root: Path | None = None,
    must_exist: bool = False,
    label: str = "path",
) -> Path:
    if not user_path or not user_path.strip():
        raise SystemExit(f"Invalid {label}: empty path")

    safe_root = (root or Path.cwd()).resolve()
    candidate = Path(user_path).expanduser()
    if not candidate.is_absolute():
        candidate = safe_root / candidate

    try:
        resolved = candidate.resolve(strict=False)
    except OSError as exc:
        raise SystemExit(f"Invalid {label}: {exc}") from exc

    try:
        resolved.relative_to(safe_root)
    except ValueError:
        raise SystemExit(
            f"Invalid {label}: must stay within workspace root '{safe_root}'"
        )

    if must_exist and not resolved.exists():
        raise SystemExit(f"Invalid {label}: file not found '{resolved}'")

    return resolved


def generate_id(type_name: str) -> str:
    prefix = type_name.lower()[:4]
    suffix = uuid.uuid4().hex[:8]
    return f"{prefix}_{suffix}"


def entity_to_create_op(entity: Entity, timestamp: datetime) -> dict:
    iso = timestamp.isoformat()
    return {
        "op": "create",
        "entity": {
            "id": entity.id,
            "type": entity.type,
            "properties": entity.properties,
            "created": entity.created or iso,
            "updated": entity.updated or iso,
        },
        "timestamp": iso,
    }


def entity_to_update_op(entity_id: str, properties: dict, timestamp: datetime) -> dict:
    iso = timestamp.isoformat()
    return {
        "op": "update",
        "id": entity_id,
        "properties": properties,
        "timestamp": iso,
    }


def entity_to_delete_op(entity_id: str, timestamp: datetime) -> dict:
    iso = timestamp.isoformat()
    return {
        "op": "delete",
        "id": entity_id,
        "timestamp": iso,
    }


def relation_to_relate_op(relation: Relation, timestamp: datetime) -> dict:
    iso = timestamp.isoformat()
    return {
        "op": "relate",
        "from": relation.from_id,
        "rel": relation.type,
        "to": relation.to_id,
        "properties": relation.properties,
        "timestamp": iso,
    }


def relation_to_unrelate_op(from_id: str, rel_type: str, to_id: str, timestamp: datetime) -> dict:
    iso = timestamp.isoformat()
    return {
        "op": "unrelate",
        "from": from_id,
        "rel": rel_type,
        "to": to_id,
        "timestamp": iso,
    }


def load_graph(path: str) -> tuple[dict, list]:
    storage = get_storage()
    operations = storage.get_operations()
    entities: dict[str, Entity] = {}
    relations: list[Relation] = []

    for record in operations:
        op = record.get("op")
        if op == "create":
            data = record.get("entity", {})
            entity_id = data.get("id")
            if not entity_id:
                continue
            entities[entity_id] = Entity(
                id=entity_id,
                type=data.get("type", ""),
                properties=data.get("properties", {}) or {},
                created=data.get("created"),
                updated=data.get("updated"),
            )
        elif op == "update":
            entity_id = record.get("id")
            if not entity_id or entity_id not in entities:
                continue
            props = record.get("properties", {}) or {}
            entities[entity_id].properties.update(props)
            entities[entity_id].updated = record.get("timestamp", entities[entity_id].updated)
        elif op == "delete":
            entity_id = record.get("id")
            if not entity_id:
                continue
            entities.pop(entity_id, None)
        elif op == "relate":
            relations.append(
                Relation(
                    from_id=record.get("from", ""),
                    type=record.get("rel", ""),
                    to_id=record.get("to", ""),
                    properties=record.get("properties", {}) or {},
                )
            )
        elif op == "unrelate":
            from_id = record.get("from")
            rel_type = record.get("rel")
            to_id = record.get("to")
            relations = [
                r
                for r in relations
                if not (r.from_id == from_id and r.type == rel_type and r.to_id == to_id)
            ]

    entities_view: dict[str, dict] = {
        eid: {
            "id": e.id,
            "type": e.type,
            "properties": e.properties,
            "created": e.created,
            "updated": e.updated,
        }
        for eid, e in entities.items()
    }
    relations_view: list[dict] = [
        {
            "from": r.from_id,
            "rel": r.type,
            "to": r.to_id,
            "properties": r.properties,
        }
        for r in relations
    ]

    return entities_view, relations_view


def append_op(path: str, record: dict):
    storage = get_storage()
    storage.append_operation(record)


def create_entity(type_name: str, properties: dict, graph_path: str, entity_id: str = None) -> dict:
    entity_id = entity_id or generate_id(type_name)
    timestamp = datetime.now(timezone.utc)
    iso = timestamp.isoformat()
    entity = Entity(
        id=entity_id,
        type=type_name,
        properties=properties,
        created=iso,
        updated=iso,
    )
    record = entity_to_create_op(entity, timestamp)
    append_op(graph_path, record)
    return {
        "id": entity.id,
        "type": entity.type,
        "properties": entity.properties,
        "created": entity.created,
        "updated": entity.updated,
    }


def get_entity(entity_id: str, graph_path: str) -> dict | None:
    entities, _ = load_graph(graph_path)
    return entities.get(entity_id)


def query_entities(type_name: str, where: dict, graph_path: str) -> list:
    entities, _ = load_graph(graph_path)
    results = []

    for entity in entities.values():
        if type_name and entity["type"] != type_name:
            continue

        match = True
        for key, value in where.items():
            if entity["properties"].get(key) != value:
                match = False
                break

        if match:
            results.append(entity)

    return results


def list_entities(type_name: str, graph_path: str) -> list:
    entities, _ = load_graph(graph_path)
    if type_name:
        return [e for e in entities.values() if e["type"] == type_name]
    return list(entities.values())


def update_entity(entity_id: str, properties: dict, graph_path: str) -> dict | None:
    entities, _ = load_graph(graph_path)
    if entity_id not in entities:
        return None
    timestamp = datetime.now(timezone.utc)
    record = entity_to_update_op(entity_id, properties, timestamp)
    append_op(graph_path, record)
    entities[entity_id]["properties"].update(properties)
    entities[entity_id]["updated"] = record["timestamp"]
    return entities[entity_id]


def delete_entity(entity_id: str, graph_path: str) -> bool:
    entities, _ = load_graph(graph_path)
    if entity_id not in entities:
        return False
    timestamp = datetime.now(timezone.utc)
    record = entity_to_delete_op(entity_id, timestamp)
    append_op(graph_path, record)
    return True


def create_relation(from_id: str, rel_type: str, to_id: str, properties: dict, graph_path: str):
    timestamp = datetime.now(timezone.utc)
    relation = Relation(
        from_id=from_id,
        type=rel_type,
        to_id=to_id,
        properties=properties,
    )
    record = relation_to_relate_op(relation, timestamp)
    append_op(graph_path, record)
    return record


def delete_relation(from_id: str, rel_type: str, to_id: str, graph_path: str) -> dict:
    timestamp = datetime.now(timezone.utc)
    record = relation_to_unrelate_op(from_id, rel_type, to_id, timestamp)
    append_op(graph_path, record)
    return record


def get_related(entity_id: str, rel_type: str, graph_path: str, direction: str = "outgoing") -> list:
    entities, relations = load_graph(graph_path)
    results = []

    for rel in relations:
        if direction == "outgoing" and rel["from"] == entity_id:
            if not rel_type or rel["rel"] == rel_type:
                if rel["to"] in entities:
                    results.append(
                        {
                            "relation": rel["rel"],
                            "entity": entities[rel["to"]],
                        }
                    )
        elif direction == "incoming" and rel["to"] == entity_id:
            if not rel_type or rel["rel"] == rel_type:
                if rel["from"] in entities:
                    results.append(
                        {
                            "relation": rel["rel"],
                            "entity": entities[rel["from"]],
                        }
                    )
        elif direction == "both":
            if rel["from"] == entity_id or rel["to"] == entity_id:
                if not rel_type or rel["rel"] == rel_type:
                    other_id = rel["to"] if rel["from"] == entity_id else rel["from"]
                    if other_id in entities:
                        results.append(
                            {
                                "relation": rel["rel"],
                                "direction": "outgoing"
                                if rel["from"] == entity_id
                                else "incoming",
                                "entity": entities[other_id],
                            }
                        )

    return results


def validate_graph(graph_path: str, schema_path: str) -> list:
    entities, relations = load_graph(graph_path)
    errors = []

    schema = load_schema(schema_path)

    type_schemas = schema.get("types", {})
    relation_schemas = schema.get("relations", {})
    global_constraints = schema.get("constraints", [])

    for entity_id, entity in entities.items():
        type_name = entity["type"]
        type_schema = type_schemas.get(type_name, {})

        required = type_schema.get("required", [])
        for prop in required:
            if prop not in entity["properties"]:
                errors.append(f"{entity_id}: missing required property '{prop}'")

        forbidden = type_schema.get("forbidden_properties", [])
        for prop in forbidden:
            if prop in entity["properties"]:
                errors.append(f"{entity_id}: contains forbidden property '{prop}'")

        for prop, allowed in type_schema.items():
            if prop.endswith("_enum"):
                field = prop.replace("_enum", "")
                value = entity["properties"].get(field)
                if value and value not in allowed:
                    errors.append(
                        f"{entity_id}: '{field}' must be one of {allowed}, got '{value}'"
                    )

    rel_index: Dict[str, List[Dict[str, Any]]] = {}
    for rel in relations:
        rel_index.setdefault(rel["rel"], []).append(rel)

    for rel_type, rel_schema in relation_schemas.items():
        rels = rel_index.get(rel_type, [])
        from_types = rel_schema.get("from_types", [])
        to_types = rel_schema.get("to_types", [])
        cardinality = rel_schema.get("cardinality")
        acyclic = rel_schema.get("acyclic", False)

        for rel in rels:
            from_entity = entities.get(rel["from"])
            to_entity = entities.get(rel["to"])
            if not from_entity or not to_entity:
                errors.append(
                    f"{rel_type}: relation references missing entity ({rel['from']} -> {rel['to']})"
                )
                continue
            if from_types and from_entity["type"] not in from_types:
                errors.append(
                    f"{rel_type}: from entity {rel['from']} type {from_entity['type']} not in {from_types}"
                )
            if to_types and to_entity["type"] not in to_types:
                errors.append(
                    f"{rel_type}: to entity {rel['to']} type {to_entity['type']} not in {to_types}"
                )

        if cardinality in ("one_to_one", "one_to_many", "many_to_one"):
            from_counts: Dict[str, int] = {}
            to_counts: Dict[str, int] = {}
            for rel in rels:
                from_counts[rel["from"]] = from_counts.get(rel["from"], 0) + 1
                to_counts[rel["to"]] = to_counts.get(rel["to"], 0) + 1

            if cardinality in ("one_to_one", "many_to_one"):
                for from_id, count in from_counts.items():
                    if count > 1:
                        errors.append(
                            f"{rel_type}: from entity {from_id} violates cardinality {cardinality}"
                        )
            if cardinality in ("one_to_one", "one_to_many"):
                for to_id, count in to_counts.items():
                    if count > 1:
                        errors.append(
                            f"{rel_type}: to entity {to_id} violates cardinality {cardinality}"
                        )

        if acyclic:
            graph: Dict[str, List[str]] = {}
            for rel in rels:
                graph.setdefault(rel["from"], []).append(rel["to"])

            state: Dict[str, int] = {}
            found_cycle = False

            for start in graph:
                if state.get(start, 0) != 0:
                    continue
                stack: List[tuple[str, bool]] = [(start, False)]
                while stack and not found_cycle:
                    node, exiting = stack.pop()
                    if exiting:
                        if state.get(node, 0) == 1:
                            state[node] = 2
                        continue
                    node_state = state.get(node, 0)
                    if node_state == 0:
                        state[node] = 1
                        stack.append((node, True))
                        for nxt in graph.get(node, []):
                            nxt_state = state.get(nxt, 0)
                            if nxt_state == 0:
                                stack.append((nxt, False))
                            elif nxt_state == 1:
                                found_cycle = True
                                break
                    elif node_state == 1:
                        found_cycle = True
                if found_cycle:
                    errors.append(f"{rel_type}: cyclic dependency detected")
                    break

    for constraint in global_constraints:
        ctype = constraint.get("type")
        relation = constraint.get("relation")
        rule = (constraint.get("rule") or "").strip().lower()
        if ctype == "Event" and "end" in rule and "start" in rule:
            for entity_id, entity in entities.items():
                if entity["type"] != "Event":
                    continue
                start = entity["properties"].get("start")
                end = entity["properties"].get("end")
                if start and end:
                    try:
                        start_dt = datetime.fromisoformat(start)
                        end_dt = datetime.fromisoformat(end)
                        if end_dt < start_dt:
                            errors.append(f"{entity_id}: end must be >= start")
                    except ValueError:
                        errors.append(
                            f"{entity_id}: invalid datetime format in start/end"
                        )
        if relation and rule == "acyclic":
            continue

    return errors


def load_schema(schema_path: str) -> dict:
    schema: dict = {}
    schema_file = Path(schema_path)
    if schema_file.exists():
        import yaml

        with open(schema_file) as f:
            schema = yaml.safe_load(f) or {}
    return schema


def write_schema(schema_path: str, schema: dict) -> None:
    schema_file = Path(schema_path)
    schema_file.parent.mkdir(parents=True, exist_ok=True)
    import yaml

    with open(schema_file, "w") as f:
        yaml.safe_dump(schema, f, sort_keys=False)


def merge_schema(base: dict, incoming: dict) -> dict:
    for key, value in (incoming or {}).items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            base[key] = merge_schema(base[key], value)
        elif key in base and isinstance(base[key], list) and isinstance(value, list):
            base[key] = base[key] + [v for v in value if v not in base[key]]
        else:
            base[key] = value
    return base


def append_schema(schema_path: str, incoming: dict) -> dict:
    base = load_schema(schema_path)
    merged = merge_schema(base, incoming)
    write_schema(schema_path, merged)
    return merged
