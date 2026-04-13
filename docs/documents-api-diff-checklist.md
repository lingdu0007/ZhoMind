# Documents API + DB 改造差异清单（可执行版）

基准：`docs/backend-api-contract-v1.md`（SSOT）

> 适用范围：`./backend` 目录下 API / Infrastructure / Repository / Migration / Tests。
> 
> 强约束：
> 1. 不修改契约，不新增契约外对外字段。
> 2. 字段名与状态枚举零漂移（不新增、不重命名、不造别名）。
> 3. 列表统一 `items + pagination`，错误统一契约结构。
> 4. 全链路可追踪（`request_id/job_id/document_id`）。

---

## A. 契约对齐（路径、状态码、返回结构）

### A1. 路由路径对齐

1. 现状存在 `/document_jobs*` 路径；契约要求统一为 `/documents/jobs*`。
2. 执行项：
   - 统一保留 `GET /documents/jobs`、`GET /documents/jobs/{job_id}`、`GET /documents/jobs/{job_id}/stream`、`POST /documents/jobs/{job_id}/cancel`。
   - 若存在旧路径，仅允许内部兼容跳转（如保留期），对外文档与主路由必须以契约路径为准。

### A2. 状态码对齐

1. `POST /documents/upload`：统一为 `202`。
2. `POST /documents/{document_id}/build`：统一为 `202`。
3. `POST /documents/batch-build`：统一为 `202`。
4. `POST /documents/jobs/{job_id}/cancel`：统一为 `202`。
5. 执行项：逐接口核对并修正返回码，禁止继续返回占位 `200`。

### A3. 响应结构对齐

1. 列表接口统一：
   - 顶层必须是 `items` 与 `pagination`。
2. 错误接口统一：
   - `code/message/detail/request_id`。
3. 文档相关接口按契约模型返回：
   - 上传/构建返回 `{job_id, document_id, status, message}`。
   - 批量构建返回 `{items:[{document_id,job_id,status}]}`。
   - chunks 返回 `DocumentChunk` 字段集合。
4. 执行项：禁止 `data/list/documents` 等历史兼容键继续外露。

---

## B. 数据模型对齐（5 表字段映射 + 枚举来源）

### B1. 首批表范围

- `users`
- `sessions`
- `messages`
- `documents`
- `document_jobs`

### B2. 字段命名原则

1. 契约可见字段：命名与契约完全一致。
2. 内部实现字段：仅允许最小必要字段（如主键、外键、审计时间），且需在本清单显式标注“内部字段”。
3. 禁止行为：
   - 契约字段重命名（例如 `doc_id` 替代 `document_id`）。
   - 同义别名并存。

### B3. 枚举零漂移策略

1. `document_jobs.status` 仅允许：
   - `queued|running|succeeded|failed|canceled`
2. `document_jobs.stage` 仅允许：
   - `uploaded|parsing|chunking|embedding|indexing|completed|failed`
3. `documents.status` 仅允许：
   - `pending|processing|ready|failed|deleting`
4. `documents.chunk_strategy` 仅允许：
   - `padding|general|book|paper|resume|table|qa`
5. 执行项：
   - 枚举定义统一来源（优先 `domain/enums.py`），API Schema / ORM / Repository / Worker 禁止各自复制一套字符串常量。

### B4. 字段映射交付物（先行）

在代码改动前，先输出“5 表字段映射清单”（含类型、nullable、default、索引、外键、是否契约字段）。

---

## C. 基础设施对齐（Async Session 管理与依赖注入）

### C1. 连接管理改造目标

1. 以 `src/infrastructure/db/connection.py` 为入口接入真实 ORM（建议 SQLAlchemy async）。
2. `create_database(url)` 工厂接口保持不变。
3. 执行项：
   - 提供 engine 生命周期管理（connect/disconnect）。
   - 提供 `async_sessionmaker` 与统一会话获取入口。

### C2. API / Worker 使用边界

1. API、队列 worker 通过 repository 调用，不直接拼 ORM 语句。
2. 会话边界统一：
   - 每次请求/任务使用独立 session；
   - 写操作明确提交与回滚策略。

### C3. 可追踪性要求

1. 关键日志必须携带：`request_id/job_id/document_id`（按场景可为空但键不可缺）。
2. 日志落点至少覆盖：
   - API 入站 + 出站（含状态码）；
   - Job 状态流转（queued→running→...）；
   - Repository 关键写操作（create/update）。

---

