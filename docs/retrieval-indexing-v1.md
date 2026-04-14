# Retrieval Indexing v1（持久化、稳定化与调参）

## 1. 范围

本方案实现：
1. chunk 元数据与检索字段持久化
2. Milvus collection schema 与索引策略
3. BM25 存储与更新策略
4. 重建索引/删除文档一致性同步
5. 检索调参配置化（便于 AgentB 动态切换）

不变更现有公开 API 契约字段名、错误结构、状态枚举。

---

## 2. 数据持久化模型

新增表：
- `document_chunks`
- `bm25_postings`

### 2.1 document_chunks

主要字段：
- `chunk_id`（唯一）
- `document_id`
- `chunk_index`
- `content`
- `keywords`
- `generated_questions`
- `metadata`
- `retrieval_text`
- `tokens`
- `version`
- `index_status`（pending/indexing/indexed/failed）
- `indexed_at`

用途：
- 作为检索事实源（source of truth）
- 追踪索引生命周期

### 2.2 bm25_postings

主要字段：
- `chunk_id`
- `document_id`
- `term`
- `tf`
- `doc_len`
- `version`

用途：
- 稀疏检索特征持久化
- 支持增量更新、按版本重建与回收

---

## 3. Milvus schema 与索引策略

Collection: `zhomind_chunks_v1`

字段：
- `chunk_id` (primary)
- `document_id`
- `chunk_index`
- `version`
- `content`
- `embedding` (FLOAT_VECTOR)

索引策略：
- 向量索引：`HNSW`
- 参数：`M=16`, `efConstruction=200`
- 查询参数：`ef=64`
- 过滤：`document_id` / `version`

---

## 4. BM25 更新策略

- 写入时使用 `retrieval_text`（由 content + keywords + generated_questions 拼接）
- 分词后计算 `tf` 与 `doc_len`
- 写入 `bm25_postings`
- 按 `document_id + version` 做替换更新

---

## 5. 一致性策略

## 5.1 重建索引

流程：
1. `replace_document_chunks(document_id, version, chunks)`
2. 标记 `index_status=indexing`
3. upsert 到 Milvus + in-memory BM25
4. 成功后标记 `indexed` + `indexed_at`

失败处理：
- 可将 `index_status` 置为 `failed`，后续重试。

## 5.2 删除文档

流程：
1. 删除 Milvus document 向量（可按 version）
2. 删除 BM25 内存记录
3. 删除 DB `document_chunks` + `bm25_postings`

返回删除统计，便于审计与补偿重试。

---

## 6. 调参配置化（AgentB 使用）

建议通过环境变量或 settings 动态切换以下参数：
- `rag_dense_weight`
- `rag_sparse_weight`
- `rag_bm25_min_term_match`
- `rag_bm25_min_score`
- `rag_dense_top_k`
- `rag_sparse_top_k`
- `rag_dense_rescue_enabled`
- `rag_max_document_filter_count`
- `rag_max_context_tokens`
- `rag_chunk_version_retention`
- `rag_max_chunk_count_per_document`
- `rag_max_bm25_postings_per_document`

默认值偏保守：优先保证“正向可命中”，其次抗噪。

---

## 7. 回滚方案

- 数据库回滚：Alembic downgrade 到 `20260413_0001_initial_schema`
- 索引回滚：按 `version` 过滤切换旧版本查询
- 删除失败补偿：重放 delete_document_index 任务（幂等）

---

## 8. 风险阈值（建议）

- 单文档 chunk 数 > `2000`：建议拆分版本重建或延迟批处理
- `bm25_postings` 单文档 term 行数 > `50000`：建议压缩停用词并减少 `generated_questions`
- `document_chunks` 版本数 > `3`：建议只保留最近 2 个 active version
- 检索候选 `top_k` 不建议超过 `50`
- `document_ids` 过滤集合不建议超过 `20`

---

## 9. 性能基线

建议基线：
- dense 搜索 < `50ms`
- BM25 查询 < `20ms`
- 融合阶段 < `5ms`

---

## 10. 复现步骤

1. 运行迁移到 head
2. 启动服务
3. 上传文档并触发构建
4. 检查 `document_chunks` / `bm25_postings`
5. 调整 settings 的 tuning 参数后重启验证检索结果变化
