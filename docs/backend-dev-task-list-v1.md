# ZhoMind 后端开发任务清单（基于 API 契约 v1）

> 来源文档：`docs/backend-api-contract-v1.md`  
> 目标：将接口契约拆分为可执行、可排期、可验收的后端开发任务。  
> 核心变更：文档管理采用**异步任务化**（上传后返回 `job_id`，前端轮询/订阅）。

---

## 0. 里程碑总览

- **M1（基础可用）**：认证 + 会话查询 + 同步聊天（`/chat`）
- **M2（核心体验）**：SSE 流式聊天（`/chat/stream`）+ 事件协议落地
- **M3（异步文档流水线）**：上传受理 + 构建任务（job）+ 状态查询/SSE 订阅 + 分块结果
- **M4（工程完善）**：统一错误模型、可观测性、联调验收、文档收敛

---

## 1. P0 必做（先打通主链路）

### T1. 统一工程基础与路由版本
- **目标**：后端统一挂载 `/api/v1` 前缀，避免与前端基地址歧义。
- **输出**：全部 API 通过 `/api/v1/*` 访问。
- **DoD**：`GET /api/v1/auth/me`（未登录）返回 401（非 404）。
- **预估**：0.5 人天
- **依赖**：无

### T2. 统一响应与错误模型
- **目标**：建立全局错误结构：`code/message/detail/request_id`。
- **输出**：全局异常处理中间件 + 状态码映射（400/401/403/404/409/422/500）。
- **DoD**：任一错误场景都返回统一结构，日志可按 `request_id` 追踪。
- **预估**：1 人天
- **依赖**：T1

### T3. 认证接口实现（Auth）
- **目标**：实现 `/auth/register`、`/auth/login`、`/auth/me`。
- **DoD**：
  - 注册 201 返回 `AuthTokens`
  - 登录失败返回 401 + `AUTH_BAD_CREDENTIALS`
  - `/auth/me` 鉴权有效
- **预估**：1.5 人天
- **依赖**：T2

### T4. 会话查询接口实现（Sessions Read）
- **目标**：实现 `/sessions`、`/sessions/{session_id}`（GET）。
- **DoD**：列表统一 `items + pagination`，资源不存在返回 404。
- **预估**：1 人天
- **依赖**：T3

### T5. 同步聊天接口实现（/chat）
- **目标**：实现非流式问答主链路。
- **DoD**：
  - 支持 `session_id` 空值自动建会话
  - 返回 `ChatResponse`
  - 会话消息可在 `/sessions*` 查询到
- **预估**：1.5 人天
- **依赖**：T4

---

## 2. P1 高优先（流式体验与可靠性）

### T6. SSE 流式聊天实现（/chat/stream）
- **目标**：实现 `meta/content/rag_step/trace/error/done` 事件序列。
- **DoD**：前端可稳定驱动“思考中 -> 生成中 -> 完成/失败”；`done` 必须且仅一次。
- **预估**：2 人天
- **依赖**：T5

### T7. 流式异常与中断处理
- **目标**：规范中断、上游失败、超时行为。
- **DoD**：
  - 取消/断网/上游失败可区分
  - 出错发送 `error` 后及时结束
  - 无僵尸连接
- **预估**：1 人天
- **依赖**：T6

### T8. 会话删除接口（Sessions Delete）
- **目标**：实现 `DELETE /sessions/{session_id}`。
- **DoD**：成功 204，删除后查询 404。
- **预估**：0.5 人天
- **依赖**：T4

---

## 3. P2 文档异步流水线（核心变更）

### T9. 文档数据模型重构
- **目标**：从“文件条目”升级为“文档 + 构建任务”双实体。
- **输出**：
  - `documents`：`document_id/filename/file_type/file_size/status/chunk_strategy/chunk_count/uploaded_at/ready_at`
  - `document_jobs`：`job_id/document_id/status/stage/progress/error_code/...`
- **DoD**：状态机可表达 `queued/running/succeeded/failed/canceled`。
- **预估**：1.5 人天
- **依赖**：T2

### T10. 异步队列与任务执行器
- **目标**：落地构建流水线：`uploaded -> parsing -> chunking -> embedding -> indexing -> completed`。
- **输出**：
  - 消息队列/任务系统接入（如 Celery/RQ/自研 worker）
  - Worker 执行与重试策略
- **DoD**：
  - 上传后任务可被 worker 消费
  - 阶段和进度持续更新
  - 失败可落错误码（如 `DOC_PARSE_ERROR`）
- **预估**：2.5 人天
- **依赖**：T9

### T11. 上传受理接口改造（/documents/upload）
- **目标**：上传接口改为异步受理。
- **输出**：`202 Accepted` + `job_id/document_id/status=queued`。
- **DoD**：
  - 接口不阻塞等待向量化完成
  - 失败仅指“受理失败”；执行失败通过 job 状态体现
- **预估**：1 人天
- **依赖**：T10

### T12. 任务查询接口（轮询）
- **目标**：实现 `GET /documents/jobs` 与 `GET /documents/jobs/{job_id}`。
- **DoD**：
  - 支持按 `status/document_id` 过滤
  - 前端 2~5s 轮询可拿到准确进度
- **预估**：1 人天
- **依赖**：T9

### T13. 任务进度订阅（SSE）
- **目标**：实现 `GET /documents/jobs/{job_id}/stream`。
- **事件**：`progress/error/done`
- **DoD**：
  - 任务阶段变化实时推送
  - 完成时发送 `done`
