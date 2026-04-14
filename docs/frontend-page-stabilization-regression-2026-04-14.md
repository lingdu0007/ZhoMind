# 页面稳定化回归记录（2026-04-14）

## 本轮范围

1. Chat 页与流式问答链路的加载态、错误态、拒答态展示优化（最小改动）。
2. 补充真实用户路径测试：登录、上传、问答、失败提示。
3. 固化前端请求路径与代理语义，避免 `/api` 与 `/api/v1` 混乱。

## 代码改动

- `frontend/src/store/chat-state.js`
  - 新增状态判定与错误文案函数：
    - `extractRejectReason(step)`
    - `formatStreamError(error)`
    - `getDoneStatus(assistantMsg)`
- `frontend/src/store/chat.js`
  - 为 assistant 消息增加 `rejected/reject_reason` 状态。
  - 在 `rag_step(retrieve)` 阶段识别 `gate_passed=false + gate_reason=*reject*`，进入拒答态。
  - `onError` 与异常 `catch` 统一使用可读错误文案。
  - `onDone` 在拒答且无正文时补默认拒答文案。
- `frontend/src/components/ChatMessageList.vue`
  - 状态文本按错误/拒答/停止分类着色。
  - 新增拒答提示块（`拒答原因：知识片段不足`）。
- `frontend/src/pages/ChatPage.vue`
  - 顶部 subtitle 改为显示当前流状态（流式中 / 最后状态）。

## 前端路径与代理稳定性

- 环境入口保持：
  - `.env.development`: `VITE_API_BASE_URL=/api`
  - `.env.production`: `VITE_API_BASE_URL=/api`
- Vite 代理：
  - `frontend/vite.config.js` 使用 `rewrite: (path) => path.replace(/^\/api/, '/api/v1')`
- 直连回退：
  - `frontend/src/api/http.js` 回退基址固定为 `http://127.0.0.1:8000/api/v1`

## 自动化回归执行记录

### 1) 单元/解析回归

```bash
cd frontend
node --test tests/chat-state.test.mjs tests/sse-parser.test.mjs tests/path-config.test.mjs
```

- 结果：3 passed，0 failed。

### 2) 构建回归

```bash
cd frontend
npm run build
```

- 结果：通过（exit code 0）。

### 3) 真实用户路径 smoke（联调后端）

```bash
cd frontend
node tests/user-path-smoke.mjs
```

- 覆盖：
  - `auth/login`
  - `documents/upload`（成功样本 + 失败样本）
  - `documents/jobs/{job_id}` 轮询终态
  - `chat` 同步问答
  - `chat/stream` 流式事件
- 结果：通过（ok=true）。
- 证据样例：
  - `login_status=200`
  - 成功任务：`status=succeeded/stage=completed`
  - 失败任务：`status=failed/stage=failed/error_code=DOC_PARSE_ERROR`

## 异常处理说明（页面侧）

### Chat / Stream

- `401`：提示“登录状态已失效，请重新登录”。
- `AUTH_FORBIDDEN`：提示“无权限执行当前问答”。
- 流式 `error` 事件：显示“生成失败 + 可读错误文案”。
- 流式中断（用户点停止）：显示“已停止”并保留已生成内容。
- 检索拒答（`gate_reason` 含 `reject`）：
  - 状态：`证据不足，进入拒答` -> 完成后 `已拒答（证据不足）`
  - 展示拒答提示块，正文为空时补默认拒答文案。

### Upload / Documents

- 上传失败：展示接口 `message`，有 `code` 时附加显示。
- 构建任务失败：任务区展示 `status/stage/message/error_code`。
- 分块未就绪：`DOC_CHUNK_RESULT_NOT_READY` -> 友好提示“分块结果未就绪，请稍后再试”。

## 手工复现步骤（给 QA）

1. 登录管理员账号（`admin/admin-token`）。
2. 聊天页输入“你好”：
   - 验证“流式生成中”状态；
   - 完成后状态清空或显示拒答态（按检索结果）。
3. 上传页上传正常文本文件：
   - 任务进入 `queued/running/succeeded`；
   - 文档状态到 `ready`。
4. 上传页上传空白文本：
   - 任务终态 `failed`；
   - 提示 `Document parse failed`。
5. 问答失败路径（可用失效 token 模拟）：
   - 页面展示可读错误文案，不出现裸协议文本。
