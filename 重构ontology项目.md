重构 ontology 项目方案
=====================

1. 背景说明
-----------

- ontology 是一个 Skill 项目，原项目地址：`https://clawhub.ai/oswalpalash/ontology`。  
- 原有能力虽然可以扩展，但在代码结构和持久化设计上存在明显优化空间，本项目的目标是在保持原有能力和使用方式的前提下，对其进行系统性重构与增强。

2. 原始项目现状
---------------

- 原始 ontology 项目只有一个 `ontology.py` 脚本，整体是脚本式写法，可维护性和可测试性较弱，不够「Pythonic」。  
- 原始实现没有数据库写入操作，所有数据仅通过本地文件（如 `graph.jsonl`）进行存储。  
- Skill 逻辑（Prompt + 解析）与存储细节强耦合，难以替换为其他存储后端。  

3. 重构总体方向
---------------

本次重构的核心目标是「分层解耦 + 可插拔存储」，在不改变 Skill 对外能力的前提下，完成以下结构化改造：

- 引入清晰的领域模型（Entity / Relation）。  
- 抽象统一的存储接口（BaseStorage）。  
- 提供多种具体存储实现（文件、本地 SQLite、远程 Supabase）。  
- Skill 逻辑层只依赖抽象的 Storage 接口，而不直接依赖具体存储实现。  
- 提供 helper 工具，对 `SKILL.md` 与 reference 中的 md 文档做统一的扩展和维护。

4. 分层设计
-----------

4.1 Domain Layer（领域层）

- 定义标准的实体与关系数据结构，明确最小字段集合与约束：  
  - `Entity`：`{ id, type, properties, created, updated }`  
  - `Relation`：`{ from_id, type, to_id, properties }`  
- 领域层只负责：  
  - 统一数据结构定义；  
  - 基础的合法性校验（例如必填字段、类型约束）。  
- 领域层不感知具体的存储细节（文件 / SQLite / Supabase）。  

4.2 Storage Interface（抽象层）

- 当前已采用「operation log」形式的存储抽象，而不是直接以实体为中心的 CRUD 接口：  
  - 定义 `BaseStorage` 基类，仅约定两个操作：  
    - `append_operation(op: dict)`：追加一条标准化的操作记录；  
    - `get_operations() -> list[dict]`：按时间顺序读取所有操作记录，用于回放构建当前图谱状态。  
  - 领域层的 `Entity` / `Relation` 通过适配函数与 operation log 互相转换，上层逻辑无需关心底层是文件、SQLite 还是 Supabase。  
- 此设计已经在 `storage_backend.py` 与 `ontology_core.py` 中落地实现，后续演进的重点是：  
  - 在文档中补充更清晰的错误模型与返回约定（例如如何处理失败的 append、何时重试）；  
  - 对不同后端的行为差异进行说明，而不是修改 `BaseStorage` 的抽象本身。  

4.3 Infrastructure Layer（基础设施层）

- 该层专门处理与外部世界的交互，包括本地文件、本地数据库以及远程服务。  

**SQLiteDriver**  
- 使用 Python 标准库 `sqlite3` 操作本地 `.db` 文件。  
- 负责：  
  - 建表（Entity/Relation 等）；  
  - 基于 `BaseStorage` 规范实现 CRUD 与查询能力；  
  - 简单事务处理与错误捕获。  

**SupabaseDriver**  
- 使用 `httpx` 或 `requests` 调用远程 REST API。  
- 负责：  
  - 将领域层的 `Entity` / `Relation` 转换为 Supabase 需要的请求参数与 JSON 结构；  
  - 处理网络异常与重试策略（在合理范围内）；  
  - 封装认证、基础路径、HTTP 错误处理等细节。  

**FileStorage**  
- 负责本地文件存储逻辑，包括兼容原始项目的 `graph.jsonl` 行式存储方式。  
- 在 `storage_backend.py` 中提供实现，复用或迁移原始 `ontology.py` 中的文件读写逻辑，并在此基础上进行规范化与抽象化。  
- 作为默认且最简单的存储后端，便于本地开发与调试。  

4.4 Skill Logic（逻辑层）

- 保持与原 `oswalpalash/ontology` 项目中 Prompt 与解析逻辑的一致性：  
  - 尽量不修改已有 Prompt 设计；  
  - 解析部分仅做必要的封装与结构化处理。  
- 将原本直接写入 `graph.jsonl` 的逻辑，改为调用抽象的 `Storage` 接口：  
  - Skill 逻辑层只需要依赖 `BaseStorage`；  
  - 实际使用的存储实现由配置或初始化参数决定（File / SQLite / Supabase）。  
