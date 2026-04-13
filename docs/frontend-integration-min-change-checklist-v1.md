# 前端联调最小改造清单（Vue 3 + Pinia）

> 目标：在尽量少改现有结构的前提下，完成“文件管理异步任务化（`job_id`）+ 分块策略 + 分块结果查看 + 批量操作”联调。  
> 对齐文档：`docs/backend-api-contract-v1.md`（最新）
> 适用范围：当前 `UploadPage.vue` + `UploadPanel.vue` + `src/api/adapters.js`。

---

## 0. 改造原则（最小化）

1. **不重构页面结构**：保留当前上传卡片 + 任务区 + 文档表格主布局。
2. **不强制新增全局状态库**：优先在 `UploadPage.vue` 本地 `ref` 管理任务与批量选择。
3. **先轮询后订阅**：P0 只接 `GET /documents/jobs/{job_id}` 轮询；SSE 作为 P2 增强。
4. **接口字段统一**：列表统一读取 `items`，分页统一 `pagination`，不再保留 `documents/data` 兜底分支。

---

## 1. API Adapter 精确回填（P0/P1）

文件：`frontend/src/api/adapters.js`

### 1.1 已有能力（保持）
- [ ] `uploadDocument(formData)` 适配 `202` 返回：`job_id/document_id/status`
- [ ] `listDocumentJobs(params)`
- [ ] `getDocumentJob(jobId)`
- [ ] `cancelDocumentJob(jobId)`

### 1.2 新增接口（本次回填）
- [ ] `buildDocument(documentId, payload)` -> `POST /documents/{document_id}/build`
  - payload: `{ chunk_strategy }`
- [ ] `batchBuildDocuments(payload)` -> `POST /documents/batch-build`
  - payload: `{ document_ids, chunk_strategy }`
- [ ] `batchDeleteDocuments(payload)` -> `POST /documents/batch-delete`
  - payload: `{ document_ids }`
- [ ] `getDocumentChunks(documentId, params)` -> `GET /documents/{document_id}/chunks`
  - params: `page/page_size`

### 1.3 可选接口
- [ ] `listChunkStrategies()` -> `GET /documents/chunk-strategies`（若后端提供）

**验收标准**
- [ ] 单文件构建能返回新 `job_id`
- [ ] 批量构建返回每个 `document_id` 对应 `job_id`
- [ ] 分块结果可分页拉取

---

## 2. UploadPanel 改造（P0）

文件：`frontend/src/components/UploadPanel.vue`

### 2.1 已完成/保持
- [ ] `emit('uploaded', { job_id, document_id, filename })`
- [ ] 上传成功文案明确“已入队”

### 2.2 建议补充
- [ ] 上传成功后清空组件内部文件列表（避免误触重复提交）
- [ ] 错误提示优先展示 `message`，必要时拼接 `code`

**验收标准**
- [ ] 父组件稳定拿到 `job_id`
- [ ] 用户清晰感知“异步处理中”

---

## 3. UploadPage 精确回填（P0/P1）

文件：`frontend/src/pages/UploadPage.vue`

### 3.1 任务轮询闭环（P0，保持）
- [ ] `jobs = ref([])` 保存最近任务（建议 20 条）
- [ ] 上传后 `schedulePoll(job_id)` 启动轮询
- [ ] `queued` 每 4s、`running` 每 2s
- [ ] 终态 `succeeded/failed/canceled` 停止轮询
- [ ] `succeeded` 后刷新 `loadDocs()`
- [ ] `onBeforeUnmount` 清理所有 timer

### 3.2 文档表字段补齐（P1）
- [ ] 增加列：`file_size`
- [ ] 增加列：`chunk_strategy`（支持下拉编辑或展示）
- [ ] `status` 列改为 Tag + 中文映射

### 3.3 单文件分块（P1）
- [ ] 行级“执行分块”按钮
- [ ] 点击时调用 `buildDocument(document_id, { chunk_strategy })`
- [ ] 返回 `job_id` 后加入任务区并轮询

### 3.4 批量操作（P1）
- [ ] 表格多选（selection）
- [ ] 顶部操作：`批量分块(n)`、`批量删除(n)`
- [ ] 批量分块调用 `batchBuildDocuments`
- [ ] 批量删除调用 `batchDeleteDocuments`
- [ ] 批量删除后根据 `failed_items` 提示部分失败明细

