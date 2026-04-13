# ZhoMind 前端设计文档

## 1. 概览
- **目标**：面向桌面端（≥1280px）提供 Agentic RAG 控制台，包括聊天、文档上传、配置管理。
- **技术栈**：Vue 3 + Vite，Pinia 状态管理，Element Plus 组件库，Lucide 图标，Fira Sans / Fira Code 字体。
- **部署模式**：静态资源经 Nginx 托管，`/api/` 前缀反代 FastAPI（默认 `http://127.0.0.1:8000/api/`）。

## 2. 视觉与布局系统
- **网格**：12 列，最大宽度 1440px。侧栏占 2 列（~200px），主内容 8 列，右侧留出 2 列呼吸区。
- **配色**：
  - 背景 `#F8FAFC`
  - 侧栏 `#F1F5F9`
  - 主色 `#475569`
  - CTA `#2563EB`
  - 警告/错误：`#F97316` / `#DC2626`
- **组件语言**：
  - 卡片统一圆角 16px、阴影 `0 8px 30px rgba(15,23,42,0.06)`。
  - 线框按钮 `btn-ghost`，实心 CTA `btn-primary`。
  - 表格自定义皮肤 `.table-minimal`（浅色表头、行 hover #EEF2FF）。
  - SessionDrawer、状态条等使用同色线条/背景，避免彩色块。

## 3. 页面规范

### 3.1 App 壳 / 导航
- 文件：`src/app/App.vue`
- 结构：固定侧栏（Logo + 导航），主视图包裹 `router-view`。
- 组件：Lucide 图标 `MessageCircle`/`FileText`/`SlidersHorizontal`。

### 3.2 聊天页（`src/pages/ChatPage.vue`）
- **顶部控制条**：显示标题、Streaming 状态、会话按钮、登录状态。
- **SessionDrawer**：`src/components/SessionDrawer.vue`，下拉抽屉展示会话列表，可刷新/删除。
- **消息列表**：`src/components/ChatMessageList.vue`，单列卡片展示角色、正文、RAG 步骤、Trace。
- **输入区**：浮动卡片包含多行输入框、停止与发送按钮；使用 Pinia `chatStore` 的 `sendMessage` + `streamChat` 实现流式更新。

### 3.3 文档上传页（`src/pages/UploadPage.vue`）
- 上传卡片（`UploadPanel.vue`）+ 统计条 + 极简表格。
- 支持搜索、刷新按钮；管理员权限校验通过 `authStore.isAdmin`。

### 3.4 配置页（`src/pages/ConfigPage.vue`）
- 分四张卡片：模型配置、检索参数、存储配置、安全/API。
- 使用 `configStore` 本地持久化，提供复制按钮（`navigator.clipboard`），保存时展示时间戳。

## 4. 交互流程
1. **认证**：登录后将 token 存入 `localStorage`，Axios 拦截器自动附加 `Authorization`。
2. **聊天 Streaming**：
   - `streamChat`（`src/api/adapters.js`）使用 `fetch` + `ReadableStream` 解析 SSE，支持 `content/rag_step/trace/error/done`。
   - Pinia store 每次 `onContent` 事件追加 token，`ChatMessageList` 自动 rerender。
3. **文档管理**：上传走 `/documents/upload`，列表/删除 `/documents` 系列接口，非管理员显示提示卡片。
4. **配置**：读取本地 `localStorage` 配置，可扩展为调用真实 API；保存后展示时间戳。

## 5. 部署要点
- 构建：`cd frontend && npm install && npm run build`。
- 产物：`frontend/dist`。
- Nginx 示例（见 `deploy/nginx/zhomind-frontend.conf`）：
  - `root /var/www/zhomind-frontend`
  - `location / { try_files ... }`
  - `location /api/ { proxy_pass http://127.0.0.1:8000/api/; proxy_buffering off; }`
- 确保静态与 API 同源以避免 SSE 缓冲。

## 6. 未来扩展建议
- 支持多主题（暗色），拆分大 bundle（动态 import）。
- 聊天页增加 RAG Trace 折叠区的结构化展示。
- 配置页可切换为真实后端接口，实现团队级配置共享。
