## Data Lineage Extension（内置扩展）

本 skill 已支持**数据元数据血缘链路**作为内置扩展。

**支持实体**：Table、Column、Metric、Dimension\
**核心血缘关系**（带 acyclic 防环）：

- `has_column`、`depends_on`、`derives_from`、`references_dimension`

**激活方式**（只需运行一次）：

```bash
python3 scripts/ontology.py extend-lineage
```

