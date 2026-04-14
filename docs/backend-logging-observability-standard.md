# ZhoMind Backend 日志与可观测性标准（v1）

## 1. 结构化日志统一字段

所有后端日志统一输出 JSON，以下字段固定存在（无值时使用 `"-"` 或 `null`）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `timestamp` | string | UTC 时间，ISO 8601（如 `2026-04-14T01:23:45.123Z`） |
| `level` | string | `DEBUG` / `INFO` / `WARN` / `ERROR` |
| `service` | string | 服务名（来自 `Settings.app_name`） |
| `env` | string | 运行环境（来自 `Settings.env`） |
| `request_id` | string | 入口中间件注入并贯穿链路 |
| `user_id` | string | 当前用户标识（认证后注入） |
| `session_id` | string | 会话标识（聊天/会话接口场景） |
| `job_id` | string | 文档任务标识（documents/jobs/worker） |
| `document_id` | string | 文档标识 |
| `route` | string | 请求路径或 worker 路由（如 `worker:document.build`） |
| `method` | string | HTTP 方法或 `QUEUE` |
| `status_code` | int/null | HTTP 状态码（worker 场景可为空） |
| `latency_ms` | float/null | 请求耗时（毫秒） |
| `error_code` | string | 业务错误码（与 API 错误结构 `code` 对齐） |

补充字段：
- `event`：事件名（例如 `http.request.complete`）。
- `logger`：logger 名称。
- `details`：扩展上下文（自动脱敏）。
- `exception`：异常栈（仅异常场景）。

## 2. 日志级别策略

- `DEBUG`：开发诊断信息（不影响主流程的细粒度状态）。
- `INFO`：正常业务路径关键里程碑（请求完成、任务完成、状态迁移）。
- `WARN`：可恢复或预期失败（鉴权失败、资源不存在、取消任务、4xx）。
- `ERROR`：不可恢复错误（5xx、未处理异常、任务失败）。

HTTP 入口默认映射：
- `2xx-3xx` -> `INFO`
- `4xx` -> `WARN`
- `5xx` -> `ERROR`

## 3. request_id 与链路追踪

### 3.1 入口注入
- `RequestIdMiddleware` 从 `x-request-id` 读取；缺失时自动生成 `req_<12hex>`。
- 响应头回传同一 `x-request-id`。

### 3.2 跨层传递
- API -> Service：通过 `ContextVar` 自动继承。
- Service -> Queue：入队 payload 附带 `request_id`。
- Queue -> Worker：执行前恢复 `request_id` 到上下文。

### 3.3 错误场景要求
- 错误日志必须包含：`request_id` + `error_code` + 核心上下文 ID（`session_id/job_id/document_id` 至少一个）。
- API 错误响应结构维持契约：`code/message/detail/request_id`（未改契约）。

## 4. 关键事件埋点清单（按模块）

### auth
- `auth.register.succeeded` / `auth.register.failed`
- `auth.login.succeeded` / `auth.login.failed`
- `auth.me.succeeded`
- `auth.token.parse_failed`

### sessions
- `sessions.list.succeeded`
- `sessions.get.succeeded` / `sessions.get.failed`
- `sessions.delete.succeeded` / `sessions.delete.failed`

### chat / chat-stream
- `chat.request.started` / `chat.request.completed`
- `chat.stream.started`
- `chat.stream.first_packet`
- `chat.stream.completed`
- `chat.stream.interrupted`
- `chat.stream.failed`

### documents / jobs / worker
- `documents.upload.accepted`
- `documents.build.accepted`
- `documents.batch_build.completed` / `documents.batch_build.item_failed`
- `documents.batch_delete.completed`
- `documents.jobs.list.succeeded`
- `documents.jobs.get.succeeded`
- `documents.jobs.stream.started` / `first_packet` / `error_packet` / `completed`
- `documents.jobs.cancel.accepted`
- `documents.job.enqueued`
- `documents.job.stage_transition`
- `documents.job.cancel_requested` / `documents.job.canceled`
- `documents.job.succeeded`
- `documents.job.failed`
- `worker.document_job.started` / `worker.document_job.completed` / `worker.document_job.failed`
- `queue.task.enqueued` / `started` / `completed` / `failed`

## 5. 脱敏策略

### 5.1 禁止落盘
- 密码、token、secret、api key 原文。
- 完整用户输入正文（聊天 message 等）。

### 5.2 自动脱敏规则
- 头部与扩展字段统一过 `redact_mapping`。
- `Authorization` 保留 scheme，token 掩码（如 `Bearer ***cdef`）。
- key 命中 `password/token/secret/api_key/apikey` 的字段统一 `***redacted***`。
- 用户输入使用摘要：`{length, sha256}`。

## 6. 排障检索模板

> 以下示例假设日志为单行 JSON，文件为 `backend.log`。

按 `request_id`：

```bash
rg '"request_id":"req_xxx"' backend.log
```

按 `job_id` 看全阶段：

```bash
rg '"job_id":"job_xxx"' backend.log | rg 'documents.job|worker.document_job|queue.task'
```

按 `document_id` 看处理与删除：

```bash
rg '"document_id":"doc_xxx"' backend.log
```

按错误码聚合：

```bash
rg '"error_code":"' backend.log | rg 'AUTH_|DOC_|INTERNAL_'
```

## 7. 自检脚本

- 文件：`backend/scripts/log_selfcheck.py`
- 目的：
  - 通过模拟 API/worker 关键事件校验结构化字段齐全；
  - 校验关键事件存在；
  - 校验 `Authorization` 与用户输入已脱敏；
  - 校验失败日志含 `error_code` 与 `request_id`。

运行方式：

```bash
cd backend
python scripts/log_selfcheck.py
```

回归测试：

```bash
cd backend
uv run pytest -q tests/test_observability_pipeline.py
```