## D. 迁移对齐（Alembic baseline 与执行入口）

### D1. 迁移入口改造

1. `src/infrastructure/db/migrations.py` 对接 Alembic 执行入口。
2. 执行项：
   - 提供统一 `run_migrations()` 调用路径；
   - 支持 `upgrade head`（至少本地/测试可执行）。

### D2. 初版 migration（baseline）

1. 生成初版 migration，创建 B 节定义的 5 张表及必要索引/外键/约束。
2. 禁止手改数据库绕过 migration。
3. 若字段新增为内部实现字段，必须在 migration 注释中说明用途。

### D3. 迁移验证

1. 空库执行 baseline 成功。
2. 重复执行具备幂等预期（由 Alembic revision 管理）。
3. 回滚（至少一版）可执行。

---

## E. 访问层对齐（Repository 最小接口与调用边界）

### E1. 最小接口范围

首批 repository 能力：
1. 会话读写（创建、读取、分页列表、删除）。
2. 消息写入（至少支持 user/assistant 消息落库）。
3. 文档任务查询（列表、单任务、状态更新读取）。

### E2. 接口稳定性约束

1. 对上游（API/Worker）暴露稳定方法签名，不泄露 ORM 模型细节。
2. 返回字段命名与契约一致（尤其 `*_id`、`status`、`stage`、时间字段）。
3. 执行项：为并发调用准备最小原子更新语义（任务状态更新时防止脏写）。

---

## F. 验证对齐（集成测试与通过准则）

### F1. 测试范围

1. 建表测试：迁移后 5 张表存在。
2. CRUD 测试：
   - users/sessions/messages/documents/document_jobs 的最小读写路径。
3. 状态一致性测试：
   - `document_jobs.status/stage` 合法流转；
   - 非法枚举值被拒绝（零漂移保护）。
4. 并发/一致性基础测试：
   - 至少覆盖任务状态更新与读取一致。

### F2. 通过准则（Done Definition）

1. 全部新增集成测试通过。
2. 契约字段与枚举零漂移（抽样核对 API Schema + ORM + DB migration）。
3. 关键日志可串联 `request_id/job_id/document_id`。
4. 不引入新的列表/错误结构分叉。

---

## 本次执行顺序（强制）

1. 先完成本差异清单确认（本文件）。
2. 再输出“5 表字段映射清单”（逐字段）。
3. 再实施代码改造：connection → models → migrations → repository → tests。
4. 最后做契约回归核对与日志串联验证。

---

## 第二步交付物：5 表字段映射清单（v1）

> 说明：
> - `契约字段` = 在 `docs/backend-api-contract-v1.md` 中直接出现并对外可见。
> - `内部字段` = 为落库/关联/审计最小必需，不对外扩散到 API 响应。
> - 时间字段统一 `ISO 8601(UTC)` 语义，在 DB 中用 `TIMESTAMP WITH TIME ZONE`（或等价）。

### 1) users

| 字段名 | 类型（建议） | Nullable | Default | 索引/约束 | 外键 | 字段属性 |
|---|---|---|---|---|---|---|
| id | BIGINT/UUID | 否 | 自增/生成 | PK | - | 内部字段 |
| username | VARCHAR(64) | 否 | - | UNIQUE INDEX | - | 契约字段（AuthTokens/CurrentUser/Register/Login） |
| password_hash | VARCHAR(255) | 否 | - | - | - | 内部字段 |
| role | VARCHAR(16) | 否 | `user` | CHECK in (`admin`,`user`) | - | 契约字段 |
| created_at | TIMESTAMPTZ | 否 | `now()` | INDEX（可选） | - | 内部字段 |
| updated_at | TIMESTAMPTZ | 否 | `now()` | - | - | 内部字段 |

### 2) sessions

| 字段名 | 类型（建议） | Nullable | Default | 索引/约束 | 外键 | 字段属性 |
|---|---|---|---|---|---|---|
| id | BIGINT/UUID | 否 | 自增/生成 | PK | - | 内部字段 |
| session_id | VARCHAR(64) | 否 | 生成 | UNIQUE INDEX | - | 契约字段 |
| user_id | BIGINT/UUID | 否 | - | INDEX | `users.id` | 内部字段 |
| title | VARCHAR(255) | 是 | NULL | - | - | 契约字段 |
| updated_at | TIMESTAMPTZ | 否 | `now()` | INDEX | - | 契约字段 |
| message_count | INTEGER | 否 | `0` | CHECK >= 0 | - | 契约字段 |
| created_at | TIMESTAMPTZ | 否 | `now()` | INDEX（可选） | - | 内部字段 |

