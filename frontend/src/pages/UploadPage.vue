<template>
  <section class="upload-page">
    <div class="top-bar">
      <h1>文档上传</h1>
      <el-button v-if="authStore.isAdmin" class="btn-ghost" @click="refreshAll">刷新</el-button>
    </div>

    <div v-if="!authStore.isLoggedIn" class="card notice">请先在聊天页登录。</div>
    <div v-else-if="!authStore.isAdmin" class="card notice">当前账号非管理员，不能管理文档。</div>
    <template v-else>
      <UploadPanel @uploaded="handleUploaded" />

      <div class="stat-row">
        <div class="stat-card" v-for="stat in stats" :key="stat.label">
          <p class="stat-label">{{ stat.label }}</p>
          <p class="stat-value">{{ stat.value }}</p>
        </div>
      </div>

      <div class="card table-card">
        <div class="table-header">
          <h3>构建任务（最近）</h3>
          <el-button class="btn-ghost" @click="loadJobs">刷新任务</el-button>
        </div>

        <el-table class="table-minimal" :data="jobs" empty-text="暂无任务" style="margin: 0 24px 24px">
          <el-table-column prop="job_id" label="任务ID" min-width="220" />
          <el-table-column prop="status" label="状态" width="120" />
          <el-table-column prop="stage" label="阶段" width="140" />
          <el-table-column label="进度" width="180">
            <template #default="scope">
              <el-progress :percentage="Number(scope.row.progress || 0)" :stroke-width="10" />
            </template>
          </el-table-column>
          <el-table-column prop="updated_at" label="更新时间" width="220" />
        </el-table>
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
          <el-table-column prop="status" label="状态" width="120" />
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
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import UploadPanel from '../components/UploadPanel.vue';
import { apiAdapter } from '../api/adapters';
import { useAuthStore } from '../store/auth';

const authStore = useAuthStore();
const docs = ref([]);
const jobs = ref([]);
const loading = ref(false);
const keyword = ref('');

const pollingTimers = new Map();

const stats = computed(() => {
  const queuedOrRunning = jobs.value.filter((item) => ['queued', 'running'].includes(item.status)).length;
  return [
    { label: '文档总数', value: docs.value.length },
    {
      label: '总分块',
      value: docs.value.reduce((sum, item) => sum + (item.chunk_count || 0), 0)
    },
    { label: '进行中任务', value: queuedOrRunning }
  ];
});

const filteredDocs = computed(() =>
  docs.value.filter((doc) => doc.filename?.toLowerCase().includes(keyword.value.toLowerCase()))
);

const sortByUpdatedAtDesc = (items) =>
  [...items].sort((a, b) => new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime());

const mergeJob = (job) => {
  if (!job?.job_id) return;
  const idx = jobs.value.findIndex((item) => item.job_id === job.job_id);
  if (idx >= 0) {
    jobs.value[idx] = { ...jobs.value[idx], ...job };
  } else {
    jobs.value.unshift(job);
  }
  jobs.value = sortByUpdatedAtDesc(jobs.value).slice(0, 20);
};

const clearPolling = (jobId) => {
  const timer = pollingTimers.get(jobId);
  if (timer) {
    clearTimeout(timer);
    pollingTimers.delete(jobId);
  }
};

const schedulePoll = (jobId, delayMs = 2000) => {
  clearPolling(jobId);
  const timer = setTimeout(() => pollJob(jobId), delayMs);
  pollingTimers.set(jobId, timer);
};

const pollJob = async (jobId) => {
  if (!jobId || !authStore.isLoggedIn || !authStore.isAdmin) return;

  try {
    const job = await apiAdapter.getDocumentJob(jobId);
    mergeJob(job);

    const status = job?.status;
    if (['succeeded', 'failed', 'canceled'].includes(status)) {
      clearPolling(jobId);
      if (status === 'succeeded') {
        await loadDocs();
      }
      return;
    }

    const delay = status === 'queued' ? 4000 : 2000;
    schedulePoll(jobId, delay);
  } catch (error) {
    clearPolling(jobId);
    ElMessage.error(error.message || `任务 ${jobId} 查询失败`);
  }
};

const loadDocs = async () => {
  if (!authStore.isLoggedIn || !authStore.isAdmin) return;
  loading.value = true;
  try {
    const data = await apiAdapter.listDocuments();
    docs.value = data?.items || [];
  } catch (error) {
    ElMessage.error(error.message || '加载文档列表失败');
  } finally {
    loading.value = false;
  }
};

const loadJobs = async () => {
  if (!authStore.isLoggedIn || !authStore.isAdmin) return;
  try {
    const data = await apiAdapter.listDocumentJobs({ page: 1, page_size: 20 });
    jobs.value = sortByUpdatedAtDesc(data?.items || []).slice(0, 20);

    jobs.value.forEach((job) => {
      if (['queued', 'running'].includes(job.status)) {
        schedulePoll(job.job_id, job.status === 'queued' ? 4000 : 2000);
      }
    });
  } catch (error) {
    ElMessage.error(error.message || '加载任务列表失败');
  }
};

const refreshAll = async () => {
  await Promise.all([loadDocs(), loadJobs()]);
};

const handleUploaded = async (payload) => {
  const jobId = payload?.job_id;
  if (!jobId) {
    ElMessage.warning('上传成功，但未获取到任务ID');
    await loadDocs();
    return;
  }

  mergeJob({
    job_id: jobId,
    document_id: payload?.document_id,
    status: 'queued',
    stage: 'uploaded',
    progress: 0,
    updated_at: new Date().toISOString()
  });

  schedulePoll(jobId, 1000);
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

onMounted(refreshAll);

onBeforeUnmount(() => {
  pollingTimers.forEach((timer) => clearTimeout(timer));
  pollingTimers.clear();
});
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
