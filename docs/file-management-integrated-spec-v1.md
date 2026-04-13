# ZhoMind 文件管理整合方案 v1

> 整合来源：
> - `docs/backend-api-contract-v1.md`
> - `docs/backend-dev-task-list-v1.md`
> - `docs/frontend-integration-min-change-checklist-v1.md`
> - 本轮补充的文件管理需求（分块策略、分块结果、批量操作）

目标：形成一份可直接用于排期、开发、联调、验收的统一规范，聚焦“文件管理 = 文档资产 + 异步构建任务 + 分块结果可视化”。

---

## 1. 统一目标与范围

### 1.1 业务目标

将文件管理从“上传/删除文件”升级为“知识库构建管线管理”：

1. 上传文档
2. 选择分块策略
3. 异步执行分块与索引构建
4. 轮询/订阅任务进度
5. 查看分块结果
6. 单个/批量删除

### 1.2 v1 范围（必须）

- 文档列表 + 状态可见
- 异步上传返回 `job_id`
- 任务轮询（SSE 订阅可选）
- 单文件分块策略字段落地
- 分块结果查看接口
- 批量分块、批量删除接口（前端 UI 可先最小化）

### 1.3 v1.1 范围（可延后）

- 任务优先级与并发配额
- 失败重试与重建索引
- 任务 SSE 全量落地
- 细粒度审计日志

---

## 2. 统一领域模型

### 2.1 Document（文档）

- `document_id`
- `filename`
- `file_type`
- `file_size`
- `status`: `pending | processing | ready | failed | deleting`
- `chunk_strategy`: `padding | general | book | paper | resume | table | qa`
- `chunk_count`
- `uploaded_at`
- `ready_at`

### 2.2 DocumentBuildJob（构建任务）

- `job_id`
- `document_id`
- `status`: `queued | running | succeeded | failed | canceled`
- `stage`: `uploaded | parsing | chunking | embedding | indexing | completed | failed`
- `progress` (0-100)
- `message`
- `error_code`
- `created_at`
- `updated_at`
- `finished_at`

### 2.3 DocumentChunk（分块结果）

- `chunk_id`
- `document_id`
- `chunk_index`
- `content`
- `keywords` (array)
- `generated_questions` (array)
- `metadata` (object, 如 `chapter`, `page`, `sheet_name`)

---

## 3. 接口整合（在现有契约上补齐）

> 基础前缀：`/api/v1`

### 3.1 已确定接口（保留）

- `GET /documents`
- `POST /documents/upload`（`202 + job_id`）
- `DELETE /documents/{filename}`
- `GET /documents/jobs`
- `GET /documents/jobs/{job_id}`
- `GET /documents/jobs/{job_id}/stream`（可选）
- `POST /documents/jobs/{job_id}/cancel`

### 3.2 新增接口（满足文件管理需求）

#### A. 单文件触发分块/重建
- `POST /documents/{document_id}/build`
- 请求：`{ chunk_strategy }`
- 响应：`202 + { job_id, document_id, status: queued }`

#### B. 批量分块
- `POST /documents/batch-build`
- 请求：
  ```json
  {
    "document_ids": ["doc_1", "doc_2"],
    "chunk_strategy": "general"
  }
  ```
- 响应：`202 + { items: [{ document_id, job_id, status }] }`

#### C. 批量删除
- `POST /documents/batch-delete`
- 请求：`{ document_ids: [...] }`
- 响应：`200 + { success_ids: [], failed_items: [{ document_id, code, message }] }`

#### D. 分块结果查询
- `GET /documents/{document_id}/chunks?page=1&page_size=20`
- 响应：`{ items: DocumentChunk[], pagination }`

#### E. 分块策略字典（可选）
- `GET /documents/chunk-strategies`
- 响应：策略列表 + 描述 + 推荐场景（给“分块方式说明”弹窗用）

---

## 4. 状态机统一约定

### 4.1 文档状态

- `pending`：已上传，尚未进入有效构建
- `processing`：存在运行中任务
- `ready`：构建成功，可检索
- `failed`：最后一次构建失败
- `deleting`：删除中