- **预估**：1.5 人天
- **依赖**：T10

### T14. 任务取消接口
- **目标**：实现 `POST /documents/jobs/{job_id}/cancel`。
- **DoD**：
  - 仅 `queued/running` 可取消
  - 已完成任务返回 409 `DOC_JOB_STATE_CONFLICT`
- **预估**：0.5 人天
- **依赖**：T10

### T15. 文档列表与删除接口完善（admin）
- **目标**：实现 `GET /documents` 与 `DELETE /documents/{filename}` 并与 job 体系一致。
- **DoD**：
  - 列表可按 `status` 过滤
  - 删除时处理运行中 job（阻止删除或级联取消，二选一并文档化）
- **预估**：1.5 人天
- **依赖**：T9, T10

### T19. 分块策略字段与校验
- **目标**：文档表与构建任务支持 `chunk_strategy`。
- **DoD**：
  - `chunk_strategy` 写入文档记录
  - 非法策略返回 `DOC_INVALID_CHUNK_STRATEGY`
- **预估**：0.5 人天
- **依赖**：T9

### T20. 单文件构建接口（/documents/{document_id}/build）
- **目标**：支持按策略触发单文档重建。
- **DoD**：
  - 返回 `202 + job_id`
  - 文档状态切换为 `processing`
- **预估**：1 人天
- **依赖**：T10, T19

### T21. 批量构建接口（/documents/batch-build）
- **目标**：支持批量触发构建任务。
- **DoD**：
  - 返回每个文档的 `job_id`
  - 支持部分失败并返回失败明细
- **预估**：1.5 人天
- **依赖**：T10, T19

### T22. 批量删除接口（/documents/batch-delete）
- **目标**：支持批量删除并返回失败明细。
- **DoD**：
  - 响应包含 `success_ids` 与 `failed_items`
  - 对运行中任务执行级联取消或阻止删除
- **预估**：1 人天
- **依赖**：T15

### T23. 分块结果查询接口（/documents/{document_id}/chunks）
- **目标**：分页返回分块结果与元数据。
- **DoD**：
  - 返回 `items + pagination`
  - 未就绪返回 409 `DOC_CHUNK_RESULT_NOT_READY`
- **预估**：1.5 人天
- **依赖**：T10

### T24. 分块策略字典输出
- **目标**：支持前端“分块方式说明”弹窗。
- **DoD**：
  - 可通过接口或配置输出策略说明
  - 描述包含适用场景与参数要点
- **预估**：0.5 人天
- **依赖**：T19

---

## 4. P3 工程化与质量保障

### T16. OpenAPI 文档收敛
- **目标**：服务端导出与契约一致的 `/openapi.json`。
- **DoD**：包含文档 job 相关接口和 schema。
- **预估**：0.5 人天
- **依赖**：T1~T15, T19~T24

### T17. 自动化测试（最小覆盖）
- **目标**：建立核心 API 回归。
- **覆盖建议**：
  - Auth：注册/登录/鉴权失败
  - Chat：同步 + SSE done
  - Documents：上传返回 202 + job 状态迁移 + 任务取消 + 分块结果查询
  - Batch：批量构建/批量删除部分失败
- **DoD**：CI 通过，核心链路通过率 100%。
- **预估**：2.5 人天
- **依赖**：T3~T15, T19~T24

### T18. 前后端联调与兼容清理
- **目标**：前端切换到 job 模式，移除临时兼容分支。
- **DoD**：
  - 上传后使用 `job_id` 轮询/订阅
  - 列表统一 `items`、分页统一 `pagination`
- **预估**：1 人天
- **依赖**：T11~T17

---

## 5. 推荐执行顺序（四周版）

1. **第 1 周**：T1 → T2 → T3 → T4 → T5  
2. **第 2 周**：T6 → T7 → T8  
3. **第 3 周**：T9 → T10 → T11 → T12 → T19 → T20  
4. **第 4 周**：T13 → T14 → T15 → T21 → T22 → T23 → T24 → T16 → T17 → T18

> 若需压缩排期：优先 M1+M2，再做 M3 的“轮询版”（T13 SSE 可延后）。

---

## 6. 风险与预案

1. **队列/worker 稳定性不足**
   - 预案：先单 worker 串行保证正确性，再扩并发；失败任务可人工重试。
2. **大文件处理耗时不可控**
   - 预案：文件大小/页数上限 + 超时 + 分阶段进度上报。
3. **索引一致性问题（任务成功但不可检索）**
   - 预案：`succeeded` 前增加检索可用性探针，失败回滚为 `failed`。
4. **删除与运行中任务冲突**
   - 预案：定义明确策略（阻止或级联取消）并固化错误码。

---

## 7. Release Gate（完成标志）

- [ ] P0 全部完成并联调通过
- [ ] `/chat/stream` 事件协议与中断场景通过测试
- [ ] 上传接口返回 `202 + job_id`，并可通过轮询拿到最终状态
- [ ] 至少一种进度通道可用：轮询（必选）/SSE 订阅（推荐）
- [ ] 文档 `ready` 后可参与 RAG 检索，`failed` 可追踪错误原因
- [ ] 分块结果可分页查询，批量操作可返回部分失败明细
- [ ] CI 覆盖核心链路，且前端不再依赖响应结构兜底分支
