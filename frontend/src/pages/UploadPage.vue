<template>
  <section class="upload-page">
    <div class="top-bar">
      <h1>文档上传</h1>
      <el-button v-if="authStore.isAdmin" class="btn-ghost" @click="loadDocs">刷新</el-button>
    </div>

    <div v-if="!authStore.isLoggedIn" class="card notice">请先在聊天页登录。</div>
    <div v-else-if="!authStore.isAdmin" class="card notice">当前账号非管理员，不能管理文档。</div>
    <template v-else>
      <UploadPanel @uploaded="loadDocs" />

      <div class="stat-row">
        <div class="stat-card" v-for="stat in stats" :key="stat.label">
          <p class="stat-label">{{ stat.label }}</p>
          <p class="stat-value">{{ stat.value }}</p>
        </div>
      </div>

      <div class="card table-card">
        <div class="table-header">
          <h3>文档列表</h3>
          <div class="table-tools">
            <el-input v-model="keyword" placeholder="搜索文件" clearable />
            <el-button class="btn-ghost" @click="loadDocs">刷新</el-button>
          </div>
        </div>
        <el-table class="table-minimal" :data="filteredDocs" v-loading="loading">
          <el-table-column prop="filename" label="文件名" />
          <el-table-column prop="file_type" label="类型" width="120" />
          <el-table-column prop="chunk_count" label="分块数" width="120" />
          <el-table-column prop="uploaded_at" label="上传时间" width="220" />
          <el-table-column label="操作" width="140">
            <template #default="scope">
              <el-button link type="danger" @click="removeDoc(scope.row.filename)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import UploadPanel from '../components/UploadPanel.vue';
import { apiAdapter } from '../api/adapters';
import { useAuthStore } from '../store/auth';

const authStore = useAuthStore();
const docs = ref([]);
const loading = ref(false);
const keyword = ref('');

const stats = computed(() => [
  { label: '文档总数', value: docs.value.length },
  {
    label: '总分块',
    value: docs.value.reduce((sum, item) => sum + (item.chunk_count || 0), 0)
  },
  { label: '最近上传', value: docs.value[0]?.uploaded_at || '--' }
]);

const filteredDocs = computed(() =>
  docs.value.filter((doc) => doc.filename?.toLowerCase().includes(keyword.value.toLowerCase()))
);

const loadDocs = async () => {
  if (!authStore.isLoggedIn || !authStore.isAdmin) return;
  loading.value = true;
  try {
    const data = await apiAdapter.listDocuments();
    docs.value = data?.items || data?.documents || data?.data || [];
  } catch (error) {
    ElMessage.error(error.message || '加载文档列表失败');
  } finally {
    loading.value = false;
  }
};

const removeDoc = async (filename) => {
  try {
    await ElMessageBox.confirm(`确认删除文档 ${filename}？`, '提示', { type: 'warning' });
    await apiAdapter.deleteDocument(filename);
    ElMessage.success('文档已删除');
    await loadDocs();
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(error.message || '删除文档失败');
  }
};

onMounted(loadDocs);
</script>

<style scoped>
.upload-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.table-card {
  margin-top: 16px;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px;
  border-bottom: 1px solid var(--line-soft);
}

.table-header h3 {
  margin: 0;
}

.table-tools {
  display: flex;
  align-items: center;
  gap: 12px;
}
</style>
