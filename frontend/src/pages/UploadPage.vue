<template>
  <section>
    <h1 class="page-title">文档上传</h1>

    <div v-if="!authStore.isLoggedIn" class="panel">请先在聊天页登录。</div>
    <div v-else-if="!authStore.isAdmin" class="panel">当前账号非管理员，不能管理文档。</div>
    <template v-else>
      <UploadPanel @uploaded="loadDocs" />

      <div class="panel list-panel">
        <div class="list-header">
          <h3>文档列表</h3>
          <el-button @click="loadDocs">刷新</el-button>
        </div>
        <el-table :data="docs" v-loading="loading">
          <el-table-column prop="filename" label="文件名" />
          <el-table-column prop="file_type" label="类型" width="120" />
          <el-table-column prop="chunk_count" label="分块数" width="120" />
          <el-table-column prop="uploaded_at" label="上传时间" width="220" />
          <el-table-column label="操作" width="120">
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
import { onMounted, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import UploadPanel from '../components/UploadPanel.vue';
import { apiAdapter } from '../api/adapters';
import { useAuthStore } from '../store/auth';

const authStore = useAuthStore();
const docs = ref([]);
const loading = ref(false);

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
.list-panel {
  margin-top: 16px;
}

.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

h3 {
  margin: 0;
}
</style>
