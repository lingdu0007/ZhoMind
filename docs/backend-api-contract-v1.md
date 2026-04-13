# ZhoMind 后端接口契约 v1（OpenAPI 风格简版）

> 目标：作为前后端联调与后端实现基线，优先保证“可执行、可验证、可扩展”。

## 1. 基础约定

- **版本**：`v1`
- **Base URL（推荐）**：`/api/v1`
  - 本地开发可映射到：`http://127.0.0.1:8000/api/v1`
- **认证**：`Authorization: Bearer <access_token>`
- **Content-Type**：
  - 普通接口：`application/json`
  - 上传：`multipart/form-data`
  - 流式：`text/event-stream`
- **时间格式**：ISO 8601（UTC），例如：`2026-04-13T09:23:41Z`
- **ID 规则**：
  - `session_id`、`message_id`、`document_id`、`job_id` 建议使用 UUID v7 或等价可排序唯一 ID
- **错误返回统一结构**（非 2xx）：

```json
{
  "code": "AUTH_INVALID_TOKEN",
  "message": "Invalid or expired token",
  "detail": {},
  "request_id": "req_01J..."
}
```

---

## 2. OpenAPI 风格简版（YAML）

```yaml
openapi: 3.0.3
info:
  title: ZhoMind API
  version: 1.0.0
servers:
  - url: /api/v1
security:
  - bearerAuth: []
components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

  schemas:
    ErrorResponse:
      type: object
      required: [code, message, request_id]
      properties:
        code: { type: string, example: AUTH_INVALID_TOKEN }
        message: { type: string, example: Invalid or expired token }
        detail: { type: object, nullable: true }
        request_id: { type: string, example: req_01JABCDEF }

    PaginationMeta:
      type: object
      required: [page, page_size, total]
      properties:
        page: { type: integer, minimum: 1 }
        page_size: { type: integer, minimum: 1, maximum: 100 }
        total: { type: integer, minimum: 0 }

    AuthTokens:
      type: object
      required: [access_token, token_type, expires_in, username, role]
      properties:
        access_token: { type: string }
        token_type: { type: string, example: Bearer }
        expires_in: { type: integer, example: 3600 }
        refresh_token: { type: string, nullable: true }
        username: { type: string }
        role:
          type: string
          enum: [admin, user]

    CurrentUser:
      type: object
      required: [username, role]
      properties:
        username: { type: string }
        role:
          type: string
          enum: [admin, user]

    RegisterRequest:
      type: object
      required: [username, password]
      properties:
        username: { type: string, minLength: 3, maxLength: 64 }
        password: { type: string, minLength: 8, maxLength: 128 }
        role:
          type: string
          enum: [admin, user]
          default: user
        admin_code:
          type: string
          nullable: true

    LoginRequest:
      type: object
      required: [username, password]
      properties:
        username: { type: string }
        password: { type: string }

    SessionItem:
      type: object
      required: [session_id, updated_at, message_count]
      properties:
        session_id: { type: string }
        title: { type: string, nullable: true }
        updated_at: { type: string, format: date-time }
        message_count: { type: integer, minimum: 0 }

    MessageItem:
      type: object
      required: [message_id, role, content, timestamp]
      properties:
        message_id: { type: string }
        role:
          type: string
          enum: [user, assistant]
        content: { type: string }
        timestamp: { type: string, format: date-time }
        rag_trace:
          type: object
          nullable: true

    ChatRequest:
      type: object
      required: [message]
      properties:
        message: { type: string, minLength: 1, maxLength: 8000 }
        session_id:
          type: string
          nullable: true
          description: |
            可选。为空时由后端创建新会话并返回 session_id。

    ChatResponse:
      type: object
      required: [session_id, message]
      properties:
        session_id: { type: string }
        message:
          type: object
          required: [message_id, role, content, timestamp]
          properties:
            message_id: { type: string }
            role: { type: string, enum: [assistant] }
            content: { type: string }
            timestamp: { type: string, format: date-time }
            rag_trace: { type: object, nullable: true }

    DocumentItem:
      type: object
      required: [document_id, filename, file_type, file_size, status, chunk_strategy, uploaded_at]
      properties:
        document_id: { type: string }
        filename: { type: string }
        file_type: { type: string }
        file_size: { type: integer, minimum: 0 }
        status:
          type: string
          enum: [pending, processing, ready, failed, deleting]
        chunk_strategy:
          type: string
          enum: [padding, general, book, paper, resume, table, qa]
        chunk_count: { type: integer, minimum: 0, nullable: true }
        uploaded_at: { type: string, format: date-time }
        ready_at: { type: string, format: date-time, nullable: true }

    DocumentBuildRequest:
      type: object
      required: [chunk_strategy]
      properties:
        chunk_strategy:
          type: string
          enum: [padding, general, book, paper, resume, table, qa]

    DocumentBatchBuildRequest:
      type: object
      required: [document_ids, chunk_strategy]
      properties:
        document_ids:
          type: array
          minItems: 1
          items: { type: string }
        chunk_strategy:
          type: string
          enum: [padding, general, book, paper, resume, table, qa]

    DocumentBatchDeleteRequest:
      type: object
      required: [document_ids]
      properties:
        document_ids:
          type: array
          minItems: 1
          items: { type: string }

    DocumentBuildJob:
      type: object
      required: [job_id, document_id, status, progress, created_at, updated_at]
      properties:
        job_id: { type: string }
        document_id: { type: string }
        status:
          type: string
          enum: [queued, running, succeeded, failed, canceled]
        stage:
          type: string
          enum: [uploaded, parsing, chunking, embedding, indexing, completed, failed]
        progress: { type: integer, minimum: 0, maximum: 100 }
        message: { type: string, nullable: true }
        error_code: { type: string, nullable: true }
        created_at: { type: string, format: date-time }
        updated_at: { type: string, format: date-time }
        finished_at: { type: string, format: date-time, nullable: true }

    UploadDocumentAcceptedResponse:
      type: object
      required: [job_id, document_id, status, message]
      properties:
        job_id: { type: string }
        document_id: { type: string }
        status: { type: string, enum: [queued] }
        message: { type: string, example: Document accepted for async indexing }

    BatchBuildAcceptedResponse:
      type: object
      required: [items]
      properties:
        items:
          type: array
          items:
            type: object
            required: [document_id, job_id, status]
            properties:
              document_id: { type: string }
              job_id: { type: string }
              status: { type: string, enum: [queued] }

    BatchDeleteResponse:
      type: object
      required: [success_ids, failed_items]
      properties:
        success_ids:
          type: array
          items: { type: string }
        failed_items:
          type: array
          items:
            type: object
            required: [document_id, code, message]
            properties:
              document_id: { type: string }
              code: { type: string }
              message: { type: string }

    DocumentChunk:
      type: object
      required: [chunk_id, document_id, chunk_index, content]
      properties:
        chunk_id: { type: string }
        document_id: { type: string }
        chunk_index: { type: integer, minimum: 0 }
        content: { type: string }
        keywords:
          type: array
          items: { type: string }
        generated_questions:
          type: array
          items: { type: string }
        metadata:
          type: object
          nullable: true

paths:
  /auth/register:
    post:
      tags: [Auth]
      security: []
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/RegisterRequest' }
      responses:
        '201':
          description: Created
          content:
            application/json:
              schema: { $ref: '#/components/schemas/AuthTokens' }
        '400': { description: Bad Request }
        '409': { description: Username exists }

  /auth/login:
    post:
      tags: [Auth]
      security: []
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/LoginRequest' }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/AuthTokens' }
        '401': { description: Invalid credentials }

  /auth/me:
    get:
      tags: [Auth]
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/CurrentUser' }
        '401': { description: Unauthorized }

  /sessions:
    get:
      tags: [Sessions]
      parameters:
        - in: query
          name: page
          schema: { type: integer, default: 1, minimum: 1 }
        - in: query
          name: page_size
          schema: { type: integer, default: 20, minimum: 1, maximum: 100 }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
                required: [items, pagination]
                properties:
                  items:
                    type: array
                    items: { $ref: '#/components/schemas/SessionItem' }
                  pagination:
                    $ref: '#/components/schemas/PaginationMeta'

  /sessions/{session_id}:
    get:
      tags: [Sessions]
      parameters:
        - in: path
          name: session_id
          required: true
          schema: { type: string }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
                required: [session_id, items]
                properties:
                  session_id: { type: string }
                  items:
                    type: array
                    items: { $ref: '#/components/schemas/MessageItem' }
        '404': { description: Not Found }
    delete:
      tags: [Sessions]
      parameters:
        - in: path
          name: session_id
          required: true
          schema: { type: string }
      responses:
        '204': { description: No Content }
        '404': { description: Not Found }

  /chat:
    post:
      tags: [Chat]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/ChatRequest' }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ChatResponse' }

  /chat/stream:
    post:
      tags: [Chat]
      summary: SSE 流式回答
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/ChatRequest' }
      responses:
        '200':
          description: text/event-stream
          content:
            text/event-stream:
              schema:
                type: string
                example: |
                  event: meta
                  data: {"request_id":"req_01","session_id":"ses_01","message_id":"msg_01"}

                  event: content
                  data: {"delta":"你好"}

                  event: rag_step
                  data: {"step":"retrieve","detail":{}}

                  event: trace
                  data: {"trace":{}}

                  event: done
                  data: [DONE]

  /documents:
    get:
      tags: [Documents]
      parameters:
        - in: query
          name: page
          schema: { type: integer, default: 1, minimum: 1 }
        - in: query
          name: page_size
          schema: { type: integer, default: 20, minimum: 1, maximum: 100 }
        - in: query
          name: keyword
          schema: { type: string }
        - in: query
          name: sort
          schema: { type: string, example: uploaded_at:desc }
        - in: query
          name: status
          schema: { type: string, enum: [pending, processing, ready, failed, deleting] }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
                required: [items, pagination]
                properties:
                  items:
                    type: array
                    items: { $ref: '#/components/schemas/DocumentItem' }
                  pagination:
                    $ref: '#/components/schemas/PaginationMeta'
        '403': { description: Forbidden }

  /documents/upload:
    post:
      tags: [Documents]
      summary: 上传文件并创建异步构建任务
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              required: [file]
              properties:
                file:
                  type: string
                  format: binary
      responses:
        '202':
          description: Accepted
          content:
            application/json:
              schema: { $ref: '#/components/schemas/UploadDocumentAcceptedResponse' }
        '403': { description: Forbidden }

  /documents/{document_id}/build:
    post:
      tags: [Documents]
      summary: 单文件触发分块/索引构建
      parameters:
        - in: path
          name: document_id
          required: true
          schema: { type: string }
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/DocumentBuildRequest' }
      responses:
        '202':
          description: Accepted
          content:
            application/json:
              schema: { $ref: '#/components/schemas/UploadDocumentAcceptedResponse' }
        '403': { description: Forbidden }
        '404': { description: Not Found }

  /documents/batch-build:
    post:
      tags: [Documents]
      summary: 批量触发分块/索引构建
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/DocumentBatchBuildRequest' }
      responses:
        '202':
          description: Accepted
          content:
            application/json:
              schema: { $ref: '#/components/schemas/BatchBuildAcceptedResponse' }
        '403': { description: Forbidden }

  /documents/batch-delete:
    post:
      tags: [Documents]
      summary: 批量删除文档
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/DocumentBatchDeleteRequest' }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/BatchDeleteResponse' }
        '403': { description: Forbidden }

  /documents/{document_id}/chunks:
    get:
      tags: [Documents]
      summary: 查询文档分块结果
      parameters:
        - in: path
          name: document_id
          required: true
          schema: { type: string }
        - in: query
          name: page
          schema: { type: integer, default: 1, minimum: 1 }
        - in: query
          name: page_size
          schema: { type: integer, default: 20, minimum: 1, maximum: 100 }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
                required: [items, pagination]
                properties:
                  items:
                    type: array
                    items: { $ref: '#/components/schemas/DocumentChunk' }
                  pagination:
                    $ref: '#/components/schemas/PaginationMeta'
        '403': { description: Forbidden }
        '404': { description: Not Found }
        '409': { description: Chunk result not ready }

  /documents/jobs:
    get:
      tags: [Documents]
      summary: 查询文档构建任务列表（轮询入口）
      parameters:
        - in: query
          name: page
          schema: { type: integer, default: 1, minimum: 1 }
        - in: query
          name: page_size
          schema: { type: integer, default: 20, minimum: 1, maximum: 100 }
        - in: query
          name: status
          schema: { type: string, enum: [queued, running, succeeded, failed, canceled] }
        - in: query
          name: document_id
          schema: { type: string }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
                required: [items, pagination]
                properties:
                  items:
                    type: array
                    items: { $ref: '#/components/schemas/DocumentBuildJob' }
                  pagination:
                    $ref: '#/components/schemas/PaginationMeta'
        '403': { description: Forbidden }

  /documents/jobs/{job_id}:
    get:
      tags: [Documents]
      summary: 查询单个构建任务状态（轮询入口）
      parameters:
        - in: path
          name: job_id
          required: true
          schema: { type: string }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/DocumentBuildJob' }
        '403': { description: Forbidden }
        '404': { description: Not Found }

  /documents/jobs/{job_id}/stream:
    get:
      tags: [Documents]
      summary: SSE 订阅单个构建任务进度
      parameters:
        - in: path
          name: job_id
          required: true
          schema: { type: string }
      responses:
        '200':
          description: text/event-stream
          content:
            text/event-stream:
              schema:
                type: string
                example: |
                  event: progress
                  data: {"job_id":"job_01","status":"running","stage":"parsing","progress":20}

                  event: progress
                  data: {"job_id":"job_01","status":"running","stage":"embedding","progress":70}

                  event: done
                  data: {"job_id":"job_01","status":"succeeded","stage":"completed","progress":100}
        '403': { description: Forbidden }
        '404': { description: Not Found }

  /documents/jobs/{job_id}/cancel:
    post:
      tags: [Documents]
      summary: 取消构建任务（仅 queued/running）
      parameters:
        - in: path
          name: job_id
          required: true
          schema: { type: string }
      responses:
        '202': { description: Accepted }
        '403': { description: Forbidden }
        '404': { description: Not Found }
        '409': { description: Job already finished }

  /documents/{filename}:
    delete:
      tags: [Documents]
      parameters:
        - in: path
          name: filename
          required: true
          schema: { type: string }
      responses:
        '204': { description: No Content }
        '403': { description: Forbidden }
        '404': { description: Not Found }
```

