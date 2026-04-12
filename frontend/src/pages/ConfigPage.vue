<template>
  <section>
    <h1 class="page-title">配置页</h1>

    <el-form class="panel" label-width="180px">
      <h3 class="section-title">模型配置（前端本地）</h3>
      <el-form-item label="LLM 模型">
        <el-input v-model="configStore.config.llm_model" />
      </el-form-item>
      <el-form-item label="Embedding 模型">
        <el-input v-model="configStore.config.embedding_model" />
      </el-form-item>
      <el-form-item label="Rerank 模型">
        <el-input v-model="configStore.config.rerank_model" />
      </el-form-item>

      <h3 class="section-title">检索参数（前端本地）</h3>
      <el-form-item label="Top K">
        <el-input-number v-model="configStore.config.top_k" :min="1" :max="50" />
      </el-form-item>
      <el-form-item label="相似度阈值">
        <el-slider v-model="configStore.config.score_threshold" :min="0" :max="1" :step="0.01" />
      </el-form-item>
      <el-form-item label="Dense 权重">
        <el-slider v-model="configStore.config.hybrid_dense_weight" :min="0" :max="1" :step="0.01" />
      </el-form-item>
      <el-form-item label="Sparse 权重">
        <el-slider v-model="configStore.config.hybrid_sparse_weight" :min="0" :max="1" :step="0.01" />
      </el-form-item>

      <div class="actions">
        <el-button @click="load">重置</el-button>
        <el-button type="primary" :loading="configStore.loading" @click="save">保存配置</el-button>
      </div>
    </el-form>
  </section>
</template>

<script setup>
import { onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { useConfigStore } from '../store/config';

const configStore = useConfigStore();

const load = async () => {
  try {
    await configStore.fetchConfig();
    ElMessage.success('配置已加载');
  } catch (error) {
    ElMessage.error(error.message || '加载配置失败');
  }
};

const save = async () => {
  try {
    await configStore.saveConfig();
    ElMessage.success('配置保存成功');
  } catch (error) {
    ElMessage.error(error.message || '保存配置失败');
  }
};

onMounted(load);
</script>

<style scoped>
.section-title {
  margin: 4px 0 12px;
  font-size: 15px;
  color: #374151;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
