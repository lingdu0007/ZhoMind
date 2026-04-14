# Retrieval 数据一致性报告 v1

## 1. 当前迁移状态

- 基础 schema：`20260413_0001_initial_schema`
- 检索持久化 schema：`20260414_0002_retrieval_persistence`
- 当前状态：**已完成到 head**（`users/sessions/messages/documents/document_jobs/document_chunks/bm25_postings`）

## 2. 回滚点

- 回滚目标：`20260413_0001_initial_schema`
- 回滚方式：
  - `alembic downgrade 20260413_0001`
- 回滚影响：
  - 删除 `document_chunks` / `bm25_postings`
  - 恢复到仅有文档任务与基础业务表的状态

## 3. 重建流程

### 3.1 单文档重建
1. 查询 `document_chunks(document_id, version)`
2. 将 chunk 状态标记为 `indexing`
3. upsert Milvus 向量
4. upsert BM25 postings
5. 标记 chunk 状态为 `indexed` 并写入 `indexed_at`

### 3.2 文档删除
1. 删除 Milvus 文档向量
2. 删除 BM25 postings
3. 删除 DB 检索数据（`document_chunks` / `bm25_postings`）
4. 返回删除计数用于审计/补偿

## 4. 一致性校验结论

- `chunk_id` 为唯一键，支持幂等重建
- `version` 已纳入查询与删除边界，支持版本级重建/清理
- `index_status` 生命周期可追踪：`pending -> indexing -> indexed -> failed`
- 删除同步已实现“双端先删 + DB 清理”模式，具备补偿重放基础

## 5. 风险与建议阈值

### 5.1 索引膨胀风险
建议阈值：
- 单文档 chunk 数 > **2000**：建议拆分版本重建或延迟批处理
- `bm25_postings` 单文档 term 行数 > **50,000**：建议压缩停用词并减少 generated_questions 长度
- `document_chunks` 版本数 > **3**：建议清理旧版本或仅保留最新 2 个 active version

### 5.2 查询性能风险
建议阈值：
- 单次检索候选数 `top_k` 不超过 **50**（当前默认 8~10）
- `document_ids` 过滤集合不超过 **20** 个；超过后建议分批
- 目标 `p95`：
  - dense 搜索 < **50ms**
  - BM25 查询 < **20ms**
  - 融合阶段 < **5ms**

## 6. 最小测试覆盖

- 迁移存在性检查
- RetrievalRepository 写入/删除/状态标记
- version 边界删除与重建
- `index_sync` 重建后状态变更
- 删除同步后 DB 计数为 0

## 7. 复现步骤

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --with pytest --with alembic --with sqlalchemy --with aiosqlite --with fastapi --with pydantic --with pydantic-settings --with python-multipart pytest -q backend/tests/test_db_integration.py
```

预期：
- `document_chunks` 和 `bm25_postings` 建表成功
- retrieval 持久化测试通过
- 删除/重建流程可复现
