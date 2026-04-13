# ZhoMind Backend API 摘要

## 1. 基础信息
- **Base URL**：`http://127.0.0.1:8000`
- **认证方式**：OAuth2 Password（token 来自 `/auth/login`），前端以 `Authorization: Bearer <token>` 发送。
- **响应格式**：JSON；流式接口使用 `text/event-stream`。

## 2. 认证

| Endpoint | Method | Body | 响应 |
| --- | --- | --- | --- |
| `/auth/register` | POST | `{ username, password, role?, admin_code? }` | `AuthResponse { access_token, username, role }` |
| `/auth/login` | POST | `{ username, password }` | `AuthResponse` |
| `/auth/me` | GET | `Authorization` 头 | `CurrentUserResponse { username, role }` |

注意：注册管理员需提供正确 `admin_code`。token 过期需重新登录。

## 3. 会话 / 聊天

| Endpoint | Method | 描述 |
| --- | --- | --- |
| `/sessions` | GET | 返回当前用户的会话列表 `SessionListResponse { sessions[] }` |
| `/sessions/{session_id}` | GET | 返回指定会话消息 `SessionMessagesResponse { messages[] }` |
| `/sessions/{session_id}` | DELETE | 删除会话 |
| `/chat` | POST | 同步回答 `{ message, session_id? } -> ChatResponse { response, rag_trace? }` |
| `/chat/stream` | POST | **SSE** 流式回答 |

### `/chat/stream` 事件类型
- `{"type":"content","content":"token"}` — LLM 字符串增量。
- `{"type":"rag_step","step": "..."}`
- `{"type":"trace","trace": {...}}`
- `{"type":"error","error":"msg"}` — 发生错误。
- `[DONE]` — 终止标识。

事件以 `data: <json>\n\n` 推送，必须禁用代理缓冲（已设置 `X-Accel-Buffering: no`）。

## 4. 文档管理

| Endpoint | Method | 权限 | 描述 |
| --- | --- | --- | --- |
| `/documents` | GET | admin | `DocumentListResponse { documents[] }` |
| `/documents/upload` | POST (multipart) | admin | 表单字段 `file`，返回 `DocumentUploadResponse { filename, chunks_processed, message }` |
| `/documents/{filename}` | DELETE | admin | 删除向量记录 |

`DocumentInfo` 包含 `filename`, `file_type`, `chunk_count`, `uploaded_at?`。

## 5. 数据结构摘要
- **SessionInfo**：`{ session_id, updated_at, message_count }`
- **MessageInfo**：`{ type("user"/"assistant"), content, timestamp, rag_trace? }`
- **RagTrace**：详尽 RAG 步骤（tool、query、rerank、retrieved_chunks 等）。

## 6. 部署假设
- FastAPI 监听 `127.0.0.1:8000`。
- Nginx 反代 `/api/` 至 FastAPI `/api/`，并允许 `Access-Control-Allow-Origin: *` 以兼容静态前端。
- SSE 代理层需 `proxy_buffering off`，`proxy_set_header Connection ""`。

## 7. 开发注意事项
- 认证：前端登录后需缓存 token，与 `role` 控制 UI。
- SSE：Abort 时服务器会捕获 `GeneratorExit` 取消后台任务，客户端应调用 `AbortController.abort()`。
- 错误处理：所有接口 422 超参错误返回 `HTTPValidationError { detail: [...] }`。
- 依赖：Milvus、BM25 存储、硅基流动 API（embedding/rerank/LLM）。
