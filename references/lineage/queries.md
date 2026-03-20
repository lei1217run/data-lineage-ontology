# Data Lineage Query Reference

血缘专用查询模式与图遍历示例（与原始 ontology CLI 完全兼容）。

## 基础血缘查询

### 查看单个实体

```bash
python3 scripts/ontology.py get --id m_revenue          # 查看指标
python3 scripts/ontology.py get --id tbl_user_orders    # 查看表
python3 scripts/ontology.py list --type Metric
python3 scripts/ontology.py list --type Table
```

### 血缘遍历查询（核心）

#### 上游血缘（这个指标依赖了什么？）
```bash
# 深度遍历上游（推荐 depth 3-5）
python3 scripts/ontology.py query --start m_revenue --relation depends_on --direction incoming --depth 5

# 只看表级上游
python3 scripts/ontology.py query --start m_revenue --relation depends_on --direction incoming --type Table
```

#### 下游影响（修改这张表会影响哪些指标？）
```bash
python3 scripts/ontology.py query --start tbl_user_orders --relation depends_on --direction outgoing --depth 5
```

#### 完整链路（包含派生指标）
```bash
# 同时遍历 depends_on + derives_from
python3 scripts/ontology.py query --start m_profit --relation depends_on,derives_from --depth 6
```

#### 字段级血缘
```bash
# 这张表的字段被哪些指标使用
python3 scripts/ontology.py related --id tbl_user_orders --rel has_column
# 再对每个 Column 执行 incoming depends_on 查询
```
### 常用血缘场景模板
#### 影响分析（Impact Analysis）
```bash
# 修改这张表会波及哪些下游指标？
python3 scripts/ontology.py query --start tbl_order_items --relation depends_on --direction outgoing --depth 4
```
#### 复合指标拆解
```bash

python3 scripts/ontology.py query --start m_gmv --relation derives_from --direction both --depth 3
```
#### 维度使用情况
```bash
python3 scripts/ontology.py query --start m_monthly_active --relation references_dimension
```
### Python 高级查询（推荐用于复杂分析）
```python
from scripts.ontology import load_graph, get_related

entities, relations = load_graph()

# 查找所有上游表（去重）
def get_upstream_tables(metric_id):
    upstream = get_related(metric_id, "depends_on", direction="incoming")
    tables = [e for e in upstream if e["type"] == "Table"]
    return tables

# 完整血缘路径（DAG 可视化准备）
def get_lineage_path(start_id, max_depth=5):
    # 使用 BFS 或 DFS 实现路径收集（类似原 queries.md 的 find_path）
    ...
```
### 验证与维护
```bash
# 全局检查血缘是否有环 + 类型是否合规
python3 scripts/ontology.py validate

# 只检查血缘关系
python3 scripts/ontology.py validate --focus relations
```