---

## 3. SSE 事件协议 v1（强约束）

### 3.1 Chat SSE（`/chat/stream`）

服务端仅允许以下 `event`：

1. `meta`（可选，建议第一条）
2. `content`（可多次）
3. `rag_step`（可多次）
4. `trace`（最多一次）
5. `error`（最多一次，出现后应尽快结束）
6. `done`（必须且仅一次）

### 3.2 Document Job SSE（`/documents/jobs/{job_id}/stream`）

服务端仅允许以下 `event`：

1. `progress`（可多次）
2. `error`（最多一次）
3. `done`（必须且仅一次）

`progress` 的 `data` 至少包含：`job_id/status/stage/progress`。

---

## 4. 文档异步构建流水线语义（v1）

### 4.1 状态与阶段

- `status`：`queued -> running -> succeeded|failed|canceled`
- `stage`：`uploaded -> parsing -> chunking -> embedding -> indexing -> completed|failed`

### 4.2 上传与可检索一致性

- 上传成功返回 `202 + job_id`，表示“任务已受理”。
- 仅当任务 `status=succeeded` 且文档 `status=ready` 时，该文档可参与 RAG 检索。
- 任务失败时，文档状态置为 `failed`，并保留错误信息供前端展示与重试。

### 4.3 分块策略与结果查询

