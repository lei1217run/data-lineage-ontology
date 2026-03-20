# Data Lineage Relations Reference

血缘关系定义与约束模式（已通过 extend-lineage 或 schema-append 激活）。

## 核心血缘关系（Relations）

### 表-字段包含关系

```yaml
has_column:
  from_types: [Table]
  to_types: [Column]
  cardinality: one_to_many
  description: "表拥有哪些字段（正向）"

belongs_to:
  from_types: [Column]
  to_types: [Table]
  cardinality: many_to_one
  description: "字段所属的表（反向，便于查询上游）"
```

### 指标与维度引用


```YAML
references_dimension:
  from_types: [Metric]
  to_types: [Dimension]
  cardinality: many_to_many
  description: "指标引用了哪些分析维度（例如 GMV 指标用了 '城市' 维度）"
```

### 核心血缘依赖（防环路）

```YAML
depends_on:
  from_types: [Metric, Table, Column]
  to_types: [Table, Column, Metric, Dimension]
  cardinality: many_to_many
  acyclic: true
  description: "核心血缘链路（指标依赖表、表依赖其他表、复合指标依赖基础指标）"

derives_from:
  from_types: [Metric]
  to_types: [Metric]
  cardinality: many_to_many
  acyclic: true
  description: "复合指标派生自基础指标（例如 '利润率' derives_from '收入' 和 '成本'）"
```

### 全局血缘约束（自动校验）

```YAML
constraints:
  # 血缘必须无环
  - relation: depends_on
    rule: "acyclic"
    message: "检测到循环血缘依赖！请检查指标/表之间的循环引用"

  - relation: derives_from
    rule: "acyclic"
    message: "复合指标不能形成循环派生关系"

  # 字段必须属于某张表
  - type: Column
    rule: "has_relation(belongs_to, Table)"
    enforcement: warn
    message: "字段必须关联到一张表"
```

