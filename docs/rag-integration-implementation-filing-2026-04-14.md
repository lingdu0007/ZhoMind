# RAG 接入实施报备（EX-2026-04-14-RAG-CHAT-01）

- 变更单号：`EX-2026-04-14-RAG-CHAT-01`
- 日期：2026-04-14
- 目标：打通 `Embedding -> Milvus/BM25 -> Rerank -> LLM -> /chat & /chat/stream`
- 发布策略：分阶段灰度，失败可一键回滚至 Echo/Mock 链路

---

## 1. 变更背景与目标

当前 `/api/v1/chat` 与 `/api/v1/chat/stream` 为占位/回声逻辑，无法反映真实 RAG 效果。
本次实施目标是在**不破坏已冻结 API 契约**前提下，完成后端真实链路接入，并输出可量化运行指标。

### 成功标准（对外）

1. `POST /api/v1/chat` 返回 `200`，响应结构保持契约一致。
2. `POST /api/v1/chat/stream` 返回稳定 `text/event-stream`，失败时错误结构保持统一。
3. `request_id` 在 API 与 RAG service 全链路可追踪。
4. 不引入契约漂移（字段名、状态枚举、错误结构不变）。

---

## 2. 变更范围（报备）

### 2.1 允许修改（本期）

- `backend/src/api/routers/chat.py`（仅接线与错误映射，不改契约字段）
- `backend/src/api/app.py`（注入已存在 RAG service 的依赖绑定）
- `backend/src/application/*`（RAG 编排 service，如已存在则接入；若缺失则新增最小编排层）
- `backend/src/infrastructure/*`（Milvus/BM25/Rerank/LLM 客户端适配与配置读取）
- `backend/src/infrastructure/logging/*`（指标与链路追踪埋点）
- `backend/tests/*`（新增/更新回归测试）

### 2.2 禁止修改（本期）

- `auth/sessions/documents/jobs` 的协议语义与返回结构
- 前端协议及前端调用契约
- 任意 API 路径与字段命名（除内部无感重构）

---

## 3. 契约红线与兼容策略

1. `/chat` 返回体严格维持：
   - `session_id`
   - `message.message_id/role/content/timestamp/rag_trace`
2. `/chat/stream` 事件协议不破坏：
   - `meta/content/.../done`（如已有 `error/rag_step/trace` 保持兼容）
3. 全部非 2xx 错误继续走统一结构：
   - `{code, message, detail, request_id}`
4. 不新增必须字段，不重命名既有字段，不改枚举值。

---

## 4. 技术实施方案（最小可回滚）

### 4.1 同步接口 `/chat`

- API 层负责：
  - 参数校验（沿用现有）
  - request_id/session_id 生成与透传
  - 调用 RAG 编排 service（同步）
  - 将内部结果映射回契约 ChatResponse

### 4.2 流式接口 `/chat/stream`

- API 层负责：
  - 建立 SSE 响应
  - 透传 request_id/session_id/message_id 到 RAG stream
  - 将 token/chunk 映射成 `content` 事件
  - 结束统一发送 `done`
  - 异常统一映射 `error` 事件 + 统一错误码

### 4.3 RAG 编排链路

- 查询改写/向量化（Embedding）
- 向量检索（Milvus）与关键词检索（BM25）
- 候选融合与重排（Rerank）
- LLM 生成（同步/流式双模式）
- 结果追踪（可选写入 `rag_trace`）

---

## 5. 观测指标与采集口径

### 5.1 指标定义

- 检索命中率（Hit Rate）
- 首包时延（TTFB）
- 总时延（E2E Latency）
- 失败率（Failure Rate）
- 成本（Cost per request）

### 5.2 采集口径

- 维度：`request_id/session_id/model/retriever`
- 统计窗口：分钟/小时/日
- 成本口径：按模型 token 单价换算（输入/输出分开）

---

## 6. 回归用例（必须）

1. `/chat` 成功路径：200 + 契约字段齐全
2. `/chat` 检索失败降级路径：错误结构统一
3. `/chat/stream` 成功路径：`meta/content/done` 顺序完整
4. `/chat/stream` 失败路径：`error + done`，且 polling 语义一致
5. request_id 追踪：API 日志与 RAG service 日志可串联
6. 契约防漂移：对比 `docs/backend-api-contract-v1.md` 的关键字段

---

## 7. 复现步骤（提交时附）

1. 启动服务（含依赖：Milvus/BM25/LLM 网关）
2. 准备最小知识库样本并完成索引
3. 调用 `/api/v1/chat` 校验非流式
4. 调用 `/api/v1/chat/stream` 校验流式与异常路径
5. 拉取日志按 `request_id` 串联检索->重排->生成链路
6. 产出指标截图/JSON 汇总

---

## 8. 回滚方案（必须）

### 8.1 回滚触发条件

- 出现契约漂移
- 主链路回归失败
- 5xx 异常率显著升高
- SSE 不稳定（断流/无 done）

### 8.2 回滚动作

1. 切换 feature flag：`RAG_CHAT_ENABLED=false`
2. `/chat` 与 `/chat/stream` 回退到原稳定逻辑（Echo/Mock）
3. 保留观测与日志，不回滚错误统一处理层
4. 输出回滚后验证结果（契约回归 + 烟测）

### 8.3 回滚验证

- 契约回归关键项全绿
- `/chat` 和 `/chat/stream` 可用性恢复
- 5xx 回落到基线

---

## 9. 风险与缓解

1. 外部依赖不稳定（Milvus/LLM）
   - 缓解：超时、重试、降级、熔断
2. 流式链路中断
   - 缓解：异常兜底 `error + done`
3. 成本波动超预期
   - 缓解：限流、上下文截断、缓存与召回阈值调优
4. 隐性契约漂移
   - 缓解：增加契约快照测试与 PR 门禁

---

## 10. 交付清单

- 代码变更（最小范围）
- 回归测试报告（含新增用例）
- 可复现步骤文档
- 指标基线与对比结果
- QA 验证结论（GO/NO-GO）