- 分块策略采用枚举：`padding/general/book/paper/resume/table/qa`。
- 可通过单文件构建与批量构建接口提交 `chunk_strategy`。
- 分块结果通过 `/documents/{document_id}/chunks` 分页查询，返回 `content/keywords/generated_questions/metadata`。

### 4.4 幂等与去重（建议）

- 建议基于文件 hash（如 sha256）做去重策略：
  - 完全相同且已 ready：可返回已有 `document_id` + 新 `job_id(复用)` 或直接提示重复。
  - 相同文件但需重建：通过显式参数触发重新构建。

---

## 5. 状态码与错误码建议

- `200` 查询/聊天成功
- `201` 注册创建成功
- `202` 异步任务已受理（文档上传、构建、取消任务）
- `204` 删除成功
- `400` 参数错误
- `401` 未认证或 token 无效
- `403` 无权限（如非 admin 调文档接口）
- `404` 资源不存在
- `409` 冲突（用户名重复、任务状态冲突、结果未就绪等）
- `422` 结构化校验失败
- `500` 服务端异常

建议错误码最小集：

- `AUTH_INVALID_TOKEN`
- `AUTH_BAD_CREDENTIALS`
- `AUTH_FORBIDDEN`
- `VALIDATION_ERROR`
- `RESOURCE_NOT_FOUND`
- `RESOURCE_CONFLICT`
- `CHAT_STREAM_INTERRUPTED`
- `RAG_UPSTREAM_ERROR`
- `DOC_JOB_NOT_FOUND`
- `DOC_JOB_STATE_CONFLICT`
- `DOC_INVALID_CHUNK_STRATEGY`
- `DOC_CHUNK_RESULT_NOT_READY`
- `DOC_BATCH_PARTIAL_FAILED`
- `DOC_PARSE_ERROR`
- `DOC_EMBEDDING_ERROR`
- `INTERNAL_ERROR`

---

## 6. 与当前前端对齐说明

1. 前端已有 `auth/sessions/chat/documents` 调用路径，以上契约已全覆盖。
2. 列表返回统一 `items`，分页统一 `pagination`，避免继续写 `data/items/documents` 兼容分支。
3. `session_id` 策略：
   - 前端传空 => 后端创建并回传
   - 前端传已有值 => 继续该会话（不存在返回 `404`）
4. 文档上传改为异步：
   - 前端上传后拿 `job_id`
   - 通过 `GET /documents/jobs/{job_id}` 轮询，或 `.../stream` 订阅进度
5. 文件管理增强：
   - 单文件分块：`POST /documents/{document_id}/build`
   - 批量分块：`POST /documents/batch-build`
   - 批量删除：`POST /documents/batch-delete`
   - 分块结果：`GET /documents/{document_id}/chunks`

---

## 7. 后续 v1.1 可扩展项（预留）

- `POST /auth/refresh` 刷新 token
- `GET/PUT /config/*`（模型、检索、存储、安全配置）
- Job 队列优先级与并发配额控制
- SSE `heartbeat` 心跳事件（长连接保活）
