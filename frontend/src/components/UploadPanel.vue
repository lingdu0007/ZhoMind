<template>
  <div class="upload-card card">
    <el-upload
      drag
      :auto-upload="false"
      :on-change="handleFileChange"
      :show-file-list="true"
      accept=".txt,.md,.pdf,.doc,.docx,.xls,.xlsx"
      class="upload-drop"
    >
      <el-icon><upload-filled /></el-icon>
      <div class="el-upload__text">拖拽文件到这里，或 <em>点击选择</em></div>
      <template #tip>
        <div class="el-upload__tip">支持 txt / md / pdf / doc / docx / xls / xlsx</div>
      </template>
    </el-upload>

    <div class="actions">
      <el-button class="btn-primary" :loading="loading" @click="submit">上传并解析</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import { UploadFilled } from '@element-plus/icons-vue';
import { apiAdapter } from '../api/adapters';

const emit = defineEmits(['uploaded']);

const file = ref(null);
const loading = ref(false);

const handleFileChange = (rawFile) => {
  file.value = rawFile.raw;
};

const submit = async () => {
  if (!file.value) {
    ElMessage.warning('请先选择文件');
    return;
  }
  loading.value = true;
  try {
    const formData = new FormData();
    formData.append('file', file.value);
    await apiAdapter.uploadDocument(formData);
    ElMessage.success('上传成功，已提交解析');
    file.value = null;
    emit('uploaded');
  } catch (error) {
    ElMessage.error(error.message || '上传失败');
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.upload-card {
  padding: 32px;
}

.upload-drop {
  border: 1px dashed var(--line-strong);
  border-radius: 16px;
  background: var(--bg-shell);
  padding: 12px 0;
}

.actions {
  margin-top: 24px;
  display: flex;
  justify-content: flex-end;
}
</style>
