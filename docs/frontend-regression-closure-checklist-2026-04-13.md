# 前端联调收口验证清单（2026-04-13）

## 收口约束

1. 冻结 API 字段命名、状态枚举、错误结构，不做协议变更。
2. 仅允许修复回归缺陷，不做功能扩展。
3. 每处改动必须附测试证据与复现步骤。
4. QA 跑全量契约回归后再给最终 go/no-go。

## 改动与测试映射

### 1) `frontend/src/api/adapters.js`

- 改动：新增 `buildDocument` / `batchBuildDocuments` / `batchDeleteDocuments` / `getDocumentChunks`，沿用既有 jobs list/get/cancel。
- 协议检查点：
  - 请求字段保持契约：`chunk_strategy`、`document_ids`、`page/page_size`
  - 返回字段保持契约：`job_id`、`document_id`、`status`、`items`、`pagination`、`failed_items`
- 测试证据：
  - 后端契约回归 `tests/test_documents_api_contract.py` 通过（见下方命令输出摘要）。
- 复现步骤：
  1. 在上传页对单文档点击“执行分块”，确认任务区出现新 `job_id`。
  2. 选择多文档点击“批量分块”，确认每个 `document_id` 都返回任务并进入轮询。
  3. 点击“查看分块”并翻页，确认请求携带 `page/page_size` 且列表分页变化。

### 2) `frontend/src/api/http.js`

- 改动：错误对象标准化，透传 `status`、`code`、`detail`、`request_id`，保留 `401` 清理登录态。
- 协议检查点：
  - 非 2xx 错误结构对齐：`code/message/detail/request_id`
- 测试证据：
  - 后端契约回归 `tests/test_documents_api_contract.py::test_contract_auth_forbidden_on_documents_apis` 通过。
- 复现步骤：
  1. 使用非管理员账号访问上传页并触发文档接口。
  2. 确认前端提示“仅管理员可操作文档管理功能”。
  3. 使用失效 token 触发请求，确认本地登录态被清理并降级到未登录提示。

### 3) `frontend/src/components/UploadPanel.vue`

- 改动：上传成功后 `clearFiles()`，继续向父组件回传 `job_id/document_id/filename`。
- 协议检查点：
  - 上传返回仍基于 `202` 受理语义，仅消费 `job_id/document_id/status/message`。
- 测试证据：
  - 前端构建通过，上传流程在手工回归步骤中覆盖。
- 复现步骤：
  1. 选择文件并点击上传。
  2. 成功提示显示“已入队”。
  3. 上传组件文件列表被清空。
  4. 任务区新增 `job_id`，随后进入轮询。

### 4) `frontend/src/pages/UploadPage.vue`

- 改动：任务轮询闭环、状态映射、单文件分块、批量分块/删除、分块结果弹窗分页、任务取消。
- 协议检查点：
  - 任务状态枚举：`queued/running/succeeded/failed/canceled`
  - 阶段枚举：`uploaded/parsing/chunking/embedding/indexing/completed/failed`
  - 文档状态枚举：`pending/processing/ready/failed/deleting`
  - 分块结果字段：`content/keywords/generated_questions/metadata`
- 测试证据：
  - 后端任务/契约回归均通过：
    - `tests/test_documents_api_contract.py`
    - `tests/test_documents_jobs_integration.py`
- 复现步骤：
  1. 上传文件后观察任务从 `queued` 进入 `running`，最终到终态并停止轮询。
  2. 文档行点击“执行分块”，确认返回新任务并可追踪终态。
  3. 批量分块后确认多个任务入队；批量删除后确认成功项消失、失败项展示明细。
  4. 仅 `ready` 文档可打开分块弹窗；分页切换正常展示 `content/keywords/generated_questions/metadata`。
  5. 非 `ready` 打开分块时显示“文档未就绪”；`DOC_CHUNK_RESULT_NOT_READY` 返回友好提示。

## 自动化测试执行记录

### 前端

```bash
cd frontend
npm run build
```

- 结果：通过（exit code 0）

### 后端（全量契约回归）

```bash
cd backend
uv run pytest
```

- 结果：通过（15 passed, 0 failed）
- 覆盖：
  - `tests/test_documents_api_contract.py`（契约）
  - `tests/test_documents_jobs_integration.py`（任务流水线）
  - `tests/test_db_integration.py`（约束一致性）
  - `tests/test_foundation.py`（基础健康）

## QA Gate（最终发布前）

- 必须由 QA 复跑：
  1. 上传 -> 任务终态可视化
  2. 单文件/批量分块
  3. 批量删除（含部分失败场景）
  4. 分块弹窗分页与字段展示
  5. 401/403/409/failed 场景
- QA 未签字前，结论保持 `pending`，不出最终 go/no-go。
