import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any


class BaseStorage(ABC):
    @abstractmethod
    def append_operation(self, op: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_operations(self) -> List[Dict[str, Any]]:
        pass


@dataclass
class Entity:
    id: str
    type: str
    properties: Dict[str, Any]
    created: str | None = None
    updated: str | None = None


@dataclass
class Relation:
    from_id: str
    type: str
    to_id: str
    properties: Dict[str, Any]


class FileStorage(BaseStorage):  # 原生实现，完美兼容旧代码
    def __init__(self, graph_path: str = "memory/ontology/graph.jsonl"):
        os.makedirs(os.path.dirname(graph_path), exist_ok=True)
        self.graph_path = graph_path

    def append_operation(self, op: Dict):
        with open(self.graph_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(op, ensure_ascii=False) + "\n")

    def get_operations(self) -> List[Dict]:
        if not os.path.exists(self.graph_path):
            return []
        with open(self.graph_path, "r", encoding="utf-8") as f:
            return [json.loads(line.strip()) for line in f if line.strip()]


class SQLiteStorage(BaseStorage):  # Mac mini 本地首选，零依赖
    def __init__(self, db_path: str = "memory/ontology/kg.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.conn = None
        self._init_db()

    def _init_db(self):
        import sqlite3
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                op_json TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def append_operation(self, op: Dict):
        import sqlite3
        self.conn.execute("INSERT INTO operations (op_json) VALUES (?)",
                          (json.dumps(op, ensure_ascii=False),))
        self.conn.commit()

    def get_operations(self) -> List[Dict]:
        cur = self.conn.execute("SELECT op_json FROM operations ORDER BY id")
        return [json.loads(row[0]) for row in cur.fetchall()]


class SupabaseStorage(BaseStorage):  # 外部 BaaS（仅此 backend 需要依赖）
    import httpx
    def __init__(self, url: str, key: str, table: str = "operations"):
        from supabase import create_client
        self.client = create_client(url, key)
        self.table = table
        self._ensure_table()  # 可选：首次运行自动建表

    def _ensure_table(self):
        # Supabase 上手动建一次即可，SQL 见下方
        """
        CREATE TABLE operations (
            id BIGSERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            op_json JSONB NOT NULL
        );
        """
        pass

    def append_operation(self, op: Dict):
        self.client.table(self.table).insert({
            "op_json": json.dumps(op, ensure_ascii=False)
        }).execute()

    def get_operations(self) -> List[Dict]:
        resp = self.client.table(self.table)\
            .select("op_json")\
            .order("id")\
            .execute()
        return [json.loads(row["op_json"]) for row in resp.data]

class SupabaseStorageRest(BaseStorage):
    """使用纯 httpx 调用 Supabase REST API（零 supabase SDK 依赖）"""
    def __init__(self, url: str, key: str, table: str = "operations"):
        self.base_url = url.rstrip("/")
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
        }
        # 使用 Client 实现连接复用 + 统一超时
        self.client = httpx.Client(
            base_url=f"{self.base_url}/rest/v1",
            headers=self.headers,
            timeout=10.0
        )
        self.table = table
        # _ensure_table 仍然手动（推荐首次运行前在 Supabase SQL Editor 执行一次）

    def _ensure_table(self):
        # 首次使用前请手动执行下面 SQL（只需一次）
        # CREATE TABLE operations (
        #     id BIGSERIAL PRIMARY KEY,
        #     created_at TIMESTAMPTZ DEFAULT NOW(),
        #     op_json JSONB NOT NULL
        # );
        pass

    def append_operation(self, op: Dict[str, Any]) -> None:
        """POST /rest/v1/operations （op_json 直接传 dict，利用 JSONB）"""
        data = {"op_json": op}
        resp = self.client.post(
            f"/{self.table}",
            json=data,
            headers={"Prefer": "return=minimal"}   # 不返回响应体，节省流量
        )
        resp.raise_for_status()   # 自动抛出 HTTP 错误，便于调试

    def get_operations(self) -> List[Dict[str, Any]]:
        """GET /rest/v1/operations?select=op_json&order=id.asc （返回已解析的 dict）"""
        resp = self.client.get(
            f"/{self.table}?select=op_json&order=id.asc&limit=100000"  # 足够大多数 ontology 使用
        )
        resp.raise_for_status()
        data = resp.json()
        return [row["op_json"] for row in data]