### 4.2 任务状态

- `queued -> running -> succeeded|failed|canceled`

### 4.3 一致性规则

1. 上传成功只代表“受理成功”，不代表可检索。
2. 仅当 `job.succeeded` 且 `document.ready` 才允许参与 RAG 检索。
3. 删除文档时，运行中任务需“阻止删除”或“级联取消”二选一并固定实现（推荐级联取消+审计日志）。

---

## 5. 前端最小改造与扩展映射

## 5.1 已完成/应保持（P0）

- `adapters.js`：已接 `job` 查询接口
- `UploadPanel.vue`：上传后回传 `job_id`
- `UploadPage.vue`：已具备任务轮询闭环

### 5.2 继续最小改造（P1）

1. 文档表增加字段展示：
   - `file_size`
   - `status`（中文 tag）
   - `chunk_strategy`
2. 任务区增强：
   - 显示 `message/error_code`
3. 分块结果弹窗：
   - 调用 `GET /documents/{document_id}/chunks`
   - 展示 `content/keywords/generated_questions/metadata`
4. 多选批量操作：
   - 批量分块
   - 批量删除

### 5.3 前端状态管理建议

- 保持当前页面本地 `ref`（不强制新建 store）
- 若后续加入 SSE 与多页复用，再抽 `documentJobsStore`

---

## 6. 后端任务清单对齐（整合版）

### M1-M2（不变）

- Auth / Sessions / Chat / Chat SSE

### M3（重点增强）

在原 `T9~T15` 基础上补充：

- **T19**：实现 `chunk_strategy` 字段入库与校验
- **T20**：实现 `POST /documents/{id}/build`（单文件重建）
- **T21**：实现 `POST /documents/batch-build`
- **T22**：实现 `POST /documents/batch-delete`
- **T23**：实现 `GET /documents/{id}/chunks`（分页）
- **T24**：策略字典接口或后端常量配置输出

### M4（质量）

- 针对批量接口与分块结果查询补自动化测试
- 错误码补齐：
  - `DOC_INVALID_CHUNK_STRATEGY`
  - `DOC_CHUNK_RESULT_NOT_READY`
  - `DOC_BATCH_PARTIAL_FAILED`

---

## 7. 统一验收标准（联调/测试共用）

### 7.1 P0 验收

- 上传后 1 秒内拿到 `job_id`
- 轮询可观察至少 3 段状态变化
- `succeeded` 后文档变为 `ready`
- 页面离开后无轮询泄漏

### 7.2 文件管理增强验收（本次新增）

- 可为单文件选择并提交分块策略
- 批量分块返回每个文档独立 `job_id`
- 可查看分块结果（分页）
- 批量删除返回部分失败明细
- 失败任务可见可读错误原因

### 7.3 一致性验收

- `GET /documents` 与 `GET /documents/jobs` 状态一致
- `ready` 文档可被检索，`failed` 不可参与检索

---

## 8. 推荐落地顺序（两周增量版）

### Week 1（联调闭环）

1. 固化现有 P0 轮询方案
2. 后端补 `chunk_strategy` 字段与校验
3. 前端加状态/tag 与策略下拉（单文件）
4. 后端补 `GET /documents/{id}/chunks`

### Week 2（功能补全）

1. 批量分块接口 + 前端多选入口
2. 批量删除接口 + 前端多选删除
3. 分块方式说明（策略字典接口或前端静态配置）
4. 回归测试与文档收敛

---

## 9. 文档收敛建议

为避免信息分散，建议后续维护策略：

1. `backend-api-contract-v1.md`：仅保留“接口与协议真相源（SSOT）”
2. `backend-dev-task-list-v1.md`：仅保留“任务排期与DoD”
3. `frontend-integration-min-change-checklist-v1.md`：仅保留“前端改造事项”
4. 本文 `file-management-integrated-spec-v1.md`：作为跨端对齐总览（产品+技术整合）

> 若后续进入 v1.1，可直接复制本文件为 `file-management-integrated-spec-v1.1.md` 迭代。