### 3.5 分块结果弹窗（P1）
- [ ] 行级“查看分块结果”按钮
- [ ] 打开弹窗后请求 `getDocumentChunks(document_id, { page, page_size })`
- [ ] 展示字段：`content/keywords/generated_questions/metadata`
- [ ] 支持分页切换

**验收标准**
- [ ] 单文件分块能触发独立任务并可追踪到终态
- [ ] 批量分块可一次创建多个任务
- [ ] 分块结果弹窗可分页展示内容

---

## 4. 权限、错误与一致性（P0/P1）

### 4.1 权限
- [ ] 保持 `authStore.isAdmin` 守卫
- [ ] `403` 明确提示“仅管理员可操作文档管理功能”

### 4.2 认证
- [ ] 保持 axios `401` 清理登录态
- [ ] 页面在未登录/非管理员时显示降级提示

### 4.3 一致性
- [ ] 文档 `ready` 前不允许查看分块结果（或提示“结果未就绪”）
- [ ] 若后端返回 `DOC_CHUNK_RESULT_NOT_READY`，前端转为友好提示
- [ ] 删除文档后同步移除本地选中状态与任务关联展示

**验收标准**
- [ ] 典型错误可读且可恢复
- [ ] 页面状态不出现“文档已删但仍选中/仍显示可操作”错位

---

## 5. 字段映射规范（P1）

### 5.1 文档状态映射
- [ ] `pending` -> 待处理
- [ ] `processing` -> 处理中
- [ ] `ready` -> 可检索
- [ ] `failed` -> 构建失败
- [ ] `deleting` -> 删除中

### 5.2 任务阶段映射
- [ ] `uploaded` -> 已上传
- [ ] `parsing` -> 解析中
- [ ] `chunking` -> 分块中
- [ ] `embedding` -> 向量化中
- [ ] `indexing` -> 建索引中
- [ ] `completed` -> 已完成
- [ ] `failed` -> 失败

### 5.3 分块策略映射
- [ ] `padding` -> 补齐分块
- [ ] `general` -> 通用分块
- [ ] `book` -> 书籍分块
- [ ] `paper` -> 论文分块
- [ ] `resume` -> 简历分块
- [ ] `table` -> 表格分块
- [ ] `qa` -> 问答分块

---

## 6. 可选增强（P2）

### 6.1 SSE 订阅替代轮询
- [ ] 接入 `GET /documents/jobs/{job_id}/stream`
- [ ] 断线回退到轮询

### 6.2 任务取消
- [ ] `queued/running` 显示“取消任务”
- [ ] 调用 `cancelDocumentJob(jobId)` 并更新状态

### 6.3 分块方式说明
- [ ] 若有策略字典接口，前端动态渲染“分块方式说明”弹窗
- [ ] 无接口时使用本地静态映射兜底

---

## 7. 联调顺序（精确版）

### Day 1（P0 稳定）
- [ ] 确认上传 + 任务轮询闭环
- [ ] 校验文档列表 `items/pagination` 单一结构

### Day 2（单文件分块）
- [ ] 接入 `buildDocument`
- [ ] 完成策略选择与单文件“执行分块”

### Day 3（批量能力）
- [ ] 接入多选
- [ ] 完成 `batchBuildDocuments` + `batchDeleteDocuments`

### Day 4（分块结果）
- [ ] 实现分块结果弹窗
- [ ] 接入分页与字段展示

### Day 5（收敛）
- [ ] 错误提示、权限提示、空态体验
- [ ] 冒烟测试与文案收敛

---

## 8. 联调验收清单（DoD）

### 8.1 P0
- [ ] 上传后 1 秒内拿到 `job_id`
- [ ] 可观察任务状态至少 3 段变化
- [ ] 页面离开无轮询泄漏

### 8.2 P1（新增）
- [ ] 可选分块策略并触发单文件构建
- [ ] 批量分块返回多个 `job_id` 并可跟踪
- [ ] 批量删除可反馈部分失败项
- [ ] 分块结果可分页展示（内容/关键词/问题/元数据）

### 8.3 一致性
- [ ] `ready` 文档可查看分块结果
- [ ] 非 `ready` 文档查看时有明确提示
- [ ] 列表、任务区、弹窗数据相互一致

---

## 9. 影响文件（最小集合）

- `frontend/src/api/adapters.js`
- `frontend/src/components/UploadPanel.vue`
- `frontend/src/pages/UploadPage.vue`

> 若分块结果弹窗单独拆组件，新增：`frontend/src/components/ChunkResultDialog.vue`。