- 确保 Skill 调用方不感知底层存储变化，从而方便扩展与迁移。  

5. helper 工具设计
------------------

- 目标：提供一个专门的工具模块，用于维护和扩展 `SKILL.md` 与 reference 中的各类 md 文档内容。  
- 初衷：希望在原有 ontology 能力之上，进一步兼容「数据血缘链路」这一类图谱能力，不只是做 schema 结构层面的扩展，还要在 Skill 的 meta 描述层面做到同步扩展。  
- helper 的本质作用不是「写死」这些扩展，而是提供一套「按需、动态兼容」的机制：  
  - 例如，在项目初始化时就挂载了血缘链路相关的 schema 扩展，那么生成的 `SKILL.md` 中，应该在 meta 区域清晰呈现该 Skill 具备血缘相关能力；  
  - 这种呈现不能只是简单把说明文字堆到 `SKILL.md` 文档末尾，否则大模型需要读完整个文档才能感知到新能力，缺乏结构化和可发现性；  
  - helper 需要面向 Skill 的 meta 结构进行「结构化更新」，确保新增能力可以被上游模型「按需加载」而不是「被动阅读」。  
- 在 `references` 目录中，已经增加了与血缘链路相关的 md 文档以及血缘链路基础 schema 的 YAML 示例：  
  - 当前这些示例（尤其是 YAML）是写死的；  
  - YAML 文件本质上应该是用户可自定义、可扩展的 schema 源；  
  - 当用户修改了该 YAML 并重新初始化项目时：  
    - 对应的 `queries.md` 示例与 `relations.md` 内容，也应该基于 YAML 的最新定义自动生成或更新；  
    - 最终整合进 `SKILL.md` 源文件的内容，亦应与 YAML 中的 schema 保持一致，避免文档与实际能力脱节。  
- 因此，helper 的核心能力包括但不限于：  
  - 根据领域模型与存储设计，自动生成 / 更新部分文档片段；  
  - 将 lineage 等扩展 schema 作为「输入」，驱动 `SKILL.md` / `queries.md` / `relations.md` 等文档的同步更新；  
  - 统一维护 Skill 能力说明、输入输出格式、示例与 meta 描述等内容；  
  - 为后续扩展其他图谱能力或领域对象时，提供「配置（YAML）→ 文档（md）→ Skill meta」的一致性自动化能力。  
- helper 工具不直接参与核心业务逻辑，仅作为文档与元信息维护的辅助模块，但对整个 Skill 的可扩展性与可发现性至关重要。  

6. 现有进度与待完善点
----------------------

- 存储抽象与基础后端实现  
  - 当前仓库中已具备完整可用的 `storage_backend.py` 与配套的 `ontology_core.py` 实现：  
    - `BaseStorage` 以 operation log 为中心，仅暴露 `append_operation` / `get_operations` 两个方法；  
    - 提供 `FileStorage` / `SQLiteStorage` / `SupabaseStorage` / `SupabaseStorageRest` 四类后端，均遵守统一的 op 协议；  
    - 通过 `get_storage()` + 全局 `STORAGE` 注入方式，已经与 CLI 层打通，实现端到端的数据流。  
  - 后续需要完善的方向主要包括：  
    - 增强各后端的错误处理与类型校验策略，明确失败重试与降级行为；  
    - 为 SQLite / Supabase 系列补充索引、事务与限流相关的工程实践说明；  
    - 补充从旧版 `graph.jsonl` 迁移到新后端的推荐路径与注意事项。  
- 原始代码中的 `load_graph` 与 `append_op` 已经做过一次重构，以兼容当前「分层架构 + 抽象存储」的设计，但仍然不够完善：  
  - 现阶段它们可以在一定程度上与新的 Storage 结构协同工作；  
  - 但在错误处理、类型约束、防止历史数据格式与新结构不一致等方面，还有进一步打磨空间；  
  - 后续会在完善具体存储后端的同时，迭代这两个入口函数，使其真正成为「领域层 / 存储层友好」的适配层。  
- 文档层面，目前已：  
  - 明确了重构的整体方向与分层设计；  
  - 描述了 helper 在 lineage 等扩展场景下的核心职责与目标。  
- 代码层面，storage 抽象与基础驱动已进入可用阶段，helper 与 Skill meta 更新机制也有初始实现：  
  - 接下来将在整体设计确认后，逐步推进各后端的工程化增强、helper 逻辑的细化以及更多扩展示例的落地。  
- 本文档仍然作为重构方向与设计原则的说明，会随着实现演进持续更新，以保持与实际代码状态的一致性。