### 3) messages

| 字段名 | 类型（建议） | Nullable | Default | 索引/约束 | 外键 | 字段属性 |
|---|---|---|---|---|---|---|
| id | BIGINT/UUID | 否 | 自增/生成 | PK | - | 内部字段 |
| message_id | VARCHAR(64) | 否 | 生成 | UNIQUE INDEX | - | 契约字段 |
| session_id | VARCHAR(64) | 否 | - | INDEX | `sessions.session_id` | 契约字段（关联） |
| role | VARCHAR(16) | 否 | - | CHECK in (`user`,`assistant`) | - | 契约字段 |
| content | TEXT | 否 | - | - | - | 契约字段 |
| timestamp | TIMESTAMPTZ | 否 | `now()` | INDEX | - | 契约字段 |
| rag_trace | JSONB | 是 | NULL | - | - | 契约字段（nullable） |

### 4) documents

| 字段名 | 类型（建议） | Nullable | Default | 索引/约束 | 外键 | 字段属性 |
|---|---|---|---|---|---|---|
| id | BIGINT/UUID | 否 | 自增/生成 | PK | - | 内部字段 |
| document_id | VARCHAR(64) | 否 | 生成 | UNIQUE INDEX | - | 契约字段 |
| filename | VARCHAR(512) | 否 | - | INDEX（按检索需要） | - | 契约字段 |
| file_type | VARCHAR(128) | 否 | - | - | - | 契约字段 |
| file_size | BIGINT | 否 | - | CHECK >= 0 | - | 契约字段 |
| status | VARCHAR(16) | 否 | `pending` | CHECK in (`pending`,`processing`,`ready`,`failed`,`deleting`) + INDEX | - | 契约字段 |
| chunk_strategy | VARCHAR(16) | 否 | `general` | CHECK in (`padding`,`general`,`book`,`paper`,`resume`,`table`,`qa`) | - | 契约字段 |
| chunk_count | INTEGER | 是 | NULL | CHECK >= 0 | - | 契约字段（nullable） |
| uploaded_at | TIMESTAMPTZ | 否 | `now()` | INDEX | - | 契约字段 |
| ready_at | TIMESTAMPTZ | 是 | NULL | - | - | 契约字段（nullable） |
| created_at | TIMESTAMPTZ | 否 | `now()` | INDEX（可选） | - | 内部字段 |
| updated_at | TIMESTAMPTZ | 否 | `now()` | - | - | 内部字段 |

### 5) document_jobs

| 字段名 | 类型（建议） | Nullable | Default | 索引/约束 | 外键 | 字段属性 |
|---|---|---|---|---|---|---|
| id | BIGINT/UUID | 否 | 自增/生成 | PK | - | 内部字段 |
| job_id | VARCHAR(64) | 否 | 生成 | UNIQUE INDEX | - | 契约字段 |
| document_id | VARCHAR(64) | 否 | - | INDEX | `documents.document_id` | 契约字段 |
| status | VARCHAR(16) | 否 | `queued` | CHECK in (`queued`,`running`,`succeeded`,`failed`,`canceled`) + INDEX | - | 契约字段 |
| stage | VARCHAR(16) | 否 | `uploaded` | CHECK in (`uploaded`,`parsing`,`chunking`,`embedding`,`indexing`,`completed`,`failed`) | - | 契约字段 |
| progress | INTEGER | 否 | `0` | CHECK between 0 and 100 | - | 契约字段 |
| message | TEXT | 是 | NULL | - | - | 契约字段（nullable） |
| error_code | VARCHAR(64) | 是 | NULL | INDEX（可选） | - | 契约字段（nullable） |
| created_at | TIMESTAMPTZ | 否 | `now()` | INDEX | - | 契约字段 |
| updated_at | TIMESTAMPTZ | 否 | `now()` | INDEX | - | 契约字段 |
| finished_at | TIMESTAMPTZ | 是 | NULL | INDEX（可选） | - | 契约字段（nullable） |

---

## 第二步实现约束补充（用于第三步编码）

1. ORM 层字段名与表字段名保持完全一致，不做别名映射。
2. Repository 输出 DTO 字段名与契约字段名一致。
3. 枚举值统一引用 `domain/enums.py`（若现有模块路径差异，先做无语义变更的归并）。
4. 任何新增内部字段必须在 migration 注释中标明用途。
